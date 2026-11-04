# Changelog

## 2.0.0
- New: OSINT connector layer (`app/connectors`) with ten connectors, one contract and one policy gate.
- New: `GET /api/v1/osint/connectors`, `POST /api/v1/cases/{id}/osint/run`; results stored as proposed Evidence with full audit.
- New: sourced-briefing connector (Wikipedia, verbatim quotes with revision permalinks, refuses pages about people).
- Removed: Holehe email-registration probing from the search agent. It is not a public-source lookup.
- Guardrails: purpose required and audited, lawful-use acknowledgment for username lookups, GHunt / Holehe / face matching hard-blocked.
- Tests: 15 new tests for policy, parsers, contract and API.
