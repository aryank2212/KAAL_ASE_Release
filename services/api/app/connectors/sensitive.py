"""Higher-risk connectors, enabled in 2.1.0. They pass the same gates as every connector (purpose, lawful-use
acknowledgment, audit) and their results are always proposed leads, never accepted facts."""
import hashlib
import json
import os
import pathlib
import re
import tempfile

from . import policy
from .base import Connector, ConnectorError, find_binary, run_cli, tools_dir
from .builtin import FOUND_RE  # noqa: F401  (shared parsing conventions)

SERVICE_RE = re.compile(r"^\[([+\-x])\]\s+([A-Za-z0-9.\-]+\.[A-Za-z]{2,})\s*$", re.M)
MIN_USABLE = 0.30  # at least this share of checks must give a usable answer, or the run is reported as failed


class Holehe(Connector):
    """GPL-3.0, so it runs as a separate program from its own venv and is never imported."""
    name, kind, license = "holehe", "email", "GPL-3.0 (run as external program)"
    description = "Which services an email address appears to be registered on (Holehe). Contacts each service's endpoint with that address."
    people_adjacent = True
    timeout = 180

    def available(self): return find_binary("holehe", "HOLEHE_BIN") is not None
    def normalise(self, t): return policy.normalise_email(t)

    def run(self, email):
        bin_ = find_binary("holehe", "HOLEHE_BIN")
        if not bin_:
            raise ConnectorError("holehe is not installed")
        args = [bin_, email, "--no-color", "--no-clear", "-T", "10"]
        if os.environ.get("HOLEHE_NO_PASSWORD_RECOVERY") == "1":
            args.append("-NP")
        text = run_cli(args, self.timeout).replace("\r", "\n")
        marks = {}
        for flag, svc in SERVICE_RE.findall(text):
            marks[svc] = flag          # last status per service wins
        used = sorted(s for s, f in marks.items() if f == "+")
        failed = sum(1 for f in marks.values() if f == "x")
        checked = len(marks)
        usable = checked - failed
        if checked == 0:
            raise ConnectorError("holehe produced no results")
        if usable / checked < MIN_USABLE:
            raise ConnectorError(f"holehe could not get a usable answer from most services ({failed} of {checked} failed or were "
                                 "rate-limited from this host). This is NOT a negative result; retry later or from another network.")
        warns = ["Registration is inferred from each site's response and can be wrong or stale. It is a lead, not proof of identity.",
                 "This lookup sends the address to each service's sign-up or recovery endpoint."]
        if failed:
            warns.append(f"{failed} of {checked} services failed or were rate-limited, so absence from the list is not proof of non-registration.")
        return {"outputs": {"services": used, "count": len(used), "checked": checked, "usable_answers": usable, "failed": failed},
                "source_references": [f"https://{s}" for s in used], "confidence": 0.5 if used else 0.0, "warnings": warns}


class Ghunt(Connector):
    """AGPL-3.0, run as a separate program. Uses the ANALYST'S OWN Google session (`ghunt login`)."""
    name, kind, license = "ghunt", "email", "AGPL-3.0 (run as external program)"
    description = "Public Google account signals for a Gmail/Google address (GHunt). Needs `ghunt login` with your own Google session."
    people_adjacent = True
    timeout = 120

    def _creds(self) -> pathlib.Path:
        return pathlib.Path(os.environ.get("GHUNT_CREDS", os.path.expanduser("~/.malfrats/ghunt/creds.m")))

    def available(self): return find_binary("ghunt", "GHUNT_BIN") is not None
    def setup_hint(self):
        return None if self._creds().is_file() else "run `ghunt login` once as the service user to authorise your own Google session"
    def normalise(self, t): return policy.normalise_email(t)

    def run(self, email):
        bin_ = find_binary("ghunt", "GHUNT_BIN")
        if not bin_:
            raise ConnectorError("ghunt is not installed")
        out = os.path.join(tempfile.mkdtemp(prefix="kaal-ghunt-"), "out.json")
        run_cli([bin_, "email", email, "--json", out], self.timeout)
        try:
            data = json.load(open(out, encoding="utf-8"))
        except (OSError, ValueError):
            raise ConnectorError("ghunt produced no readable output (session expired, or no public Google profile)")
        if len(json.dumps(data)) > 100_000:
            data = {"truncated": True, "keys": sorted(data)[:50]}
        return {"outputs": {"ghunt": data}, "source_references": [f"ghunt://{email}"], "confidence": 0.6,
                "warnings": ["Runs under the analyst's own Google session. Output can contain personal data: review before sharing.",
                             "A Google profile for an address is a lead, not proof of who controls it."]}


# ---- faces ---------------------------------------------------------------------------------------------
DET = "face_detection_yunet_2023mar.onnx"
REC = "face_recognition_sface_2021dec.onnx"
MODEL_SHA256 = {
    DET: "8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4",
    REC: "0ba9fbfa01b5270c96627c4ef784da859931e02f04419c829e83484087c34e79",
}
COSINE_THRESHOLD = 0.363  # published SFace operating point
MAX_IMAGE_BYTES = 15_000_000
_verified: set[str] = set()


def models_dir() -> pathlib.Path:
    return pathlib.Path(os.environ.get("KAAL_MODELS_DIR", os.path.join(tools_dir(), "models")))


def _model(name: str) -> str:
    path = models_dir() / name
    if not path.is_file():
        raise ConnectorError(f"face model missing: {name} (see docs/osint-connectors.md)")
    if name not in _verified:
        if hashlib.sha256(path.read_bytes()).hexdigest() != MODEL_SHA256[name]:
            raise ConnectorError(f"face model {name} failed its checksum")
        _verified.add(name)
    return str(path)


def models_ready() -> bool:
    return all((models_dir() / n).is_file() for n in MODEL_SHA256)


def load_image(evidence_dir: str, filename: str):
    import cv2
    import numpy as np
    root = pathlib.Path(evidence_dir).resolve()
    path = (root / filename).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise ConnectorError(f"'{filename}' not found in the evidence store.")
    if path.stat().st_size > MAX_IMAGE_BYTES:
        raise ConnectorError("Image too large (15 MB max).")
    img = cv2.imdecode(np.frombuffer(path.read_bytes(), np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise ConnectorError(f"'{filename}' is not a readable image.")
    h, w = img.shape[:2]
    if max(h, w) > 1600:
        s = 1600 / max(h, w)
        img = cv2.resize(img, (int(w * s), int(h * s)))
    return img


def detect(img):
    import cv2
    h, w = img.shape[:2]
    det = cv2.FaceDetectorYN.create(_model(DET), "", (w, h), 0.8, 0.3, 50)
    det.setInputSize((w, h))
    _, faces = det.detect(img)
    return [] if faces is None else list(faces)


def _box(f):
    return {"x": int(f[0]), "y": int(f[1]), "w": int(f[2]), "h": int(f[3]), "score": round(float(f[-1]), 3)}


class _FaceBase(Connector):
    kind = "image"
    dist = "opencv-python-headless"

    def __init__(self, evidence_dir: str):
        self.evidence_dir = evidence_dir

    def available(self):
        try:
            import cv2  # noqa: F401
        except ImportError:
            return False
        return models_ready()

    def _name(self, t):
        t = (t or "").strip()
        if not t or t.startswith("/") or ".." in t.split("/"):
            raise policy.PolicyError("Give filenames inside the evidence store (no absolute paths or '..').")
        return t


class FaceLocate(_FaceBase):
    name, license = "face_locate", "Apache-2.0 (OpenCV YuNet model)"
    description = "Locate faces in an evidence image (bounding boxes, e.g. for redaction). Detection only, no identification."

    def normalise(self, t): return self._name(t)

    def run(self, filename):
        faces = detect(load_image(self.evidence_dir, filename))
        return {"outputs": {"faces": [_box(f) for f in faces], "count": len(faces)},
                "source_references": [f"evidence://{filename}"], "confidence": 0.8 if faces else 0.0,
                "warnings": [] if faces else ["No faces detected."]}


class FaceCompare(_FaceBase):
    name, license = "face_compare", "Apache-2.0 (OpenCV SFace model)"
    description = "1:1 similarity of the single face in each of two evidence images. Not a search: it never looks anyone up."
    people_adjacent = True

    def normalise(self, t):
        parts = [self._name(p) for p in (t or "").split(",")]
        if len(parts) != 2 or parts[0] == parts[1]:
            raise policy.PolicyError("Give exactly two different evidence filenames separated by a comma.")
        return ",".join(parts)

    def run(self, target):
        import cv2
        a_name, b_name = target.split(",")
        a, b = load_image(self.evidence_dir, a_name), load_image(self.evidence_dir, b_name)
        fa, fb = detect(a), detect(b)
        if len(fa) != 1 or len(fb) != 1:
            raise ConnectorError(f"Each image must contain exactly one face (found {len(fa)} and {len(fb)}).")
        rec = cv2.FaceRecognizerSF.create(_model(REC), "")
        ea = rec.feature(rec.alignCrop(a, fa[0]))
        eb = rec.feature(rec.alignCrop(b, fb[0]))
        score = float(rec.match(ea, eb, cv2.FaceRecognizerSF_FR_COSINE))
        above = score >= COSINE_THRESHOLD
        conf = 0.3 + 0.3 * min(1.0, (score - COSINE_THRESHOLD) / 0.3) if above else 0.1
        return {"outputs": {"cosine_score": round(score, 4), "threshold": COSINE_THRESHOLD,
                            "verdict": "above_threshold" if above else "below_threshold",
                            "faces": {a_name: _box(fa[0]), b_name: _box(fb[0])}},
                "source_references": [f"evidence://{a_name}", f"evidence://{b_name}"], "confidence": conf,
                "warnings": ["Face similarity is a lead, not an identification. False matches and misses happen, more so across "
                             "lighting, age, pose and demographic groups. Never act on it without human review."]}
