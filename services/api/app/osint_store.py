import json
import logging
import os
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

from app.config import settings

# Lookups live under the configured data directory (KAAL_DATA_DIR). KAAL_LOOKUP_DIR still overrides it (Docker uses that).
# Created lazily: a read-only install location must never break importing the app.
DATA_DIR = Path(os.getenv("KAAL_LOOKUP_DIR") or (Path(settings.data_dir).expanduser() / "osint_lookups")).expanduser()


def save_lookup(data: dict) -> str:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    lookup_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    path = DATA_DIR / f"{lookup_id}.json"
    record = {"lookup_id": lookup_id, "timestamp": datetime.now().isoformat(), **data}
    with path.open("w", encoding="utf-8") as f:
        json.dump(record, f, indent=2, ensure_ascii=False, default=str)
    logger.info("Saved OSINT lookup %s", lookup_id)
    return lookup_id


def get_lookups(limit: int = 20) -> list[dict]:
    files = sorted(DATA_DIR.glob("*.json"), reverse=True)[:limit]
    results = []
    for f in files:
        try:
            with f.open(encoding="utf-8") as fh:
                results.append(json.load(fh))
        except Exception:
            logger.warning("Failed to read saved lookup %s", f.name, exc_info=True)
    return results


def get_lookup(lookup_id: str) -> dict | None:
    if not lookup_id or any(ch not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-" for ch in lookup_id):
        return None
    path = DATA_DIR / f"{lookup_id}.json"
    if path.is_file():
        with path.open(encoding="utf-8") as f:
            return json.load(f)
    return None
