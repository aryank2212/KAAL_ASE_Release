from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app import llm_backend as lb
from app.audit import audit
from app.database import get_db

router = APIRouter()


class LLMUpdate(BaseModel):
    provider: str | None = Field(default=None, max_length=20)
    base_url: str | None = Field(default=None, max_length=300)
    model: str | None = Field(default=None, max_length=200)
    embed_model: str | None = Field(default=None, max_length=200)
    api_key: str | None = Field(default=None, max_length=300)   # "" clears it; omit to keep
    verify: bool = True


@router.get("/llm")
def get_llm() -> dict:
    return lb.status()


@router.get("/llm/models")
def get_models() -> list[dict]:
    try:
        return lb.list_models()
    except lb.LLMError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.put("/llm")
def set_llm(payload: LLMUpdate, db: Session = Depends(get_db)) -> dict:
    cfg = lb.current()
    before = cfg.public()
    for f in ("provider", "base_url", "model", "embed_model", "api_key"):
        v = getattr(payload, f)
        if v is not None:
            setattr(cfg, f, v.strip())
    if payload.provider and payload.base_url is None and payload.provider != before["provider"]:
        cfg.base_url = lb.PROVIDERS.get(cfg.provider, cfg.base_url)     # sensible default port when only the provider changes
    try:
        cfg.base_url = lb.validate_base_url(cfg.base_url)
        if cfg.provider not in lb.PROVIDERS:
            raise lb.LLMError(f"provider must be one of {sorted(lb.PROVIDERS)}")
        if payload.verify:
            names = {m["name"] for m in lb.list_models(cfg)}
            for label, name in (("model", cfg.model), ("embed_model", cfg.embed_model)):
                if name not in names:
                    raise lb.LLMError(f"{label} '{name}' is not installed on {cfg.base_url}. Available: {sorted(names)[:30]}")
        lb.save(cfg)
    except lb.LLMError as e:
        raise HTTPException(status_code=422, detail=str(e))
    audit(db, action="llm.configure", resource_type="llm", resource_id=cfg.provider,
          metadata={"before": before, "after": cfg.public()})
    db.commit()
    return lb.status()


@router.post("/llm/test")
def test_llm() -> dict:
    try:
        reply = lb.chat("You are a connectivity probe.", "Reply with the single word: OK", temperature=0)
    except lb.LLMError as e:
        raise HTTPException(status_code=502, detail=str(e))
    return {"ok": True, "model": lb.current().model, "reply": reply.strip()[:80]}
