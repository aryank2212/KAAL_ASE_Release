import logging
import os
import time
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.audit import audit
from app.database import SessionLocal
from app.extractors import extract_evidence_metadata, extract_social_indicators
from app.models import Evidence, IngestionJob, Observation

logger = logging.getLogger(__name__)


def process_next_job(db: Session) -> IngestionJob | None:
    job = (
        db.query(IngestionJob)
        .filter(IngestionJob.status == "queued")
        .order_by(IngestionJob.created_at.asc())
        .with_for_update(skip_locked=True)
        .first()
    )
    if not job:
        return None

    evidence = db.get(Evidence, job.evidence_id)
    if not evidence:
        job.status = "failed"
        job.error_message = "Evidence not found"
        job.finished_at = datetime.now(UTC)
        db.commit()
        return job

    job.status = "processing"
    job.started_at = datetime.now(UTC)
    evidence.ingestion_status = "processing"
    db.flush()

    try:
        all_observations = []
        all_observations.extend(extract_evidence_metadata(evidence))
        all_observations.extend(extract_social_indicators(evidence))

        for item in all_observations:
            db.add(
                Observation(
                    case_id=evidence.case_id,
                    evidence_id=evidence.evidence_id,
                    source_reference_id=evidence.source_reference_id,
                    **item,
                )
            )

        job.status = "complete"
        job.extractor = "metadata-agent+social-indicator-extractor"
        job.extractor_version = "0.1.0"
        job.finished_at = datetime.now(UTC)
        evidence.ingestion_status = "complete"
        audit(
            db,
            action="evidence.ingest.complete",
            resource_type="ingestion_job",
            resource_id=str(job.ingestion_job_id),
            case_id=evidence.case_id,
            metadata={"observation_count": len(all_observations)},
        )
    except Exception as exc:
        logger.exception("Evidence ingestion failed for job %s", job.ingestion_job_id)
        job.status = "failed"
        job.error_message = f"Ingestion failed ({type(exc).__name__})"
        job.finished_at = datetime.now(UTC)
        evidence.ingestion_status = "failed"
        audit(
            db,
            action="evidence.ingest.failed",
            resource_type="ingestion_job",
            resource_id=str(job.ingestion_job_id),
            case_id=evidence.case_id,
            metadata={"error_type": type(exc).__name__},
        )

    db.commit()
    db.refresh(job)
    return job


def main() -> None:
    poll_seconds = max(0.25, float(os.getenv("WORKER_POLL_SECONDS", "2")))
    logger.info("Ingestion worker started (poll interval: %.2fs)", poll_seconds)
    while True:
        try:
            with SessionLocal() as db:
                job = process_next_job(db)
            if job is None:
                time.sleep(poll_seconds)
            else:
                logger.info("Processed ingestion job %s: %s", job.ingestion_job_id, job.status)
        except KeyboardInterrupt:
            logger.info("Ingestion worker stopped")
            break
        except Exception:
            logger.exception("Ingestion worker iteration failed")
            time.sleep(poll_seconds)


if __name__ == "__main__":
    main()
