import datetime
import email.utils
import json
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.audit import audit
from app.config import settings
from app.database import get_db
from app.llm import (
    _chat,
    analyze_sentiment,
    classify_media_type,
    detect_inconsistencies,
    embed_text,
    extract_entities,
    generate_leads,
    generate_name_suggestions,
    summarize,
)
from app.models import Case, Evidence, Observation
from app.osint_store import save_lookup
from app.schemas import (
    ClassifyRequest,
    ClassifyResponse,
    DetectInconsistenciesRequest,
    EntityExtractionResponse,
    ExtractEntitiesRequest,
    GenerateLeadsRequest,
    InconsistenciesResponse,
    LeadItem,
    LeadsResponse,
    SentimentRequest,
    SentimentResponse,
    SummarizeRequest,
    SummarizeResponse,
)
from app.search_web import fetch_page_text, search_web
from app.social_search import search_social_profiles
from app.task_planner import analyze_goal, create_plan
from app.task_executor import TaskExecutor

logger = logging.getLogger(__name__)
router = APIRouter()


def _to_str_list(val: Any) -> list[str]:
    if isinstance(val, list):
        return [str(v) for v in val]
    if isinstance(val, dict):
        return [f"{k}: {v}" for k, v in val.items()]
    if isinstance(val, str):
        return [val]
    return []


def _to_dict_list(val: Any) -> list[dict]:
    if isinstance(val, list):
        return [v if isinstance(v, dict) else {"value": str(v)} for v in val]
    if isinstance(val, dict):
        return [val]
    return []


@router.post("/analysis/summarize", response_model=SummarizeResponse)
def analyze_summarize(payload: SummarizeRequest) -> SummarizeResponse:
    result = summarize(payload.text, payload.max_length)
    return SummarizeResponse(
        title=result.get("title", "Summary"),
        summary=result.get("summary", result.get("text", "")),
        key_facts=_to_str_list(result.get("key_facts", result.get("facts", []))),
    )


@router.post("/analysis/extract-entities", response_model=EntityExtractionResponse)
def analyze_extract_entities(
    payload: ExtractEntitiesRequest, db: Session = Depends(get_db)
) -> EntityExtractionResponse:
    entities = extract_entities(payload.text)

    if payload.evidence_id:
        evidence = db.get(Evidence, payload.evidence_id)
        if evidence:
            for ent in entities:
                obs = Observation(
                    case_id=evidence.case_id,
                    evidence_id=evidence.evidence_id,
                    observation_type=f"entity.{ent.get('type', 'unknown')}",
                    value={
                        "name": ent.get("name"),
                        "type": ent.get("type"),
                        "context": ent.get("context"),
                    },
                    confidence=ent.get("confidence", 0.5),
                    extractor=settings.ollama_model,
                    extractor_version="0.1.0",
                )
                db.add(obs)

            audit(
                db,
                action="analysis.entities.extracted",
                resource_type="evidence",
                resource_id=str(payload.evidence_id),
                case_id=evidence.case_id,
                metadata={"entity_count": len(entities)},
            )
            db.commit()

    return EntityExtractionResponse(entities=_to_dict_list(entities))


@router.post("/analysis/detect-inconsistencies", response_model=InconsistenciesResponse)
def analyze_inconsistencies(payload: DetectInconsistenciesRequest) -> InconsistenciesResponse:
    issues = detect_inconsistencies(payload.text)
    return InconsistenciesResponse(inconsistencies=_to_dict_list(issues))


@router.post("/analysis/generate-leads", response_model=LeadsResponse)
def analyze_generate_leads(
    payload: GenerateLeadsRequest, db: Session = Depends(get_db)
) -> LeadsResponse:
    case = db.get(Case, payload.case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    context = {
        "case_title": case.title,
        "case_description": case.description,
        "case_status": case.status,
        **payload.context,
    }

    leads = generate_leads(context)

    audit(
        db,
        action="analysis.leads.generated",
        resource_type="case",
        resource_id=str(case.case_id),
        case_id=case.case_id,
        metadata={"lead_count": len(leads)},
    )
    db.commit()

    return LeadsResponse(leads=[LeadItem(**l) for l in leads])


@router.post("/analysis/sentiment", response_model=SentimentResponse)
def analyze_sentiment_endpoint(payload: SentimentRequest) -> SentimentResponse:
    result = analyze_sentiment(payload.text)
    return SentimentResponse(
        sentiment=result.get("sentiment", "neutral"),
        confidence=result.get("confidence", 0.5),
        key_emotional_indicators=_to_str_list(result.get("key_emotional_indicators", [])),
    )


@router.post("/analysis/classify", response_model=ClassifyResponse)
def analyze_classify(payload: ClassifyRequest) -> ClassifyResponse:
    result = classify_media_type(payload.text)
    return ClassifyResponse(
        category=result.get("category", "unknown"),
        subcategory=result.get("subcategory", ""),
        confidence=result.get("confidence", 0.5),
        tags=_to_str_list(result.get("tags", [])),
    )


@router.post("/analysis/name-suggestions")
def analyze_name_suggestions(payload: dict):
    partial_name = payload.get("partial_name", "")
    if not partial_name:
        raise HTTPException(status_code=422, detail="partial_name is required")
    suggestions = generate_name_suggestions(partial_name)
    return {"suggestions": suggestions}


@router.post("/analysis/embeddings")
def generate_embeddings(payload: dict):
    text = payload.get("text", "")
    if not text:
        raise HTTPException(status_code=422, detail="text is required")
    embedding = embed_text(text)
    return {"embedding": embedding, "dimensions": len(embedding)}


@router.post("/analysis/chat")
def chat_with_llm(payload: dict):
    prompt = payload.get("prompt", "")
    system = payload.get("system", "You are an expert OSINT analyst assistant.")
    model = payload.get("model", "").strip()
    if not prompt:
        raise HTTPException(status_code=422, detail="prompt is required")

    kwargs = dict(system=system, prompt=prompt, temperature=payload.get("temperature", 0.3))
    if model:
        kwargs["model"] = model
    response = _chat(**kwargs)
    return {"response": response}


@router.post("/analysis/osint-lookup")
def osint_lookup(payload: dict):
    name = payload.get("name", "").strip()
    context = payload.get("context", "").strip()
    phrase = payload.get("phrase", "").strip()
    links = payload.get("links", "").strip()
    information_wanted = payload.get("information_wanted", "").strip()
    anything_you_have = payload.get("anything_you_have", "").strip()
    model = payload.get("model", "").strip()

    filled = [k for k in ("name", "context", "phrase", "links", "information_wanted", "anything_you_have") if payload.get(k, "").strip()]
    if not filled:
        raise HTTPException(status_code=422, detail="At least one field must be filled")

    user_input = {
        "name": name,
        "context": context,
        "phrase": phrase,
        "links": links,
        "information_wanted": information_wanted,
        "anything_you_have": anything_you_have,
    }

    result = {"input": dict(user_input), "model": model or settings.ollama_model}

    step = lambda s: logger.info("[osint-lookup] %s", s)

    step("Analyzing goal...")
    goal = analyze_goal(name, context, phrase, links, information_wanted, anything_you_have)
    result["goal_analysis"] = goal

    step("Creating investigation plan...")
    plan = create_plan(goal, user_input)
    result["plan"] = [{"id": t["id"], "name": t["name"], "agent": t["agent"]} for t in plan]

    step("Executing plan...")
    executor = TaskExecutor(model=model)
    execution_results = executor.execute(plan)

    step("Compiling results...")
    web_results = []
    social_results = []
    name_results = []
    analysis_text = ""

    for r in execution_results:
        agent = r.get("agent", "")
        if agent == "search_agent":
            web_results.extend(r.get("results", []))
        elif agent == "social_agent":
            social_results = r.get("profiles", [])
        elif agent == "summary_agent":
            analysis_text = r.get("analysis", "")

    raw_copy = [dict(r) for r in web_results[:10]]
    result["raw_web_search"] = raw_copy

    recent_cutoff = (datetime.datetime.utcnow() - datetime.timedelta(days=3)).isoformat()
    filtered = []
    for r in web_results:
        pub = r.get("published", "")
        if pub:
            try:
                dt = email.utils.parsedate_to_datetime(pub).replace(tzinfo=None)
                if dt >= datetime.datetime.utcnow() - datetime.timedelta(days=3):
                    filtered.append(r)
            except Exception:
                filtered.append(r)
        else:
            filtered.append(r)
    result["web_search"] = filtered
    result["social_profiles"] = social_results

    step("Analyzing actual search results...")
    search_text_parts = []
    for w in web_results:
        title = w.get("title", "")
        snippet = w.get("snippet", "")
        if title:
            search_text_parts.append(title)
        if snippet:
            search_text_parts.append(snippet)
    search_corpus = ". ".join(search_text_parts) if search_text_parts else f"{name} {context} {phrase}"

    try:
        entities_results = extract_entities(search_corpus)
        result["entities"] = entities_results
    except Exception as e:
        logger.warning("Entity extraction on search results failed: %s", e)
        result["entities"] = []

    try:
        sentiment_result = analyze_sentiment(search_corpus)
        result["sentiment"] = sentiment_result
    except Exception as e:
        logger.warning("Sentiment analysis on search results failed: %s", e)
        result["sentiment"] = {}

    try:
        classification_result = classify_media_type(search_corpus)
        result["classification"] = classification_result
    except Exception as e:
        logger.warning("Classification on search results failed: %s", e)
        result["classification"] = {}

    try:
        inconsistencies = detect_inconsistencies(search_corpus)
        result["inconsistencies"] = inconsistencies
    except Exception as e:
        logger.warning("Inconsistency detection on search results failed: %s", e)
        result["inconsistencies"] = []

    if name:
        try:
            name_results = generate_name_suggestions(name)
            result["name_suggestions"] = name_results
        except Exception as e:
            logger.warning("Name suggestions failed: %s", e)
            result["name_suggestions"] = []

    step("Collecting OSINT tool results from investigation...")
    from app.osint_core import analyze_osint_data_ollama

    osint_maigret_results = []
    osint_email_results = []
    for r in execution_results:
        if r.get("agent") == "social_agent":
            mr = r.get("maigret_results", {})
            if isinstance(mr, dict):
                osint_maigret_results.extend(mr.get("username_searches", []))
                osint_email_results.extend(mr.get("email_searches", []))
            break
    result["maigret_searches"] = osint_maigret_results
    result["holehe_searches"] = osint_email_results

    step("Generating intelligence report from all findings...")
    web_lines = []
    for w in web_results[:15]:
        title = w.get("title", "")
        src = w.get("source", "")
        url = w.get("url", "")
        pub = w.get("published", "")
        tag = f" ({pub})" if pub else ""
        web_lines.append(f"  [{src}]{tag} {title}")
        if url:
            web_lines.append(f"    {url}")

    social_lines = []
    for p in social_results:
        if p.get("exists"):
            social_lines.append(f"  [{p['platform']}] {p['url']}")

    maigret_lines = []
    for mr in osint_maigret_results:
        uname = mr.get("username", "?")
        for site, info in mr.get("profiles", {}).items():
            maigret_lines.append(f"  [{info.get('site_name', site)}] {info.get('url', '')}")

    holehe_lines = []
    for hr in osint_email_results:
        email = hr.get("email", "?")
        for site, info in hr.get("registrations", {}).items():
            if info.get("exists"):
                holehe_lines.append(f"  [{site}] {email}")

    try:
        today = datetime.date.today().isoformat()
        prompt = (
            f"OSINT investigation report for: {name or 'unknown subject'}\n"
            f"Today's date: {today}\n"
            f"User context: {context}\n"
            f"Information wanted: {information_wanted}\n\n"
            f"--- WEB SEARCH RESULTS ({len(web_results)} total) ---\n"
            + "\n".join(web_lines[:30]) + "\n\n"
            f"--- SOCIAL PROFILES FOUND ({len(social_lines)} existing) ---\n"
            + "\n".join(social_lines[:20]) + "\n\n"
            f"--- USERNAME SCANS (Maigret - {len(osint_maigret_results)} usernames) ---\n"
            + "\n".join(maigret_lines[:30]) + "\n\n"
            f"--- EMAIL REGISTRATIONS (Holehe - {len(osint_email_results)} emails) ---\n"
            + "\n".join(holehe_lines[:20]) + "\n\n"
            "Based on ALL the above findings, provide:\n"
            "1. Who/what this subject appears to be\n"
            "2. Digital footprint and key evidence found (cite specific sources)\n"
            "3. Red flags or contradictions\n"
            "4. Recommended next investigation steps"
        )
        chat_kwargs = dict(system=f"You are a senior OSINT analyst. Today is {today}. Write concise, evidence-based intelligence reports. Only reference information that appears in the findings above.", prompt=prompt)
        if model:
            chat_kwargs["model"] = model
        if analysis_text:
            result["llm_analysis"] = analysis_text
        else:
            result["llm_analysis"] = _chat(**chat_kwargs)
    except Exception as e:
        logger.warning("LLM analysis failed: %s", e)
        result["llm_analysis"] = ""

    result["lookup_id"] = ""
    try:
        result["lookup_id"] = save_lookup(result)
    except Exception as e:
        logger.warning("Failed to save lookup: %s", e)

    return result
