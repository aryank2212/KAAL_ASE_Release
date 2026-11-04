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
| `image_metadata` | image | ExifRead | BSD-3 | Files must already be in `EVIDENCE_DIR`. GPS is flagged as sensitive |
| `wikipedia_briefing` | topic | Wikipedia API | CC BY-SA text | Verbatim sentences with revision permalinks. Refuses pages about people |

## Deliberately not included

- **Holehe** (removed from V1): it probes sites' password-reset flows to learn whether an email is registered. Not a public source.
- **GHunt**: needs a logged-in Google session. Credentialed access is out of scope.
- **Face matching**: biometric identity matching stays off.

These names are hard-blocked in `app/connectors/policy.py` (`DENIED`), so a request for them is refused and audited.

## Using results

A username match is a lead, not proof of identity. Treat every connector output as unverified until an
analyst reviews it. Use the connectors only for lawful, authorized research.

## Installing optional tools

    pip install -r requirements.txt        # includes Maigret and Sherlock
    # theHarvester (GPL-2.0) is optional. Install it yourself, then:
    export THEHARVESTER_BIN=/path/to/theHarvester

## Third-party notices

The `wikipedia_briefing` connector returns text from Wikipedia under CC BY-SA 4.0; keep the permalink
attribution it provides when you reuse a claim. The other tools are used through their public packages
or CLIs under their own licences (see the table).
