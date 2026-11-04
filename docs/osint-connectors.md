# OSINT connectors (V2)

V2 wraps well-known public-source tools behind one contract and one policy gate.
Endpoints (all need `X-API-Key`):

    GET  /api/v1/osint/connectors
    POST /api/v1/cases/{case_id}/osint/run
         {"connector": "dns_records", "target": "example.com",
          "purpose": "Authorized brand-protection review",
          "acknowledge_lawful_use": false}

Every run returns the agent contract (`outputs`, `source_references`, `confidence`, `warnings`,
`requires_human_review: true`), is stored as **Evidence** with `ingestion_status = "proposed"`
(the full result and purpose are in `chain_of_custody`), and writes an audit event. Refusals and
errors are audited too. Nothing is promoted to an accepted fact by a connector.

| Connector | Kind | Tool | Licence | Notes |
|---|---|---|---|---|
| `dns_records` | domain | dnspython | ISC | A, AAAA, MX, NS, TXT, CAA, SOA |
| `whois` | domain | python-whois | MIT | Registrant names, emails and addresses are dropped by design |
| `cert_transparency` | domain | crt.sh | public logs | Subdomains from CT logs |
| `wayback` | domain | Internet Archive CDX | public archive | Up to 25 snapshots |
| `theharvester` | domain | theHarvester | GPL-2.0 | Opt-in. Run as a separate program (set `THEHARVESTER_BIN`), never imported. Passive sources only |
| `maigret` | username | Maigret | MIT | Top 150 sites. Needs `acknowledge_lawful_use` |
| `sherlock` | username | Sherlock | MIT | Needs `acknowledge_lawful_use` |
| `phone_parse` | phone | phonenumbers | Apache-2.0 | Offline validity and region only. No subscriber lookup |
| `image_metadata` | image | ExifTool (preferred) / ExifRead | Artistic or GPL / BSD-3 | Files must already be in `EVIDENCE_DIR`. Uses ExifTool when installed (far more complete), else ExifRead. Server paths are dropped, GPS is flagged |
| `sentinel2` | area | Sentinel-2 via Earth Search STAC | Copernicus open data | See [area-watch.md](area-watch.md). Detector is a baseline heuristic |
| `opensky` | area | OpenSky Network | research terms | Aircraft in a bounding box |
| `aisstream` | area | aisstream.io | free key | Vessels in a bounding box, ~12 s sample |
| `holehe` | email | Holehe | GPL-3.0 | Opt-in tool, run as a separate program. Contacts each service with the address. Needs acknowledgment |
| `ghunt` | email | GHunt | AGPL-3.0 | Run as a separate program under **your own** Google session (`ghunt login`, one manual step). Needs acknowledgment |
| `face_locate` | image | OpenCV YuNet | Apache-2.0 | Face bounding boxes for redaction. Detection only |
| `face_compare` | image | OpenCV SFace | Apache-2.0 | **1:1 only**: similarity of the one face in each of two evidence images. Needs acknowledgment |
| `wikipedia_briefing` | topic | Wikipedia API | CC BY-SA text | Verbatim sentences with revision permalinks. Refuses pages about people |

## Sensitive connectors (enabled in 2.1.0)

Holehe, GHunt and face comparison are on, behind the same gates as everything else: a stated purpose, the
lawful-use acknowledgment, and an audit event for every run and every refusal. Their results are always
proposed leads with `requires_human_review: true`.

- **Holehe** infers where an email is registered from each service's sign-up or recovery response, and sends
  the address to those services. Set `HOLEHE_NO_PASSWORD_RECOVERY=1` to skip the recovery-flow checks.
- **GHunt** needs a Google session. Run `ghunt login` once as the service user; until then the connector
  reports `status: needs_setup` and refuses to run. Its output can contain personal data from the account.
- **Face comparison is deliberately 1:1.** It compares two images that are already in the case evidence and
  requires exactly one face in each. There is no gallery, no web search and no "who is this" lookup. Scores
  use the published SFace operating point (cosine 0.363) and confidence is capped at 0.6. Face models are
  pinned by SHA-256 and re-checked on load.
- The old V1 behaviour of probing every email found in free text is **not** restored. These tools run only
  through the gated endpoint, one explicit request at a time.

Still blocked in `app/connectors/policy.py`: access to private accounts.

`GET /api/v1/osint/connectors` reports each connector as `ready`, `needs_setup` or `not_installed`.

## Using results

A username match is a lead, not proof of identity. Treat every connector output as unverified until an
analyst reviews it. Use the connectors only for lawful, authorized research.

## Installing optional tools

    pip install -r requirements.txt        # includes Maigret and Sherlock
    scripts/install_optional_tools.sh      # Holehe, GHunt (own venvs) + pinned face models
    export KAAL_TOOLS_DIR=~/.kaal/tools     # where the script installs them
    # theHarvester (GPL-2.0) is optional. Install it yourself, then:
    export THEHARVESTER_BIN=/path/to/theHarvester

## Third-party notices

The `wikipedia_briefing` connector returns text from Wikipedia under CC BY-SA 4.0; keep the permalink
attribution it provides when you reuse a claim. The other tools are used through their public packages
or CLIs under their own licences (see the table).
