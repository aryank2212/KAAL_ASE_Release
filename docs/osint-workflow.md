# OSINT Workflow

## Intake

1. Analyst creates a case and defines legal basis, purpose, and retention policy.
2. Analyst uploads public evidence or enables approved public-source connectors.
3. System records source URL, access time, collector identity, content hash, and licensing/terms notes when available.

## Collection

Collection sources:

- Uploaded images, PDFs, documents, videos, and audio.
- Search engine result aggregation through configured APIs.
- Public websites with crawler policy checks.
- News monitoring feeds.
- Public social media pages where collection is lawful and source terms allow it.
- Public records connectors where jurisdictionally approved.

## Extraction

Artifacts are processed by media type:

- Images: EXIF, OCR, object/vehicle/clothing detection, landmark candidates, face detection for redaction/indexing.
- PDFs/documents: metadata, text extraction, OCR fallback, embedded images, authorship fields.
- Video: container metadata, keyframes, OCR on frames, object/scene detection, audio extraction.
- Audio: metadata, transcription where permitted, speaker diarization only when approved.
- Web pages: title, canonical URL, text, links, dates, named entities, screenshots.

## Enrichment

- Normalize dates, names, organizations, handles, domains, phone/email strings, addresses, and coordinates.
- Reverse geocode coordinates.
- Convert observations into candidate entities and timeline events.
- Generate embeddings for semantic search.
- Add graph nodes and edges with provenance.

## Review

Analysts review candidate facts:

- Accept: promoted to profile or graph fact.
- Reject: preserved as rejected with reason.
- Needs more evidence: converted to lead.
- Merge: links duplicate entities with audit trail.

## Analysis

AI assists with:

- Case summaries.
- Profile summaries.
- Timeline summaries.
- Inconsistency detection.
- Missing-source warnings.
- Investigative lead suggestions.
- Pattern and cluster detection.

AI output must cite source references and remains a draft until reviewed.

## Reporting

Reports include:

- Scope and legal basis.
- Methodology.
- Findings.
- Confidence explanations.
- Source citations.
- Analyst review record.
- Export audit ID.

