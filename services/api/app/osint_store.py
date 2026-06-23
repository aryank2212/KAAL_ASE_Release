import json
import logging
import os
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

DATA_DIR = Path(os.path.dirname(os.path.abspath(__file__))) / ".." / ".." / ".." / "data" / "osint_lookups"
DATA_DIR.mkdir(parents=True, exist_ok=True)


def save_lookup(data: dict) -> str:
    lookup_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    path = DATA_DIR / f"{lookup_id}.json"
    record = {"lookup_id": lookup_id, "timestamp": datetime.now().isoformat(), **data}
    with open(path, "w") as f:
        json.dump(record, f, indent=2, default=str)
    logger.info("Saved OSINT lookup %s to %s", lookup_id, path)
    return lookup_id


def get_lookups(limit: int = 20) -> list[dict]:
    files = sorted(DATA_DIR.glob("*.json"), reverse=True)[:limit]
    results = []
    for f in files:
        try:
            with open(f) as fh:
                results.append(json.load(fh))
        except Exception as e:
            logger.warning("Failed to read %s: %s", f, e)
    return results


def get_lookup(lookup_id: str) -> dict | None:
    path = DATA_DIR / f"{lookup_id}.json"
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return None
