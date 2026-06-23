from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Case
from app.schemas import SearchRequest


router = APIRouter()


@router.post("/search")
def search(payload: SearchRequest, db: Session = Depends(get_db)) -> dict:
    if not db.get(Case, payload.case_id):
        raise HTTPException(status_code=404, detail="Case not found")
    return {
        "query": payload.query,
        "modes": payload.modes,
        "results": [],
        "note": "Vector, graph, timeline, and geospatial adapters are the next implementation layer.",
    }

