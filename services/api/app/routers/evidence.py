from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.audit import audit
from app.database import get_db
from app.models import Case, Evidence, IngestionJob, Observation
from app.schemas import EvidenceCreate, EvidenceRead, IngestionJobRead, ObservationRead


router = APIRouter()


@router.post("/cases/{case_id}/evidence", response_model=EvidenceRead, status_code=status.HTTP_201_CREATED)
def register_evidence(case_id: UUID, payload: EvidenceCreate, db: Session = Depends(get_db)) -> Evidence:
    if not db.get(Case, case_id):
        raise HTTPException(status_code=404, detail="Case not found")

    evidence = Evidence(case_id=case_id, **payload.model_dump())
    db.add(evidence)
    db.flush()
    audit(
        db,
        action="evidence.register",
        resource_type="evidence",
        resource_id=str(evidence.evidence_id),
        case_id=case_id,
        metadata={"filename": evidence.filename, "sha256": evidence.sha256},
    )
    db.commit()
    db.refresh(evidence)
    return evidence


@router.post("/evidence/{evidence_id}/ingest", response_model=IngestionJobRead, status_code=status.HTTP_202_ACCEPTED)
def queue_ingestion(evidence_id: UUID, response: Response, db: Session = Depends(get_db)) -> IngestionJob:
    evidence = db.get(Evidence, evidence_id)
    if not evidence:
        raise HTTPException(status_code=404, detail="Evidence not found")

    evidence.ingestion_status = "queued"
    job = IngestionJob(
        case_id=evidence.case_id,
        evidence_id=evidence.evidence_id,
        job_type="extract.all",
        priority="normal",
    )
    db.add(job)
    db.flush()
    audit(
        db,
        action="evidence.ingest.queue",
        resource_type="evidence",
        resource_id=str(evidence.evidence_id),
        case_id=evidence.case_id,
        metadata={"ingestion_job_id": str(job.ingestion_job_id)},
    )
    db.commit()
    db.refresh(job)
    response.headers["Location"] = f"/api/v1/ingestion-jobs/{job.ingestion_job_id}"
    return job


@router.get("/evidence/{evidence_id}/observations", response_model=list[ObservationRead])
def list_observations(evidence_id: UUID, db: Session = Depends(get_db)) -> list[Observation]:
    evidence = db.get(Evidence, evidence_id)
    if not evidence:
        raise HTTPException(status_code=404, detail="Evidence not found")

    return (
        db.query(Observation)
        .filter(Observation.evidence_id == evidence_id)
        .order_by(Observation.created_at.desc())
        .all()
    )


@router.get("/ingestion-jobs/{ingestion_job_id}", response_model=IngestionJobRead)
def get_ingestion_job(ingestion_job_id: UUID, db: Session = Depends(get_db)) -> IngestionJob:
    job = db.get(IngestionJob, ingestion_job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Ingestion job not found")
    return job
