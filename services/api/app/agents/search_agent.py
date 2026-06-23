from app.agents.base import BaseAgent
from app.search_web import search_recent, search_web, fetch_page_text
from app.social_search import search_social_profiles
from app.osint_core import search_username_maigret, search_email_holehe, _extract_emails


class SearchAgent(BaseAgent):
    def execute(self, task: dict) -> dict:
        query = task.get("query", task.get("description", ""))
        max_results = task.get("max_results", 10)
        results = search_recent(query, max_results=max_results)
        scraped = []
        for r in results[:3]:
            url = r.get("url", "")
            if url:
                page = fetch_page_text(url)
                if page:
                    scraped.append(page)
        return {
            "status": "completed",
            "task_id": task["id"],
            "agent": "search_agent",
            "query": query,
            "results": results,
            "scraped_pages": scraped,
        }


class SocialSearchAgent(BaseAgent):
    def execute(self, task: dict) -> dict:
        name = task.get("subject_name") or task.get("name", "")
        phrase = task.get("phrase", "")
        links = task.get("links", "")

        profiles = search_social_profiles(name, phrase, links)

        emails = _extract_emails(f"{name} {phrase} {links}")
        holehe_results = []
        for email in emails[:3]:
            try:
                hr = search_email_holehe(email, timeout=10)
                holehe_results.append(hr)
            except Exception as e:
                holehe_results.append({"email": email, "error": str(e)})

        maigret_results = {"username_searches": [], "email_searches": holehe_results}
        seen_usernames = set()
        for p in profiles:
            u = p.get("username", "")
            if u and u not in seen_usernames:
                seen_usernames.add(u)
                try:
                    mr = search_username_maigret(u, timeout=8)
                    maigret_results["username_searches"].append(mr)
                except Exception:
                    pass

        return {
            "status": "completed",
            "task_id": task["id"],
            "agent": "social_agent",
            "profiles": profiles,
            "total_found": len(profiles),
            "existing": sum(1 for p in profiles if p.get("exists")),
            "maigret_results": maigret_results,
            "holehe_results": holehe_results,
        }
