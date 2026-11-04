"""Object detection over imagery tiles. Two detectors, chosen with KAAL_DETECTOR:

  baseline (default)  Classical bright-object-on-open-water finder. No model, no GPU. Finds ship-sized bright specks at
                      ~10 m/pixel. It is a heuristic and says so in every result.
  rfdetr              Adapter for an RF-DETR checkpoint (set KAAL_RFDETR_WEIGHTS, install the optional `rfdetr` package).
                      NOTE: the public KAAL model was trained on ground-vehicle photos. Sentinel-2 at 10 m/pixel cannot
                      show vehicles, so use this adapter only with a checkpoint trained on overhead imagery.
"""
import os

_RFDETR = {}
MAX_DETECTIONS = 400


def run(rgb) -> dict:
    which = os.environ.get("KAAL_DETECTOR", "baseline").lower()
    return _rfdetr(rgb) if which == "rfdetr" else _baseline(rgb)


def _baseline(rgb) -> dict:
    """Open water = large smooth areas that are not red-dominant. Ships = compact outliers inside it."""
    import cv2
    import numpy as np
    r, g, b = (rgb[..., i].astype("float32") for i in range(3))
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY).astype("float32")
    mean = cv2.blur(gray, (11, 11))
    texture = np.sqrt(np.maximum(cv2.blur(gray * gray, (11, 11)) - mean * mean, 0))
    brownish = r > np.maximum(g, b) + 5          # bare land / sediment-coloured ground; real water is not red-dominant
    water = ((texture < 7.0) & ~brownish).astype("uint8")   # forests and towns are rough (texture 30+), water is ~1-2
    water = cv2.morphologyEx(water, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    n_w, lab, st, _ = cv2.connectedComponentsWithStats(water, connectivity=8)
    big = np.zeros_like(water)
    for i in range(1, n_w):                                   # keep only large water bodies, not smooth roofs or fields
        if st[i, cv2.CC_STAT_AREA] > 0.004 * water.size:
            big[lab == i] = 1
    out = {"detector": "baseline-outlier-on-water", "detections": [], "max_score": 0.0, "warnings": [
        "Baseline heuristic, not the KAAL model: it flags bright or dark specks on open water and will include whitecaps, "
        "wakes, buoys and surf. Treat as candidates only."]}
    if big.mean() < 0.05:
        out["warnings"].append("Little open water in this scene, so no ship search was done.")
        return out
    # A ship is not itself smooth: close the mask over small holes before searching inside it.
    region = cv2.morphologyEx(big, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (25, 25)))
    inner = cv2.erode(region, np.ones((9, 9), np.uint8))
    diff = gray - cv2.blur(gray, (41, 41))
    sd = float(diff[inner > 0].std()) if inner.any() else 0.0
    thr = max(14.0, 4.0 * sd)
    cand = ((np.abs(diff) > thr) & (inner > 0)).astype("uint8")
    cand = cv2.morphologyEx(cand, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    n, _, stats, _ = cv2.connectedComponentsWithStats(cand, connectivity=8)
    dets = []
    for i in range(1, n):
        x, y, bw, bh, area = (int(v) for v in stats[i])
        if 3 <= area <= 600 and max(bw, bh) <= 45:
            contrast = float(np.abs(diff[y:y + bh, x:x + bw]).max())
            dets.append({"x": x, "y": y, "w": bw, "h": bh, "area_px": area, "label": "object_on_water",
                         "score": round(min(0.5, contrast / 160.0), 2)})
    dets.sort(key=lambda d: -d["score"])
    out["detections"] = dets[:MAX_DETECTIONS]
    out["total_candidates"] = len(dets)
    out["max_score"] = out["detections"][0]["score"] if dets else 0.0
    if len(dets) > MAX_DETECTIONS:
        out["warnings"].append(f"{len(dets)} candidates found; showing the {MAX_DETECTIONS} strongest.")
    return out


def _rfdetr(rgb) -> dict:
    weights = os.environ.get("KAAL_RFDETR_WEIGHTS")
    if not weights or not os.path.isfile(weights):
        raise RuntimeError("KAAL_DETECTOR=rfdetr needs KAAL_RFDETR_WEIGHTS pointing to a checkpoint file")
    try:
        from PIL import Image
        from rfdetr import RFDETRSmall
    except ImportError as e:
        raise RuntimeError("the optional 'rfdetr' package is not installed") from e
    if "m" not in _RFDETR:
        _RFDETR["m"] = RFDETRSmall(pretrain_weights=weights)
    m = _RFDETR["m"]
    det = m.predict(Image.fromarray(rgb), threshold=float(os.environ.get("KAAL_DETECTOR_THRESHOLD", "0.5")))
    names = getattr(m, "class_names", None) or {}
    dets = []
    for (x1, y1, x2, y2), c, cid in zip(det.xyxy, det.confidence, det.class_id):
        label = names.get(int(cid), str(int(cid))) if isinstance(names, dict) else str(int(cid))
        dets.append({"x": int(x1), "y": int(y1), "w": int(x2 - x1), "h": int(y2 - y1), "label": label, "score": round(float(c), 2)})
    dets.sort(key=lambda d: -d["score"])
    return {"detector": "rfdetr", "detections": dets[:100], "max_score": dets[0]["score"] if dets else 0.0,
            "warnings": ["RF-DETR adapter is untested in this release. Only meaningful with a checkpoint trained for the "
                         "imagery's resolution (the public KAAL model is ground-level)."]}
