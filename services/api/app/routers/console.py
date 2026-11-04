"""Endpoints the dashboard needs: listings, review, imagery previews, system summary."""
import platform
import re
import time
from urllib.parse import urlparse
from uuid import UUID

import httpx

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import llm_backend
from app.config import settings
from app.audit import audit
from app.connectors import registry
from app.connectors.geo import imagery_dir
from app.database import get_db
from app.models import AuditEvent, Case, Evidence

router = APIRouter()
STARTED = time.time()
VERSION = "2.2.0"


def _case(c: Case) -> dict:
    return {"case_id": str(c.case_id), "title": c.title, "description": c.description, "legal_basis": c.legal_basis,
            "status": c.status, "created_at": c.created_at.isoformat() if c.created_at else None}


def _evidence(e: Evidence, full: bool = False) -> dict:
    coc = e.chain_of_custody or []
    run = coc[0] if coc and isinstance(coc[0], dict) else {}
    d = {"evidence_id": str(e.evidence_id), "case_id": str(e.case_id), "filename": e.filename, "media_type": e.media_type,
         "status": e.ingestion_status, "created_at": e.created_at.isoformat() if e.created_at else None,
         "connector": run.get("connector"), "purpose": run.get("purpose")}
    res = run.get("result") or {}
    d["summary"] = {"confidence": res.get("confidence"), "warnings": res.get("warnings", []), "target": res.get("target"),
                    "sources": len(res.get("source_references", []))}
    if full:
        d["result"] = res
    return d


@router.get("/cases")
def list_cases(db: Session = Depends(get_db), limit: int = Query(100, le=500)) -> list[dict]:
    return [_case(c) for c in db.scalars(select(Case).order_by(Case.created_at.desc()).limit(limit))]


@router.get("/cases/{case_id}/evidence")
def list_evidence(case_id: UUID, db: Session = Depends(get_db), limit: int = Query(200, le=500)) -> list[dict]:
    if not db.get(Case, case_id):
        raise HTTPException(404, "Case not found")
    rows = db.scalars(select(Evidence).where(Evidence.case_id == case_id).order_by(Evidence.created_at.desc()).limit(limit))
    return [_evidence(e) for e in rows]


@router.get("/evidence/{evidence_id}")
def get_evidence(evidence_id: UUID, db: Session = Depends(get_db)) -> dict:
    e = db.get(Evidence, evidence_id)
    if not e:
        raise HTTPException(404, "Evidence not found")
    return _evidence(e, full=True)


class Review(BaseModel):
    decision: str
    note: str = ""


@router.post("/evidence/{evidence_id}/review")
def review_evidence(evidence_id: UUID, body: Review, db: Session = Depends(get_db)) -> dict:
    """The analyst, not an agent, promotes or rejects a proposed finding."""
    if body.decision not in ("accepted", "rejected"):
        raise HTTPException(422, "decision must be 'accepted' or 'rejected'")
    e = db.get(Evidence, evidence_id)
    if not e:
        raise HTTPException(404, "Evidence not found")
    before = e.ingestion_status
    e.ingestion_status = body.decision
    e.chain_of_custody = [*(e.chain_of_custody or []), {"event": "review", "decision": body.decision, "note": body.note[:500],
                                                         "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}]
    audit(db, action=f"evidence.{body.decision}", resource_type="evidence", resource_id=str(e.evidence_id), case_id=e.case_id,
          metadata={"before": before, "note": body.note[:200]})
    db.commit()
    return _evidence(e)


@router.get("/audit")
def list_audit(db: Session = Depends(get_db), limit: int = Query(100, le=500), case_id: UUID | None = None) -> list[dict]:
    q = select(AuditEvent).order_by(AuditEvent.created_at.desc()).limit(limit)
    if case_id:
        q = q.where(AuditEvent.case_id == case_id)
    return [{"at": a.created_at.isoformat() if a.created_at else None, "action": a.action, "resource_type": a.resource_type,
             "resource_id": a.resource_id, "case_id": str(a.case_id) if a.case_id else None, "metadata": a.metadata_json}
            for a in db.scalars(q)]


@router.get("/imagery/{name}")
def get_imagery(name: str):
    if not re.fullmatch(r"[a-f0-9]{16}\.png", name):
        raise HTTPException(404, "Not found")
    p = imagery_dir() / name
    if not p.is_file():
        raise HTTPException(404, "Not found")
    return FileResponse(p, media_type="image/png", headers={"Cache-Control": "private, max-age=3600"})


@router.get("/system")
def system(db: Session = Depends(get_db)) -> dict:
    conns = registry.describe()
    return {"version": VERSION, "python": platform.python_version(), "platform": platform.platform(),
            "uptime_s": int(time.time() - STARTED),
            "counts": {"cases": db.query(Case).count(), "evidence": db.query(Evidence).count(),
                       "proposed": db.query(Evidence).filter_by(ingestion_status="proposed").count()},
            "connectors": {s: sum(1 for c in conns if c["status"] == s) for s in ("ready", "needs_setup", "not_installed")},
            "llm": {k: v for k, v in llm_backend.status().items() if k != "models"}}


def globe_origin() -> str:
    """Origin of the configured God's Eye View instance, or '' when unset or not a plain http(s) origin."""
    u = urlparse((settings.globe_url or "").strip())
    if u.scheme not in ("http", "https") or not u.hostname or u.username or u.password:
        return ""
    return f"{u.scheme}://{u.netloc}"


@router.get("/globe")
def globe() -> dict:
    """Is a God's Eye View instance configured for the Globe tab, and does it answer?"""
    origin = globe_origin()
    if not origin:
        return {"configured": False, "setup": "Set KAAL_GLOBE_URL to your God's Eye View address (for example http://100.64.0.1:4173) "
                "and restart. See docs/globe.md or run scripts/install-globe.sh."}
    try:
        r = httpx.get(origin + "/", timeout=4, follow_redirects=False)
        reachable, err = r.status_code < 500, (None if r.status_code < 500 else f"HTTP {r.status_code}")
    except httpx.HTTPError as e:
        reachable, err = False, f"cannot reach {origin} ({type(e).__name__})"
    return {"configured": True, "url": origin, "reachable": reachable, "error": err}
