from app.models import Evidence


EXTRACTOR_NAME = "metadata-agent"
EXTRACTOR_VERSION = "0.1.0"


def extract_evidence_metadata(evidence: Evidence) -> list[dict]:
    """Return baseline metadata observations available without reading the object payload."""
    return [
        {
            "observation_type": "evidence.file",
            "value": {
                "filename": evidence.filename,
                "media_type": evidence.media_type,
                "storage_uri": evidence.storage_uri,
                "sha256": evidence.sha256,
                "size_bytes": evidence.size_bytes,
            },
            "confidence": 1.0,
            "extractor": EXTRACTOR_NAME,
            "extractor_version": EXTRACTOR_VERSION,
        }
    ]

