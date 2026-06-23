# Agent Architecture

## Agent Roles

KAAL-ASE agents are bounded workers with explicit permissions, inputs, outputs, and audit events. Agents do not directly promote AI conclusions into accepted profile facts.

| Agent | Responsibility | Writes |
| --- | --- | --- |
| Ingestion Agent | Validates input, stores raw objects, creates extraction jobs | evidence, source references, jobs |
| Metadata Agent | Extracts EXIF, document metadata, media metadata, hashes | observations |
| OCR Agent | Extracts text from images and PDFs | observations, text chunks |
| Web Discovery Agent | Runs approved public search/news/crawl connectors | source references, evidence |
| Entity Agent | Performs NER and entity normalization | entities, candidate links |
| Geolocation Agent | Extracts coordinates, place names, reverse geocoding candidates | locations, observations |
| Vision Agent | Detects objects, vehicles, clothing, landmarks, and faces for indexing/redaction | observations |
| Timeline Agent | Converts dated observations into timeline events | timeline events |
| Graph Agent | Creates graph nodes/edges with provenance | Neo4j graph |
| Embedding Agent | Chunks text and stores embeddings | Qdrant vectors |
| Analysis Agent | Summarizes, detects inconsistencies, proposes leads | AI analysis records |
| Review Agent | Tracks analyst approvals, rejections, and requested corrections | review decisions |

## Agent Contract

Every agent job includes:

```json
{
  "job_id": "",
  "case_id": "",
  "actor_id": "",
  "agent_type": "",
  "input_refs": [],
  "policy_context": {},
  "created_at": "",
  "priority": "normal"
}
```

Every agent output includes:

```json
{
  "job_id": "",
  "outputs": [],
  "source_references": [],
  "confidence": 0.0,
  "warnings": [],
  "requires_human_review": true
}
```

## Orchestration

- Redis Streams or Celery queues handle MVP execution.
- Jobs are idempotent by evidence checksum and extractor version.
- Failed jobs move to a dead-letter queue with structured error metadata.
- Extractor version is stored with every observation to support reprocessing.
- Agent actions emit audit events.

## AI Safety Controls

- Prompt templates include source citation requirements.
- Model outputs are stored separately from accepted facts.
- Risk scores are explainable and reviewable.
- High-impact labels require analyst approval.
- PII minimization policies apply to model context construction.

