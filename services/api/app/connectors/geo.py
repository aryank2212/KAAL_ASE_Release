"""Open-source geospatial connectors: Sentinel-2 imagery (Copernicus data via the Earth Search STAC), OpenSky flights,
aisstream.io vessel positions. All three are public data about aircraft, vessels and places, not people."""
import hashlib
import json
import math
import os
import re
import time
from pathlib import Path
from urllib.parse import urlparse

import httpx

from app.config import settings

from . import policy
from .base import Connector, ConnectorError

UA = "KAAL-ASE/2.2 (+https://redclove.space)"
STAC_URL = "https://earth-search.aws.element84.com/v1/search"
ALLOWED_COG_HOSTS = ("sentinel-cogs.s3.us-west-2.amazonaws.com", "sentinel-cogs.s3.amazonaws.com")
MAX_PIXELS = 1024
ATTRIBUTION = "Contains modified Copernicus Sentinel data"


def parse_bbox(value: str, max_span_deg: float) -> tuple[float, float, float, float]:
    """'west,south,east,north' in degrees."""
    try:
        w, s, e, n = (float(x) for x in re.split(r"[,\s]+", (value or "").strip(), maxsplit=3))
    except ValueError:
        raise policy.PolicyError("Give a bounding box as: west,south,east,north (decimal degrees).")
    if not (-180 <= w < e <= 180 and -90 <= s < n <= 90):
        raise policy.PolicyError("Bounding box is out of range or west/south is not smaller than east/north.")
    if (e - w) > max_span_deg or (n - s) > max_span_deg:
        raise policy.PolicyError(f"Bounding box is too large (max {max_span_deg} degrees per side).")
    return w, s, e, n


def imagery_dir() -> Path:
    d = Path(settings.data_dir).expanduser() / "imagery"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _get_json(url: str, **kw) -> dict:
    headers = {"User-Agent": UA, **kw.pop("headers", {})}
    try:
        r = httpx.get(url, headers=headers, timeout=kw.pop("timeout", 20), **kw)
    except httpx.HTTPError as e:
        raise ConnectorError(f"source did not respond: {type(e).__name__}")
    if r.status_code == 429:
        raise ConnectorError("source rate limit reached; try again later")
    if r.status_code >= 400:
        raise ConnectorError(f"source returned HTTP {r.status_code}")
    try:
        return r.json()
    except ValueError:
        raise ConnectorError("source returned an unreadable response")


# ---- Sentinel-2 -------------------------------------------------------------------------------------------
def _check_cog_url(url: str) -> str:
    u = urlparse(url)
    if u.scheme != "https" or u.hostname not in ALLOWED_COG_HOSTS:
        raise ConnectorError("refusing to read imagery from an unexpected host")
    return url


def read_window(cog_url: str, bbox: tuple) -> tuple["np.ndarray", dict]:       # noqa: F821
    """Windowed read of a cloud-optimised GeoTIFF (HTTP range requests). Returns RGB uint8 HxWx3 + georeference."""
    import numpy as np
    import rasterio
    from affine import Affine
    from rasterio.warp import transform_bounds
    from rasterio.windows import from_bounds

    with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR", CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif,.TIF",
                      GDAL_HTTP_TIMEOUT="20", GDAL_HTTP_MAX_RETRY="2"):
        with rasterio.open(cog_url) as ds:
            l, b, r, t = transform_bounds("EPSG:4326", ds.crs, *bbox)
            win = from_bounds(l, b, r, t, ds.transform).round_offsets().round_lengths()
            win = win.intersection(rasterio.windows.Window(0, 0, ds.width, ds.height))
            if win.width < 8 or win.height < 8:
                raise ConnectorError("the scene does not cover that area")
            scale = min(1.0, MAX_PIXELS / max(win.width, win.height))
            shape = (3, max(8, int(win.height * scale)), max(8, int(win.width * scale)))
            data = ds.read([1, 2, 3], window=win, out_shape=shape)
            tr = ds.window_transform(win) * Affine.scale(win.width / shape[2], win.height / shape[1])
            geo = {"crs": ds.crs.to_string(), "transform": list(tr)[:6], "width": shape[2], "height": shape[1]}
    return np.transpose(data, (1, 2, 0)).astype("uint8"), geo


def pixel_to_lonlat(geo: dict, x: float, y: float) -> tuple[float, float]:
    from rasterio.warp import transform
    a, b, c, d, e, f = geo["transform"]
    E, N = a * x + b * y + c, d * x + e * y + f
    lon, lat = transform(geo["crs"], "EPSG:4326", [E], [N])
    return round(lon[0], 5), round(lat[0], 5)


class Sentinel2(Connector):
    name, kind, license = "sentinel2", "area", "Copernicus Sentinel data (free and open, attribution required)"
    description = ("Latest low-cloud Sentinel-2 scene over an area (10 m/pixel) with an optional detector pass. "
                   "Target: west,south,east,north")
    dist = "rasterio"

    def available(self):
        try:
            import rasterio  # noqa: F401
            return True
        except ImportError:
            return False

    def normalise(self, t):
        return ",".join(f"{v:.5f}" for v in parse_bbox(t, 0.6))

    def search(self, bbox):
        body = {"collections": ["sentinel-2-l2a"], "bbox": list(bbox), "limit": 5,
                "query": {"eo:cloud_cover": {"lt": 40}}, "sortby": [{"field": "properties.datetime", "direction": "desc"}]}
        try:
            r = httpx.post(STAC_URL, json=body, headers={"User-Agent": UA}, timeout=25)
            r.raise_for_status()
            return r.json().get("features", [])
        except (httpx.HTTPError, ValueError) as e:
            raise ConnectorError(f"scene search failed: {type(e).__name__}")

    def run(self, target):
        import cv2
        from . import detector
        bbox = tuple(float(x) for x in target.split(","))
        feats = self.search(bbox)
        if not feats:
            raise ConnectorError("No recent low-cloud Sentinel-2 scene covers that area.")
        item = min(feats[:3], key=lambda f: f["properties"].get("eo:cloud_cover", 100))
        href = _check_cog_url(item["assets"]["visual"]["href"])
        rgb, geo = read_window(href, bbox)
        name = hashlib.sha256(f"{item['id']}{bbox}".encode()).hexdigest()[:16] + ".png"
        cv2.imwrite(str(imagery_dir() / name), cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR))
        det = detector.run(rgb)
        for d in det["detections"]:
            d["lon"], d["lat"] = pixel_to_lonlat(geo, d["x"] + d["w"] / 2, d["y"] + d["h"] / 2)
        props = item["properties"]
        from rasterio.transform import Affine as _A, array_bounds
        from rasterio.warp import transform_bounds
        a_, b_, c_, d_, e_, f_ = geo["transform"]
        l_, b2, r_, t_ = array_bounds(geo["height"], geo["width"], _A(a_, b_, c_, d_, e_, f_))
        ib = [round(v, 6) for v in transform_bounds(geo["crs"], "EPSG:4326", l_, b2, r_, t_)]
        return {"outputs": {"image_bounds": ib, "scene_id": item["id"], "captured": props.get("datetime"), "cloud_cover": props.get("eo:cloud_cover"),
                            "bbox": list(bbox), "preview": name, "size": [geo["width"], geo["height"]],
                            "detector": det["detector"], "detections": det["detections"], "total_candidates": det.get("total_candidates", len(det["detections"])), "attribution": f"{ATTRIBUTION} ({(props.get('datetime') or '')[:4]})"},
                "source_references": [f"{STAC_URL.rsplit('/search', 1)[0]}/collections/sentinel-2-l2a/items/{item['id']}"],
                "confidence": 0.9 if det["detections"] == [] else min(0.5, det["max_score"]),
                "warnings": det["warnings"] + [f"{ATTRIBUTION}. Scenes are days old: this is not live imagery."]}


# ---- OpenSky ----------------------------------------------------------------------------------------------
class OpenSky(Connector):
    name, kind, license = "opensky", "area", "OpenSky Network data (research/non-commercial terms)"
    description = "Aircraft state vectors inside a bounding box (ADS-B/Mode-S). Target: west,south,east,north"

    def normalise(self, t): return ",".join(f"{v:.4f}" for v in parse_bbox(t, 10.0))

    def _token(self):
        cid, sec = os.environ.get("OPENSKY_CLIENT_ID"), os.environ.get("OPENSKY_CLIENT_SECRET")
        if not (cid and sec):
            return None
        try:
            r = httpx.post("https://auth.opensky-network.org/auth/realms/opensky-network/protocol/openid-connect/token",
                           data={"grant_type": "client_credentials", "client_id": cid, "client_secret": sec}, timeout=15)
            r.raise_for_status()
            return r.json()["access_token"]
        except (httpx.HTTPError, KeyError, ValueError):
            raise ConnectorError("OpenSky login failed; check OPENSKY_CLIENT_ID / OPENSKY_CLIENT_SECRET")

    def run(self, target):
        w, s, e, n = (float(x) for x in target.split(","))
        tok = self._token()
        url = f"https://opensky-network.org/api/states/all?lamin={s}&lomin={w}&lamax={n}&lomax={e}"
        data = _get_json(url, headers={"Authorization": f"Bearer {tok}"} if tok else {})
        out = []
        for st in (data.get("states") or [])[:300]:
            if st[5] is None or st[6] is None:
                continue
            out.append({"icao24": st[0], "callsign": (st[1] or "").strip(), "country": st[2], "lon": st[5], "lat": st[6],
                        "altitude_m": st[7] if st[7] is not None else st[13], "speed_ms": st[9], "heading": st[10],
                        "on_ground": st[8], "last_contact": st[4]})
        warns = ["ADS-B coverage is incomplete: many military and some civil aircraft do not appear."]
        if not tok:
            warns.append("Anonymous access is rate limited; set OPENSKY_CLIENT_ID / OPENSKY_CLIENT_SECRET for more.")
        return {"outputs": {"aircraft": out, "count": len(out), "snapshot_time": data.get("time")},
                "source_references": [url.split("?")[0] + "?bbox=" + target], "confidence": 0.8 if out else 0.0, "warnings": warns}


# ---- aisstream.io -----------------------------------------------------------------------------------------
class AisStream(Connector):
    name, kind, license, dist = "aisstream", "area", "aisstream.io terms (free API key)", "websockets"
    description = "Vessel positions in a bounding box from the live AIS stream, sampled for a few seconds. Needs AISSTREAM_API_KEY."
    SECONDS = 12
    MAX_MESSAGES = 400
    URL = os.environ.get("AISSTREAM_URL", "wss://stream.aisstream.io/v0/stream")

    def available(self):
        try:
            import websockets  # noqa: F401
            return True
        except ImportError:
            return False

    def setup_hint(self):
        return None if os.environ.get("AISSTREAM_API_KEY") else "set AISSTREAM_API_KEY (free key from aisstream.io)"

    def normalise(self, t): return ",".join(f"{v:.4f}" for v in parse_bbox(t, 6.0))

    def run(self, target):
        from websockets.exceptions import ConnectionClosed
        from websockets.sync.client import connect
        w, s, e, n = (float(x) for x in target.split(","))
        sub = {"APIKey": os.environ["AISSTREAM_API_KEY"], "BoundingBoxes": [[[s, w], [n, e]]], "FilterMessageTypes": ["PositionReport"]}
        ships, end = {}, time.time() + self.SECONDS
        try:
            with connect(self.URL, open_timeout=10, max_size=2**20) as ws:
                ws.send(json.dumps(sub))
                while time.time() < end and len(ships) < self.MAX_MESSAGES:
                    try:
                        raw = ws.recv(timeout=max(0.1, end - time.time()))
                    except TimeoutError:
                        break
                    m = json.loads(raw)
                    if "error" in m:
                        raise ConnectorError(f"aisstream refused the request: {str(m['error'])[:120]}")
                    pr, meta = m.get("Message", {}).get("PositionReport"), m.get("MetaData", {})
                    if pr and meta.get("MMSI"):
                        ships[meta["MMSI"]] = {"mmsi": meta["MMSI"], "name": (meta.get("ShipName") or "").strip(), "lon": pr["Longitude"],
                                               "lat": pr["Latitude"], "speed_kn": pr.get("Sog"), "course": pr.get("Cog"),
                                               "heading": pr.get("TrueHeading"), "nav_status": pr.get("NavigationalStatus"),
                                               "time_utc": meta.get("time_utc")}
        except ConnectorError:
            raise
        except ConnectionClosed as cc:
            if not ships:
                raise ConnectorError(f"AIS stream closed before any data arrived (code {cc.rcvd.code if cc.rcvd else 'none'}); check the API key")
        except Exception as ex:
            raise ConnectorError(f"AIS stream error: {type(ex).__name__}")
        vessels = list(ships.values())
        return {"outputs": {"vessels": vessels, "count": len(vessels), "sample_seconds": self.SECONDS},
                "source_references": ["wss://stream.aisstream.io/v0/stream"], "confidence": 0.7 if vessels else 0.0,
                "warnings": ["A few seconds of the stream only: vessels that report rarely may be missing.",
                             "AIS is self-reported and can be switched off or spoofed."]}
