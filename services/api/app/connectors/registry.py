import hashlib
import json
import time
import uuid

from app.config import settings

from . import policy
from .base import ConnectorError
from .builtin import (CertTransparency, DnsRecords, ImageMetadata, Maigret, PhoneParse, Sherlock,
                      TheHarvester, Wayback, Whois, WikipediaBriefing)
from .sensitive import FaceCompare, FaceLocate, Ghunt, Holehe


def build() -> dict:
    cs = [DnsRecords(), Whois(), CertTransparency(), Wayback(), PhoneParse(), ImageMetadata(settings.evidence_dir),
          Maigret(), Sherlock(), TheHarvester(), WikipediaBriefing(),
          Holehe(), Ghunt(), FaceLocate(settings.evidence_dir), FaceCompare(settings.evidence_dir)]
    return {c.name: c for c in cs}


REGISTRY = build()


def describe() -> list[dict]:
    return [{"name": c.name, "kind": c.kind, "license": c.license, "description": c.description, "version": c.version(),
             "available": c.available(), "status": c.status(), "setup": c.setup_hint(),
             "requires_acknowledgment": c.people_adjacent} for c in REGISTRY.values()]


def execute(connector: str, target: str, purpose: str, acknowledged: bool = False) -> dict:
    """Policy check, run, and wrap in the KAAL agent contract. Never writes an accepted fact."""
    policy.check_denied(connector)
    c = REGISTRY.get(connector)
    if not c:
        raise policy.PolicyError(f"Unknown connector '{connector}'.")
    purpose = policy.check_purpose(purpose)
    if c.people_adjacent and not acknowledged:
        raise policy.PolicyError("This lookup concerns a person's online presence. Confirm it is lawful, authorized and "
                                 "consent-based or in the public interest (acknowledge=true).")
    target = c.normalise(target)
    if not c.available():
        raise ConnectorError(f"Connector '{connector}' is not installed on this deployment.")
    if c.setup_hint():
        raise ConnectorError(f"Connector '{connector}' needs setup: {c.setup_hint()}")
    started = time.time()
    raw = c.run(target)
    result = {
        "job_id": uuid.uuid4().hex[:12], "agent": f"connector.{c.name}", "connector": c.name, "connector_version": c.version(),
        "license": c.license, "target": target, "purpose": purpose,
        "outputs": raw["outputs"], "source_references": raw["source_references"],
        "confidence": round(raw["confidence"], 2), "warnings": raw["warnings"],
        "requires_human_review": True,
        "collected_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "duration_s": round(time.time() - started, 2),
    }
    result["sha256"] = hashlib.sha256(json.dumps(result["outputs"], sort_keys=True).encode()).hexdigest()
    return result
