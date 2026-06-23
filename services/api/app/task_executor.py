import logging

from app.agents.search_agent import SearchAgent, SocialSearchAgent
from app.agents.analyze_agent import AnalyzeAgent, SummaryAgent

logger = logging.getLogger(__name__)


class TaskExecutor:
    def __init__(self, model: str = ""):
        self.model = model
        self.agents = {
            "search_agent": SearchAgent(),
            "social_agent": SocialSearchAgent(),
            "analyze_agent": AnalyzeAgent(),
            "summary_agent": SummaryAgent(),
        }

    def execute(self, plan: list[dict]) -> list[dict]:
        completed: dict[str, dict] = {}
        results: list[dict] = []
        accumulated_findings: list[str] = []

        for task in plan:
            task["model"] = self.model
            deps = task.get("dependencies", [])
            for dep_id in deps:
                if dep_id not in completed:
                    logger.warning("Dependency %s not completed for %s", dep_id, task["id"])

            agent_name = task.get("agent", "analyze_agent")

            if agent_name == "summary_agent":
                findings = "\n".join(accumulated_findings) if accumulated_findings else "No findings from prior tasks."
                task["findings"] = findings

            agent = self.agents.get(agent_name)
            if not agent:
                logger.error("Unknown agent: %s", agent_name)
                err = {"status": "failed", "task_id": task["id"], "agent": agent_name, "error": f"Unknown agent: {agent_name}"}
                completed[task["id"]] = err
                results.append(err)
                continue

            logger.info("Executing %s with agent %s...", task["id"], agent_name)
            try:
                result = agent.execute(task)
                completed[task["id"]] = result
                results.append(result)
                accumulated_findings.append(self._summarize_result(result))
                logger.info("  %s completed", task["id"])
            except Exception as e:
                logger.error("  %s failed: %s", task["id"], e)
                err_result = {"status": "failed", "task_id": task["id"], "agent": agent_name, "error": str(e)}
                completed[task["id"]] = err_result
                results.append(err_result)
                accumulated_findings.append(f"[{task['id']}] FAILED: {e}")

        return results

    def _summarize_result(self, result: dict) -> str:
        agent = result.get("agent", "")
        tid = result.get("task_id", "?")
        if agent == "search_agent":
            pages = result.get("results", [])
            lines = [f"[{tid}] Web search for '{result.get('query', '?')}' found {len(pages)} results:"]
            for p in pages[:3]:
                lines.append(f"  - {p.get('title', '?')}: {p.get('url', '')[:100]}")
            return "\n".join(lines)
        elif agent == "social_agent":
            profiles = result.get("profiles", [])
            found = sum(1 for p in profiles if p.get("exists"))
            return f"[{tid}] Social media: {found} profiles found out of {len(profiles)} checked"
        elif agent == "analyze_agent":
            parts = []
            ents = result.get("entities", [])
            if ents:
                parts.append(f"entities: {len(ents)}")
            sent = result.get("sentiment", {})
            if sent:
                parts.append(f"sentiment: {sent.get('sentiment', '?')}")
            cls = result.get("classification", {})
            if cls:
                parts.append(f"class: {cls.get('category', '?')}")
            inc = result.get("inconsistencies", [])
            if inc:
                parts.append(f"inconsistencies: {len(inc)}")
            names = result.get("name_suggestions", [])
            if names:
                parts.append(f"name variants: {len(names)}")
            return f"[{tid}] Analysis: {', '.join(parts) if parts else 'completed'}"
        elif agent == "summary_agent":
            analysis = result.get("analysis", "")
            return f"[{tid}] Summary generated ({len(analysis)} chars)"
        return f"[{tid}] {result.get('status', 'completed')}"
