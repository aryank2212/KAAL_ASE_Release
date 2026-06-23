# Deployment Architecture

## Local MVP

Docker Compose runs:

- FastAPI API.
- PostgreSQL.
- Redis.
- Neo4j.
- Qdrant.
- MinIO.
- Ollama endpoint configured externally or as an optional profile.

## Kubernetes-Ready Production

Recommended workloads:

- `api-gateway` deployment.
- `ingestion-worker` deployment.
- `extractor-worker` deployment.
- `analysis-worker` deployment.
- `graph-worker` deployment.
- `frontend` deployment.
- Managed PostgreSQL.
- Managed Redis or Redis Cluster.
- Neo4j cluster.
- Qdrant cluster.
- S3-compatible object storage.

## Environment Boundaries

- `dev`: local and synthetic data only.
- `staging`: production-like infrastructure with anonymized or approved test data.
- `prod`: audited access, backups, monitoring, and retention policies.

## Observability

- Structured JSON logs with request IDs.
- Metrics: job latency, queue depth, extraction failures, model latency, search latency.
- Tracing across API, workers, and data stores.
- Security alerts for unusual export volume, failed access checks, and connector abuse.

## Backup and Recovery

- PostgreSQL point-in-time recovery.
- Object storage versioning.
- Neo4j periodic dumps.
- Qdrant snapshots.
- Audit log replication to immutable storage.
- Disaster recovery runbooks tested quarterly.

## CI/CD

- Static analysis and tests on every pull request.
- Container image signing.
- Database migration checks.
- Infrastructure policy checks.
- Promotion gates for production deploys.

