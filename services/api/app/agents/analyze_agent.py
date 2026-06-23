import datetime

from app.agents.base import BaseAgent
from app.llm import _chat, extract_entities, analyze_sentiment, classify_media_type, detect_inconsistencies, generate_name_suggestions


class AnalyzeAgent(BaseAgent):
    def execute(self, task: dict) -> dict:
        text = task.get("text", task.get("description", ""))
        operation = task.get("operation", "analyze")
        model = task.get("model", "")
        results: dict = {}
        ops = operation.split("+") if operation != "all" else ["all"]

        if "entities" in ops or "all" in ops:
            try:
                results["entities"] = extract_entities(text, model=model)
            except Exception as e:
                results["entities_error"] = str(e)

        if "sentiment" in ops or "all" in ops:
            try:
                results["sentiment"] = analyze_sentiment(text, model=model)
            except Exception as e:
                results["sentiment_error"] = str(e)

        if "classify" in ops or "all" in ops:
            try:
                results["classification"] = classify_media_type(text, model=model)
            except Exception as e:
                results["classification_error"] = str(e)

        if "inconsistencies" in ops or "all" in ops:
            try:
                results["inconsistencies"] = detect_inconsistencies(text, model=model)
            except Exception as e:
                results["inconsistencies_error"] = str(e)

        if "names" in ops or "all" in ops:
            name = task.get("name") or task.get("subject_name", "")
            if name:
                try:
                    results["name_suggestions"] = generate_name_suggestions(name, model=model)
                except Exception as e:
                    results["name_suggestions_error"] = str(e)

        return {
            "status": "completed",
            "task_id": task["id"],
            "agent": "analyze_agent",
            "operation": operation,
            **results,
        }


class SummaryAgent(BaseAgent):
    def execute(self, task: dict) -> dict:
        context = task.get("context", "")
        findings = task.get("findings", "")
        name = task.get("subject_name") or task.get("name", "unknown subject")
        model = task.get("model", "")
        today = datetime.date.today().isoformat()
        prompt = (
            f"OSINT intelligence summary for: {name}\n"
            f"Today's date: {today}\n\n"
            f"Context from user:\n{context}\n\n"
            f"Raw findings from investigation:\n{findings}\n\n"
            "Provide a structured intelligence report (today is "
            + today
            + "):\n"
            "1. Who/what this subject appears to be\n"
            "2. Digital footprint found\n"
            "3. Key findings and evidence\n"
            "4. Any red flags or contradictions\n"
            "5. Recommended next investigation steps\n\n"
            "Be specific. Reference actual data from the findings."
        )
        kwargs = {}
        if model:
            kwargs["model"] = model
        analysis = _chat(
            system=f"You are a senior OSINT analyst. Today is {today}. Write concise, evidence-based intelligence reports. Always reference the correct current date.",
            prompt=prompt,
            **kwargs,
        )
        return {
            "status": "completed",
            "task_id": task["id"],
            "agent": "summary_agent",
            "analysis": analysis,
        }
