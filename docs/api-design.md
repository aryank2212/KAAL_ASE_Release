# API Design

## API Style

- Protocol: HTTPS JSON REST for MVP.
- Auth: OIDC-compatible JWT bearer tokens.
- Versioning: `/api/v1`.
- Idempotency: mutation endpoints accept `Idempotency-Key`.
- Traceability: all responses include `request_id`.
- Authorization: role and case-level policy checks on every endpoint.

## Core Resources

- Cases
- Profiles
- Evidence objects
- Source references
- Observations
- Timeline events
- Relationships
- AI analyses
- Search requests
- Reports
- Audit events

## Representative Endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/api/v1/cases` | Create case |
| `GET` | `/api/v1/cases/{case_id}` | Retrieve case |
| `POST` | `/api/v1/cases/{case_id}/profiles` | Create profile |
| `GET` | `/api/v1/profiles/{profile_id}` | Retrieve structured profile |
| `PATCH` | `/api/v1/profiles/{profile_id}` | Update profile with version record |
| `POST` | `/api/v1/cases/{case_id}/evidence` | Register uploaded evidence metadata |
| `POST` | `/api/v1/evidence/{evidence_id}/ingest` | Queue extraction jobs |
| `GET` | `/api/v1/evidence/{evidence_id}/observations` | List extracted observations |
| `POST` | `/api/v1/search` | Natural language, entity, semantic, timeline, or geo search |
| `GET` | `/api/v1/profiles/{profile_id}/timeline` | Timeline for profile |
| `GET` | `/api/v1/cases/{case_id}/graph` | Graph subnetwork |
| `POST` | `/api/v1/analysis/summarize` | Generate reviewable AI summary |
| `POST` | `/api/v1/reports` | Generate cited report draft |
| `GET` | `/api/v1/audit` | Search audit logs |

## Standard Error Shape

```json
{
  "request_id": "req_01J...",
  "error": {
    "code": "policy_denied",
    "message": "User does not have access to this case.",
    "details": {}
  }
}
```

## Profile Response Shape

```json
{
  "profile_id": "prf_01J...",
  "case_id": "case_01J...",
  "name": "John Doe",
  "aliases": [],
  "known_locations": [],
  "social_profiles": [],
  "images": [],
  "documents": [],
  "timeline": [],
  "relationships": [],
  "confidence_score": 0.72,
  "risk_score": 0.31,
  "source_references": [],
  "review_status": "draft",
  "version": 4
}
```

## Search Request Shape

```json
{
  "case_id": "case_01J...",
  "query": "Show all locations associated with John Doe.",
  "modes": ["natural_language", "entity", "geospatial"],
  "filters": {
    "date_from": "2026-05-24",
    "date_to": "2026-06-23",
    "min_confidence": 0.6
  }
}
```

