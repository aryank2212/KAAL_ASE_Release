# Data Ingestion Pipeline

## Pipeline Stages

```mermaid
flowchart TD
    A["Input: upload, URL, connector"] --> B["Policy and source validation"]
    B --> C["Object storage write"]
    C --> D["Evidence record and checksum"]
    D --> E["Media type detection"]
    E --> F["Extractor jobs"]
    F --> G["Observations"]
    G --> H["Entity resolution"]
    H --> I["Timeline builder"]
    H --> J["Graph builder"]
    G --> K["Embedding builder"]
    I --> L["Analyst review"]
    J --> L
    K --> M["Search"]
```

## Evidence Identity

Each evidence item receives:

- `evidence_id`
- SHA-256 hash
- storage URI
- source reference
- media type
- chain-of-custody metadata
- ingestion policy decision

## Extractor Outputs

Observations use a common envelope:

```json
{
  "observation_id": "",
  "case_id": "",
  "evidence_id": "",
  "type": "entity.person",
  "value": {},
  "confidence": 0.81,
  "source_reference_id": "",
  "extractor": "metadata-agent",
  "extractor_version": "0.1.0",
  "review_status": "candidate"
}
```

## Queue Design

Queues:

- `ingest.requested`
- `extract.metadata`
- `extract.ocr`
- `extract.vision`
- `extract.audio`
- `enrich.entity`
- `enrich.geo`
- `index.vector`
- `index.graph`
- `analysis.requested`
- `report.requested`

## Reprocessing

Reprocessing is triggered when:

- Extractor version changes.
- Analyst requests it.
- New model version is approved.
- Source is refreshed.

Old observations are not overwritten; they are superseded with links to replacement records.

