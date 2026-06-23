from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Case


router = APIRouter()


@router.get("/cases/{case_id}/graph")
def get_case_graph(case_id: UUID, db: Session = Depends(get_db)) -> dict:
    if not db.get(Case, case_id):
        raise HTTPException(status_code=404, detail="Case not found")
    return {"nodes": [], "edges": []}

