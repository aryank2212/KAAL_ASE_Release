# Changelog

## 2.1.0
- Enabled Holehe (`holehe`), GHunt (`ghunt`) and face matching (`face_locate`, 1:1 `face_compare`) as connectors.
  They require a stated purpose and the lawful-use acknowledgment, and are audited like every other run.
- Holehe and GHunt run as separate programs from isolated venvs (GPL-3.0 / AGPL-3.0 are not linked in).
  GHunt needs a one-time `ghunt login`; connectors now report `ready` / `needs_setup` / `not_installed`.
- Face comparison is 1:1 on case evidence only (exactly one face per image), with SHA-256-pinned models.
- Policy denylist now only blocks private-account access.
- `scripts/install_optional_tools.sh` installs the optional tools and models.

## 2.0.0
- New: OSINT connector layer (`app/connectors`) with ten connectors, one contract and one policy gate.
- New: `GET /api/v1/osint/connectors`, `POST /api/v1/cases/{id}/osint/run`; results stored as proposed Evidence with full audit.
- New: sourced-briefing connector (Wikipedia, verbatim quotes with revision permalinks, refuses pages about people).
- Removed: Holehe email-registration probing from the search agent. It is not a public-source lookup.
- Guardrails: purpose required and audited, lawful-use acknowledgment for username lookups, GHunt / Holehe / face matching hard-blocked.
- Tests: 15 new tests for policy, parsers, contract and API.
