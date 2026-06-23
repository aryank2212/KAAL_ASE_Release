import json
import logging
import re
from typing import Any

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

OLLAMA_BASE = settings.ollama_base_url.rstrip("/")
OLLAMA_MODEL = settings.ollama_model
OLLAMA_EMBED_MODEL = settings.ollama_embed_model


def _chat(
    system: str,
    prompt: str,
    model: str = OLLAMA_MODEL,
    temperature: float = 0.1,
) -> str:
    resp = httpx.post(
        f"{OLLAMA_BASE}/api/chat",
        json={
            "model": model,
            "stream": False,
            "temperature": temperature,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
        },
        timeout=120,
    )
    resp.raise_for_status()
    return resp.json()["message"]["content"]


def _extract_json(text: str) -> str:
    text = text.strip()
    if "```" in text:
        parts = text.split("```")
        for i, part in enumerate(parts):
            if i % 2 == 1:
                candidate = part.strip()
                if candidate.startswith("json"):
                    candidate = candidate[4:].strip()
                if candidate:
                    return candidate
        for part in parts:
            candidate = part.strip()
            if candidate.startswith("{") or candidate.startswith("["):
                return candidate
    brace_start = text.find("{")
    bracket_start = text.find("[")
    start = -1
    if brace_start >= 0 and bracket_start >= 0:
        start = min(brace_start, bracket_start)
    elif brace_start >= 0:
        start = brace_start
    elif bracket_start >= 0:
        start = bracket_start
    if start >= 0:
        text = text[start:]
        depth = 0
        end = -1
        for i, ch in enumerate(text):
            if ch in "{[":
                depth += 1
            elif ch in "}]":
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
        if end > 0:
            text = text[:end]
    return text.strip()


def _clean_json(text: str) -> str:
    text = text.strip()
    text = re.sub(r",\s*([\]}])", r"\1", text)

    if text.startswith("{") and not text.startswith("[") and text.count("{") > 1:
        last_close = text.rfind("}")
        if last_close >= 0:
            inner = text[:last_close+1]
            if inner.startswith("{") and inner.endswith("}"):
                text = "[" + text + "]"
                text = text.replace("}{", "},{")

    return text


def _json_chat(
    system: str,
    prompt: str,
    model: str = OLLAMA_MODEL,
) -> Any:
    system_prompt = system + (
        "\n\nIMPORTANT: Your entire response must be valid JSON. "
        "Do NOT use markdown, code fences, bullet points, or any formatting. "
        "Only output the raw JSON object."
    )
    text = _chat(
        system=system_prompt,
        prompt=prompt,
        model=model,
        temperature=0.05,
    )
    extracted = _extract_json(text)
    last_error = None
    parsed = None
    for attempt in [extracted, _clean_json(extracted), extracted + "}", extracted.replace("'", '"')]:
        try:
            parsed = json.loads(attempt)
            break
        except json.JSONDecodeError as e:
            last_error = e
            continue

    if parsed is not None:
        if isinstance(parsed, dict) and "$schema" in parsed:
            items = parsed.get("items") or parsed.get("properties", {})
            if items:
                return {"_raw_text": json.dumps(items, indent=2)[:1000]}
            return {"_raw_text": json.dumps(parsed, indent=2)[:1000]}
        return parsed

    logger.warning("JSON parse failed, extracting from raw text. error=%s", last_error)

    if isinstance(text, str) and text.strip():
        return {"_raw_text": text.strip()[:1000]}
    return {}


def summarize(text: str, max_length: int = 200, model: str = "") -> dict[str, Any]:
    system = "You are an expert OSINT analyst. Summarize the following evidence text concisely."
    prompt = (
        f"Summarize this evidence in at most {max_length} words. "
        f"Return a JSON object with keys: title (string), summary (string), key_facts (list of strings).\n\n{text}"
    )
    kwargs = {}
    if model:
        kwargs["model"] = model
    result = _json_chat(system, prompt, **kwargs)
    if "_raw_text" in result:
        raw = result["_raw_text"]
        lines = [l.strip() for l in raw.replace("**", "").split("\n") if l.strip()]
        title = lines[0] if lines else "Summary"
        body = " ".join(l for l in lines[1:] if not l.startswith("-") and not l.startswith("*"))
        facts = [l.lstrip("-* ") for l in lines if l.startswith("-") or l.startswith("*")]
        return {"title": title, "summary": body[:500], "key_facts": facts or ["See summary"]}
    return result


def _maybe_parse_entities(entities: list) -> list[dict]:
    result = []
    for item in entities:
        if isinstance(item, str):
            try:
                parsed = json.loads(item)
                if isinstance(parsed, dict):
                    result.append(parsed)
                    continue
            except json.JSONDecodeError:
                pass
            result.append({"type": "unknown", "name": item, "confidence": 0.5})
        elif isinstance(item, dict):
            if "name" not in item and "value" in item:
                item["name"] = str(item.pop("value", ""))
            if "number" in item and "name" not in item:
                item["name"] = str(item.pop("number", ""))
            result.append(item)
    return result if result else entities


def extract_entities(text: str, model: str = "") -> list[dict[str, Any]]:
    system = (
        "You are an expert OSINT entity extractor. Extract all named entities from the text. "
        "Entity types: person, organization, location, email, phone, url, date, event, identifier."
    )
    prompt = (
        "Extract entities as a JSON array of objects. "
        "Each object must have: type (string), name (string), confidence (number 0-1). "
        "Optionally include context (string).\n\n"
        f"{text}"
    )
    kwargs = {}
    if model:
        kwargs["model"] = model
    result = _json_chat(system, prompt, **kwargs)
    if "_raw_text" in result:
        return []
    if isinstance(result, list):
        return _maybe_parse_entities(result)
    if isinstance(result, dict):
        for key in ("entities", "results", "entity_list", "data"):
            val = result.get(key)
            if isinstance(val, list):
                return _maybe_parse_entities(val)
        if any(k in result for k in ("type", "name")):
            return [result]
    return []


def _deep_get(d: dict, *keys: str) -> Any:
    for key in keys:
        if isinstance(d, dict) and key in d:
            d = d[key]
        else:
            return None
    return d


def detect_inconsistencies(text: str, model: str = "") -> list[dict[str, Any]]:
    system = (
        "You are an expert OSINT analyst specializing in detecting inconsistencies, "
        "contradictions, and suspicious claims in intelligence data."
    )
    prompt = (
        "Analyze the following text for inconsistencies, contradictions, "
        "or suspicious claims. Return a JSON array of objects. "
        "Each object must have: description (string), severity (low/medium/high), "
        "text_snippet (string).\n\n"
        f"{text}"
    )
    kwargs = {}
    if model:
        kwargs["model"] = model
    result = _json_chat(system, prompt, **kwargs)
    if "_raw_text" in result:
        return []
    if isinstance(result, list):
        return result
    if isinstance(result, dict):
        for key in ("inconsistencies", "issues", "results"):
            val = result.get(key)
            if isinstance(val, list):
                return val
        for key in ("analysis", "data"):
            val = result.get(key)
            if isinstance(val, dict):
                for subkey in ("inconsistencies", "issues", "results"):
                    subval = val.get(subkey)
                    if isinstance(subval, list):
                        return subval
        if "description" in result or "severity" in result or "text_snippet" in result:
            return [result]
        return []
    return []


def generate_leads(context: dict[str, Any]) -> list[dict[str, Any]]:
    system = (
        "You are an expert OSINT analyst generating investigation leads. "
        "Based on the case context, propose actionable next steps."
    )
    prompt = (
        "Generate 3-5 investigation leads based on this context. "
        "Return a JSON array of objects. "
        "Each object must have: title (string), description (string), priority (low/medium/high), "
        "rationale (string).\n\n"
        f"{json.dumps(context, indent=2)}"
    )
    result = _json_chat(system, prompt)
    if "_raw_text" in result:
        return []
    if isinstance(result, list):
        return result
    if isinstance(result, dict):
        return result.get("leads", result.get("results", []))
    return []


def embed_text(text: str) -> list[float]:
    resp = httpx.post(
        f"{OLLAMA_BASE}/api/embeddings",
        json={"model": OLLAMA_EMBED_MODEL, "prompt": text},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["embedding"]


def _extract_suggestions(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, list):
        result = []
        for item in data:
            if isinstance(item, dict):
                if "suggested_name" in item:
                    result.append(item)
                elif "name" in item:
                    result.append({"suggested_name": item["name"], "type": item.get("type", "alias"), "rationale": item.get("rationale", "")})
                elif "value" in item:
                    result.append({"suggested_name": item["value"], "type": "alias", "rationale": item.get("description", "")})
        if result:
            return result[:8]
    if isinstance(data, dict):
        if "suggested_name" in data:
            names = data["suggested_name"]
            if isinstance(names, list):
                return [{"suggested_name": n, "type": data.get("type", "alias"), "rationale": data.get("rationale", "")} for n in names]
            return [{"suggested_name": str(names), "type": data.get("type", "alias"), "rationale": data.get("rationale", "")}]
        for key, val in data.items():
            if isinstance(val, dict) and "suggested_name" in val:
                return _extract_suggestions(val)
            if isinstance(val, list):
                for v in val:
                    if isinstance(v, dict) and "suggested_name" in v:
                        return _extract_suggestions(val)
    return []


def _parse_name_lines(text: str) -> list[dict[str, Any]]:
    text_json = _extract_json(text)
    try:
        parsed = json.loads(text_json)
        extracted = _extract_suggestions(parsed)
        if extracted:
            return extracted
    except json.JSONDecodeError:
        pass
    try:
        parsed = json.loads(_clean_json(text_json))
        extracted = _extract_suggestions(parsed)
        if extracted:
            return extracted
    except json.JSONDecodeError:
        pass

    suggestions = []
    for line in text.replace("\r", "").split("\n"):
        line = line.strip().lstrip("-*•0123456789. ")
        if not line or line in ['{', '}', '[', ']', '', ',']:
            continue
        parts = [p.strip().strip('"').strip("'") for p in line.split(",")]
        name = parts[0] if len(parts) > 0 else line
        ntype = "alias"
        rationale = ""
        if len(parts) > 1:
            if parts[1].lower() in ("full_name", "alias", "nickname"):
                ntype = parts[1].lower()
            else:
                rationale = parts[1]
        if len(parts) > 2:
            rationale = parts[2]
        name = name.strip().lstrip('{').strip('"').strip("'")
        if name and len(name) > 1 and name not in ('{', '}', '},'):
            suggestions.append({"suggested_name": name, "type": ntype, "rationale": rationale})
    return suggestions


def generate_name_suggestions(partial_name: str, model: str = "") -> list[dict[str, Any]]:
    system = (
        "You are an expert OSINT analyst. Given a partial name, suggest possible full names "
        "and known aliases that an investigator should consider."
    )
    prompt = (
        f"Based on the partial name '{partial_name}', suggest 3-5 possible full name variations "
        "and aliases. Return a JSON array of objects. "
        "Each object must have: suggested_name (string), type (full_name/alias/nickname), rationale (string).\n\n"
    )
    kwargs = {}
    if model:
        kwargs["model"] = model
    result = _json_chat(system, prompt, **kwargs)
    if "_raw_text" in result:
        return _parse_name_lines(result["_raw_text"])
    if isinstance(result, list):
        return result
    if isinstance(result, dict):
        extracted = _extract_suggestions(result)
        if extracted:
            return extracted
    return []


def analyze_sentiment(text: str, model: str = "") -> dict[str, Any]:
    system = (
        "You are an expert text analyst. Analyze the sentiment and emotional tone of the text."
    )
    prompt = (
        "Analyze the sentiment of this text. Return a JSON object with keys: "
        "sentiment (positive/negative/neutral/mixed), confidence (number 0-1), "
        "key_emotional_indicators (list of strings).\n\n"
        f"{text}"
    )
    kwargs = {}
    if model:
        kwargs["model"] = model
    result = _json_chat(system, prompt, **kwargs)
    if "_raw_text" in result:
        raw = result["_raw_text"].lower()
        if any(w in raw for w in ["positive", "good", "success", "safe"]):
            return {"sentiment": "positive", "confidence": 0.6, "key_emotional_indicators": ["positive tone detected"]}
        if any(w in raw for w in ["negative", "bad", "threat", "danger", "hostil"]):
            return {"sentiment": "negative", "confidence": 0.6, "key_emotional_indicators": ["negative tone detected"]}
        return {"sentiment": "neutral", "confidence": 0.5, "key_emotional_indicators": ["neutral tone"]}
    return result


def classify_media_type(text: str, model: str = "") -> dict[str, Any]:
    system = (
        "You are an expert OSINT evidence classifier. Given text extracted from a document "
        "or message, classify the type of content."
    )
    prompt = (
        "Classify this content. Return a JSON object with keys: "
        "category (string), subcategory (string), confidence (number 0-1), "
        "tags (list of strings).\n\n"
        f"{text}"
    )
    kwargs = {}
    if model:
        kwargs["model"] = model
    result = _json_chat(system, prompt, **kwargs)
    if "_raw_text" in result:
        return {"category": "document", "subcategory": "text", "confidence": 0.5, "tags": ["uncategorized"]}
    return result
