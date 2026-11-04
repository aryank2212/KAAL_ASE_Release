import asyncio
import json
import os
import threading
import unittest
from unittest.mock import patch

import numpy as np
import rasterio
from rasterio.transform import from_origin
from rasterio.warp import transform_bounds

from app.connectors import builtin, detector, geo, policy, registry
from app.connectors.base import ConnectorError

TMP = os.path.join(os.environ["KAAL_DATA_DIR"], "geo-test")
os.makedirs(TMP, exist_ok=True)
E0, N0, PX, SIZE = 700000.0, 1925000.0, 10.0, 400
BLOBS = [(60, 70), (200, 150), (320, 300)]        # (x, y) top-left of 3x3 bright ships


def make_scene(path):
    rng = np.random.default_rng(1)
    img = np.zeros((3, SIZE, SIZE), np.uint8)
    img[0], img[1], img[2] = 20, 50, 90                      # open water
    img += rng.integers(0, 4, img.shape, dtype=np.uint8)
    img[:, :, :40] = np.array([120, 110, 80], np.uint8)[:, None, None]     # land strip on the left
    for x, y in BLOBS:
        img[:, y:y + 3, x:x + 3] = 235
    with rasterio.open(path, "w", driver="GTiff", width=SIZE, height=SIZE, count=3, dtype="uint8", crs="EPSG:32643",
                       transform=from_origin(E0, N0, PX, PX)) as dst:
        dst.write(img)
    return transform_bounds("EPSG:32643", "EPSG:4326", E0, N0 - SIZE * PX, E0 + SIZE * PX, N0)


class BBoxTests(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(geo.parse_bbox("77.1, 12.2, 77.3, 12.4", 1), (77.1, 12.2, 77.3, 12.4))
        for bad in ("1,2,3", "a,b,c,d", "10,10,5,20", "0,0,50,50", "-200,0,0,10", "0,95,1,96"):
            with self.assertRaises(policy.PolicyError, msg=bad):
                geo.parse_bbox(bad, 1)


class DetectorTests(unittest.TestCase):
    def test_baseline_finds_ships_on_water_not_land(self):
        p = os.path.join(TMP, "scene.tif"); bbox = make_scene(p)
        rgb, g = geo.read_window(p, bbox)
        res = detector.run(rgb)
        self.assertEqual(res["detector"], "baseline-outlier-on-water")
        self.assertGreaterEqual(len(res["detections"]), 3)
        xs = sorted(d["x"] for d in res["detections"])
        for bx, _ in BLOBS:
            self.assertTrue(any(abs(x - bx) <= 3 for x in xs), f"missed ship near x={bx}: {xs}")
        self.assertTrue(all(d["x"] > 38 for d in res["detections"]), "detection on the land strip")
        self.assertIn("heuristic", res["warnings"][0])

    def test_no_water_means_no_search(self):
        land = np.full((200, 200, 3), (120, 110, 80), np.uint8)
        r = detector.run(land)
        self.assertEqual(r["detections"], [])
        self.assertTrue(any("open water" in w for w in r["warnings"]))

    def test_rfdetr_requires_weights(self):
        with patch.dict(os.environ, {"KAAL_DETECTOR": "rfdetr"}, clear=False):
            os.environ.pop("KAAL_RFDETR_WEIGHTS", None)
            with self.assertRaises(RuntimeError):
                detector.run(np.zeros((10, 10, 3), np.uint8))


class Sentinel2Tests(unittest.TestCase):
    def test_full_run_with_local_scene(self):
        p = os.path.join(TMP, "scene2.tif"); bbox = make_scene(p)
        item = {"id": "S2TEST_1", "properties": {"datetime": "2026-10-30T05:00:00Z", "eo:cloud_cover": 3.2},
                "assets": {"visual": {"href": p}}}
        c = geo.Sentinel2()
        with patch.object(c, "search", return_value=[item]), patch.object(geo, "_check_cog_url", lambda u: u):
            r = c.run(",".join(f"{v:.5f}" for v in bbox))
        o = r["outputs"]
        self.assertEqual(o["scene_id"], "S2TEST_1")
        self.assertTrue((geo.imagery_dir() / o["preview"]).is_file())
        self.assertGreaterEqual(len(o["detections"]), 3)
        d = o["detections"][0]
        self.assertTrue(bbox[0] <= d["lon"] <= bbox[2] and bbox[1] <= d["lat"] <= bbox[3], (d, bbox))
        self.assertIn("Copernicus", o["attribution"])
        self.assertTrue(r["requires_human_review"] if "requires_human_review" in r else True)

    def test_refuses_unexpected_hosts(self):
        for bad in ("http://sentinel-cogs.s3.us-west-2.amazonaws.com/a.tif", "https://evil.example/a.tif",
                    "file:///etc/passwd", "https://sentinel-cogs.s3.us-west-2.amazonaws.com.evil.io/a.tif"):
            with self.assertRaises(ConnectorError, msg=bad):
                geo._check_cog_url(bad)
        geo._check_cog_url("https://sentinel-cogs.s3.us-west-2.amazonaws.com/x/TCI.tif")

    def test_no_scene(self):
        c = geo.Sentinel2()
        with patch.object(c, "search", return_value=[]), self.assertRaises(ConnectorError):
            c.run("77.1,12.2,77.2,12.3")


class OpenSkyTests(unittest.TestCase):
    def test_parse_states_and_skip_positionless(self):
        states = [["abc123", "AIC101  ", "India", 1, 1700000000, 78.4, 17.4, 11000.0, False, 230.0, 90.0, 0, None, 11100.0],
                  ["def456", "", "India", None, 1700000001, None, None, None, True, 0, 0, 0, None, None]]
        with patch.object(geo, "_get_json", return_value={"time": 1700000002, "states": states}):
            r = geo.OpenSky().run("77,16,80,18")
        self.assertEqual(r["outputs"]["count"], 1)
        a = r["outputs"]["aircraft"][0]
        self.assertEqual((a["callsign"], a["altitude_m"], a["lon"]), ("AIC101", 11000.0, 78.4))
        self.assertTrue(any("incomplete" in w for w in r["warnings"]))

    def test_bbox_limits(self):
        with self.assertRaises(policy.PolicyError): geo.OpenSky().normalise("0,0,30,30")


class AisTests(unittest.TestCase):
    def test_collects_positions_from_stream(self):
        from websockets.sync.server import serve
        def handler(ws):
            sub = json.loads(ws.recv())
            assert sub["APIKey"] == "k" and sub["BoundingBoxes"] == [[[12.0, 77.0], [13.0, 78.0]]]
            ws.send(json.dumps({"Message": {"PositionReport": {"Latitude": 12.5, "Longitude": 77.5, "Sog": 11.2, "Cog": 80.0,
                                                                "TrueHeading": 81, "NavigationalStatus": 0}},
                                "MetaData": {"MMSI": 419000001, "ShipName": "MV TEST   ", "time_utc": "2026-11-04 10:00:00"}}))
            ws.send(json.dumps({"Message": {"PositionReport": {"Latitude": 12.6, "Longitude": 77.6}}, "MetaData": {"MMSI": 419000002}}))
            import time; time.sleep(0.5)
        with serve(handler, "127.0.0.1", 0) as srv:
            threading.Thread(target=srv.serve_forever, daemon=True).start()
            c = geo.AisStream(); c.SECONDS = 2
            with patch.object(geo.AisStream, "URL", f"ws://127.0.0.1:{srv.socket.getsockname()[1]}"), \
                 patch.dict(os.environ, {"AISSTREAM_API_KEY": "k"}):
                self.assertIsNone(c.setup_hint())
                r = c.run("77,12,78,13")
        self.assertEqual(r["outputs"]["count"], 2)
        self.assertEqual(r["outputs"]["vessels"][0]["name"], "MV TEST")

    def test_needs_key(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("AISSTREAM_API_KEY", None)
            self.assertIn("AISSTREAM_API_KEY", geo.AisStream().setup_hint())


class ExifToolTests(unittest.TestCase):
    def test_exiftool_engine_and_filtering(self):
        f = os.path.join(os.environ["EVIDENCE_DIR"], "p.jpg"); os.makedirs(os.path.dirname(f), exist_ok=True); open(f, "wb").write(b"x")
        out = json.dumps([{"SourceFile": f, "System:FileName": "p.jpg", "ExifTool:ExifToolVersion": 13.6,
                           "IFD0:Make": "Canon", "ExifIFD:DateTimeOriginal": "2026:01:01 10:00:00", "GPS:GPSLatitude": 12.97, "XMP-dc:Creator": "A"}])
        c = builtin.ImageMetadata(os.environ["EVIDENCE_DIR"])
        with patch.object(builtin, "find_binary", return_value="/usr/bin/exiftool"), patch.object(builtin, "run_cli", return_value=out) as rc:
            r = c.run("p.jpg")
        self.assertEqual(r["outputs"]["engine"], "exiftool")
        self.assertNotIn("System:FileName", r["outputs"]["tags"])
        self.assertIn("XMP-dc:Creator", r["outputs"]["tags"])
        self.assertTrue(r["outputs"]["has_gps"])
        args = rc.call_args[0][0]
        self.assertEqual(args[-2], "--")            # path can never be parsed as an option

    def test_falls_back_to_exifread(self):
        import cv2
        f = os.path.join(os.environ["EVIDENCE_DIR"], "q.jpg"); cv2.imwrite(f, np.zeros((20, 20, 3), np.uint8))
        c = builtin.ImageMetadata(os.environ["EVIDENCE_DIR"])
        with patch.object(builtin, "find_binary", return_value=None):
            r = c.run("q.jpg")
        self.assertEqual(r["outputs"]["engine"], "exifread")
        self.assertTrue(any("ExifTool is not installed" in w for w in r["warnings"]))


class RegistryTests(unittest.TestCase):
    def test_new_connectors_registered(self):
        names = {c["name"]: c for c in registry.describe()}
        for n in ("sentinel2", "opensky", "aisstream"):
            self.assertIn(n, names)
        self.assertEqual(names["aisstream"]["status"], "needs_setup" if not os.environ.get("AISSTREAM_API_KEY") else "ready")


if __name__ == "__main__":
    unittest.main()
