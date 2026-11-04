# Changelog

## Unreleased
- Fixed the `theharvester` connector for theHarvester 4.11: it asked for a source that no longer exists (`threatminer`), would have failed on every run, and could lose its report when a temp path contained a dot. Hosts, IPs, ASNs and emails are now parsed and normalised, and `total_hosts` reports the real count.
- `install-optional-tools.sh` now installs theHarvester 4.11.1 (via uv) as well.

## 2.2.0
- Remote model host: Ollama or LM Studio (for example your laptop) selectable at runtime from the console or `kaal-model`; all LLM calls go through one switchable backend. See docs/remote-models.md.
- New connectors: `sentinel2` (Copernicus Sentinel-2 imagery with a baseline ship-candidate detector), `opensky` (flights), `aisstream` (ships).
- `image_metadata` now uses ExifTool when installed, falling back to ExifRead.
- Web console at `/ui/` (overview, investigate with analyst accept/reject, area-watch map, models, audit).
- Installers: `.deb`, Arch package and Windows `.exe`, built and smoke-tested by the release workflow. `kaal-ase` launcher with SQLite and an auto-generated API key.
- Analyst review endpoint (`POST /evidence/{id}/review`), listing endpoints, `GET /system`.
- Fixed: test runs no longer touch the real home directory.

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
