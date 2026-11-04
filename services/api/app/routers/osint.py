from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.audit import audit
from app.connectors import registry
from app.connectors.base import ConnectorError
from app.connectors.policy import PolicyError
from app.database import get_db
from app.models import Case, Evidence

router = APIRouter()


class OsintRun(BaseModel):
    connector: str = Field(max_length=40)
    target: str = Field(max_length=300)
    purpose: str = Field(max_length=500)
    acknowledge_lawful_use: bool = False


@router.get("/osint/connectors")
def list_connectors() -> list[dict]:
    return registry.describe()


@router.post("/cases/{case_id}/osint/run", status_code=status.HTTP_201_CREATED)
def run_connector(case_id: UUID, payload: OsintRun, db: Session = Depends(get_db)) -> dict:
    if not db.get(Case, case_id):
        raise HTTPException(status_code=404, detail="Case not found")
    try:
        result = registry.execute(payload.connector, payload.target, payload.purpose, payload.acknowledge_lawful_use)
    except PolicyError as e:
        audit(db, action="osint.refused", resource_type="connector", resource_id=payload.connector, case_id=case_id,
              metadata={"reason": str(e), "purpose": payload.purpose[:200]})
        db.commit()
        raise HTTPException(status_code=422, detail=str(e))
    except ConnectorError as e:
        audit(db, action="osint.error", resource_type="connector", resource_id=payload.connector, case_id=case_id,
              metadata={"error": str(e)})
        db.commit()
        raise HTTPException(status_code=502, detail=str(e))

    ev = Evidence(
        case_id=case_id, filename=f"{result['connector']}-{result['sha256'][:10]}.json",
        media_type="application/vnd.kaal.connector-result+json", storage_uri=f"connector://{result['connector']}/{result['sha256']}",
        sha256=result["sha256"], size_bytes=len(str(result["outputs"])),
        chain_of_custody=[{"event": "connector.run", "connector": result["connector"], "version": result["connector_version"],
                           "collected_at": result["collected_at"], "purpose": result["purpose"],
                           "acknowledged_lawful_use": payload.acknowledge_lawful_use, "result": result}],
        ingestion_status="proposed",
    )
    db.add(ev)
    db.flush()
    audit(db, action="osint.run", resource_type="evidence", resource_id=str(ev.evidence_id), case_id=case_id,
          metadata={"connector": result["connector"], "target": result["target"], "purpose": result["purpose"],
                    "sources": len(result["source_references"])})
    db.commit()
    return {"evidence_id": str(ev.evidence_id), **result}
