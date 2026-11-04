"""Guardrails every connector run passes through. Mirrors the five KAAL ASE rules."""
import re

DOMAIN_RE = re.compile(r"^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$")
USERNAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,38}[A-Za-z0-9]$")
INTERNAL_SUFFIXES = (".local", ".internal", ".localhost", ".lan", ".home", ".corp", ".onion", ".arpa")

# Capabilities KAAL ASE refuses by design. Names are matched against requested connectors.
DENIED = {
    "holehe": "Probes sites' password-reset flows to learn whether an email is registered. Not a public source.",
    "ghunt": "Requires a logged-in Google session. Credentialed access is out of scope.",
    "face_match": "Biometric identity matching is off. Faces may only be located for redaction.",
    "private_account": "No access to private accounts.",
}


class PolicyError(ValueError):
    pass


def check_denied(connector: str) -> None:
    if connector in DENIED:
        raise PolicyError(f"'{connector}' is blocked by design: {DENIED[connector]}")


def check_purpose(purpose: str) -> str:
    purpose = (purpose or "").strip()
    if len(purpose) < 10:
        raise PolicyError("State the purpose of this lookup (at least 10 characters). It is written to the audit trail.")
    if len(purpose) > 500:
        raise PolicyError("Purpose is too long (500 characters max).")
    return purpose


def normalise_domain(value: str) -> str:
    v = (value or "").strip().lower().rstrip(".")
    if not v or "/" in v or ":" in v or " " in v or "@" in v:
        raise PolicyError("Give a bare domain such as example.com (no scheme, path, port or email).")
    try:
        v = v.encode("idna").decode("ascii")
    except UnicodeError:
        raise PolicyError("Invalid domain.")
    if v.endswith(INTERNAL_SUFFIXES) or not DOMAIN_RE.match(v):
        raise PolicyError("Only public domain names are allowed. IP addresses and internal names are refused.")
    return v


def normalise_username(value: str) -> str:
    v = (value or "").strip().lstrip("@")
    if not USERNAME_RE.match(v):
        raise PolicyError("Username must be 2-40 characters: letters, digits, dot, dash, underscore.")
    return v


def normalise_phone(value: str) -> str:
    v = (value or "").strip()
    if not re.fullmatch(r"\+[0-9 ()\-]{6,25}", v):
        raise PolicyError("Give a phone number in international format, e.g. +14155550100.")
    return v


def normalise_topic(value: str) -> str:
    v = (value or "").strip()
    if not 4 <= len(v) <= 200:
        raise PolicyError("Ask a question between 4 and 200 characters.")
    return v
