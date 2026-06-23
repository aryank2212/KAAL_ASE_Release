# Roadmap

## MVP Roadmap

### Phase 1: Foundation

- FastAPI service with health, cases, profiles, evidence, and search stubs.
- PostgreSQL schema for cases, profiles, evidence, observations, timeline, audit, and versions.
- Docker Compose for local services.
- RBAC policy skeleton.
- Immutable audit event writer.

### Phase 2: Evidence and Extraction

- File upload workflow with object storage.
- Metadata extraction for images, PDFs, documents, videos, and audio.
- OCR pipeline for images and PDFs.
- Evidence checksum and source attribution.
- Extraction job queue.

### Phase 3: Intelligence Model

- Entity extraction and normalization.
- Profile candidate builder.
- Timeline builder.
- Confidence scoring framework.
- Analyst review workflow.

### Phase 4: Retrieval and Graph

- Qdrant vector indexing.
- Natural language and semantic search.
- Neo4j graph projection.
- Basic graph visualization API.
- Geospatial query support.

### Phase 5: AI Assistance

- Local Ollama integration.
- Cited summaries.
- Inconsistency detection.
- Lead generation.
- Human approval workflow for sensitive outputs.

### Phase 6: Dashboard

- Case management UI.
- Profile workspace.
- Evidence explorer.
- Timeline view.
- Map view.
- Graph view.
- Report builder.

## Production Roadmap

- OIDC integration and enterprise RBAC.
- Policy engine with jurisdiction and source-specific rules.
- Kubernetes deployment manifests and Helm chart.
- Managed secrets integration.
- Advanced graph algorithms and temporal graph snapshots.
- Connector marketplace with legal/policy metadata.
- Export approval workflow and watermarking.
- Full-text search with PostgreSQL or OpenSearch.
- Model evaluation harness for AI analysis quality.
- Data retention and deletion automation.
- Red-team testing and privacy impact assessment.
- SOC2-style operational controls.

