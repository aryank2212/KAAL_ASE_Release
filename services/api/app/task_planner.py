import json
import logging

from app.llm import _chat

logger = logging.getLogger(__name__)


def analyze_goal(
    name: str,
    context: str,
    phrase: str,
    links: str,
    information_wanted: str,
    anything_you_have: str,
) -> dict:
    user_input = (
        f"Name/subject: {name or 'not provided'}\n"
        f"Background context: {context or 'not provided'}\n"
        f"Phrase/quote: {phrase or 'not provided'}\n"
        f"Known links/URLs: {links or 'not provided'}\n"
        f"What to find out: {information_wanted or 'not provided'}\n"
        f"Additional info: {anything_you_have or 'not provided'}"
    )

    prompt = (
        "You are a Goal Analyzer for an OSINT investigation system.\n\n"
        "Analyze the user's input and decompose it into concrete investigative objectives.\n\n"
        "Rules:\n"
        "- Identify EXACTLY what the user wants (specific data, people, events)\n"
        "- Break compound requests into separate deliverables\n"
        "- List SPECIFIC search queries that would actually find relevant data (max 3 queries)\n"
        "- Each query should be a complete, targeted search string (e.g. 'Elon Musk biography companies' not just 'Elon Musk')\n"
        "- Keep queries general enough to return useful results\n\n"
        f"User input:\n{user_input}\n\n"
        "Return ONLY valid JSON with this schema:\n"
        "{\n"
        '  "goal": "single sentence summarizing overall objective",\n'
        '  "deliverables": ["list of specific things user wants (be precise)"],\n'
        '  "search_queries": ["max 3 specific search queries to run"],\n'
        '  "requires_social_search": true/false,\n'
        '  "requires_name_analysis": true/false,\n'
        '  "requires_entity_extraction": true/false,\n'
        '  "requires_sentiment": true/false,\n'
        '  "success_criteria": ["how to know we succeeded"]\n'
        "}"
    )

    try:
        raw = _chat(
            system="You are a precise goal analyzer. Your job is to understand exactly what the user wants and break it into concrete, actionable objectives.",
            prompt=prompt,
            temperature=0.1,
        )
        result = _parse_json(raw, {
            "goal": "",
            "deliverables": [],
            "search_queries": [],
            "requires_social_search": bool(name),
            "requires_name_analysis": bool(name),
            "requires_entity_extraction": True,
            "requires_sentiment": True,
            "success_criteria": [],
        })
        if not result.get("search_queries") and (name or phrase):
            result["search_queries"] = [f"{name} {phrase}".strip() or name or context[:100]]
        return result
    except Exception as e:
        logger.warning("Goal analysis failed: %s", e)
        return {
            "goal": "General OSINT investigation",
            "deliverables": ["Gather intelligence on subject"],
            "search_queries": [f"{name} {phrase}" if name or phrase else context[:100]],
            "requires_social_search": True,
            "requires_name_analysis": bool(name),
            "requires_entity_extraction": True,
            "requires_sentiment": True,
            "success_criteria": ["Information gathered"],
        }


def create_plan(goal_analysis: dict, user_input: dict) -> list[dict]:
    tasks = []
    task_id = 0

    def next_id():
        nonlocal task_id
        task_id += 1
        return f"TASK_{task_id:03d}"

    name = user_input.get("name", "").strip()
    context = user_input.get("context", "").strip()
    phrase = user_input.get("phrase", "").strip()
    links = user_input.get("links", "").strip()
    info_wanted = user_input.get("information_wanted", "").strip()
    extra = user_input.get("anything_you_have", "").strip()

    queries = goal_analysis.get("search_queries", [])
    if not queries and (name or phrase):
        queries = [f"{name} {phrase}".strip() or name or phrase]

    for q in queries[:3]:
        tasks.append({
            "id": next_id(),
            "name": f"Web search: {q[:60]}",
            "description": q,
            "agent": "search_agent",
            "dependencies": [],
            "max_results": 5,
        })

    if (goal_analysis.get("requires_social_search", False) or bool(name)) and (name or phrase):
        all_text = f"{name} {phrase} {links}".strip()
        tasks.append({
            "id": next_id(),
            "name": "Social media profile discovery",
            "description": all_text,
            "agent": "social_agent",
            "dependencies": [],
            "subject_name": name,
            "phrase": phrase,
            "links": links,
        })

    if goal_analysis.get("requires_name_analysis", False) and name:
        tasks.append({
            "id": next_id(),
            "name": "Name variations analysis",
            "description": f"Generate name variations for: {name}",
            "agent": "analyze_agent",
            "operation": "names",
            "dependencies": [],
            "subject_name": name,
        })

    all_text = f"Name: {name}. Context: {context}. Phrase: {phrase}. Links: {links}. Info wanted: {info_wanted}. Additional: {extra}."

    if goal_analysis.get("requires_entity_extraction", True):
        tasks.append({
            "id": next_id(),
            "name": "Entity extraction",
            "description": all_text,
            "agent": "analyze_agent",
            "operation": "entities",
            "dependencies": [],
        })

    if goal_analysis.get("requires_sentiment", True):
        tasks.append({
            "id": next_id(),
            "name": "Sentiment & classification",
            "description": all_text,
            "agent": "analyze_agent",
            "operation": "sentiment+classify",
            "dependencies": [],
        })

    tasks.append({
        "id": next_id(),
        "name": "Inconsistency detection",
        "description": all_text,
        "agent": "analyze_agent",
        "operation": "inconsistencies",
        "dependencies": [],
    })

    search_task_ids = [t["id"] for t in tasks if t["agent"] == "search_agent"]
    social_task_ids = [t["id"] for t in tasks if t["agent"] == "social_agent"]

    tasks.append({
        "id": next_id(),
        "name": "Final intelligence summary",
        "description": "Compile all findings into a structured OSINT report",
        "agent": "summary_agent",
        "dependencies": search_task_ids + social_task_ids,
        "context": all_text,
        "subject_name": name or context[:50] or "unknown subject",
    })

    return tasks


def _parse_json(raw: str, default: dict) -> dict:
    text = raw.strip()
    for marker in ("```json", "```", "``"):
        if marker in text:
            parts = text.split(marker)
            if len(parts) >= 2:
                text = parts[1]
            break
    text = text.strip()
    try:
        start = text.index("{")
        end = text.rindex("}") + 1
        candidate = text[start:end]
        return json.loads(candidate)
    except (ValueError, json.JSONDecodeError):
        pass
    try:
        import re as _re
        matches = _re.findall(r"\{[^{}]*\}", text)
        if matches:
            for m in reversed(matches):
                try:
                    return json.loads(m)
                except json.JSONDecodeError:
                    continue
    except Exception:
        pass
    logger.warning("Failed to parse JSON from: %s", raw[:200])
    return default
