import asyncio
import logging
import re
import sys

from app.llm import _chat

logger = logging.getLogger(__name__)

sys.path.insert(0, "/mnt/d/BACKUP/KAAL (ASE)/osint_tools/maigret")

MAIGRET_DB_PATH = "/mnt/d/BACKUP/KAAL (ASE)/osint_tools/maigret/maigret/resources/data.json"

_maigret_db = None

def _get_maigret_db():
    global _maigret_db
    if _maigret_db is None:
        from maigret.maigret import MaigretDatabase
        _maigret_db = MaigretDatabase()
        _maigret_db.load_from_path(MAIGRET_DB_PATH)
    return _maigret_db


def _extract_emails(text: str) -> list[str]:
    return list(set(re.findall(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", text)))


def _generate_usernames(name: str, context: str = "") -> list[str]:
    usernames = set()
    name = name.strip()
    if not name:
        return []

    n = name.lower().strip()
    usernames.add(n.replace(" ", ""))
    usernames.add(n.replace(" ", "."))
    usernames.add(n.replace(" ", "_"))
    usernames.add(n.replace(" ", "-"))
    np = n.split()
    if len(np) >= 2:
        usernames.add(f"{np[0]}{np[-1]}")
        usernames.add(f"{np[0]}.{np[-1]}")
        usernames.add(f"{np[0]}_{np[-1]}")
        usernames.add(f"{np[0]}-{np[-1]}")
        usernames.add(np[0])
        usernames.add(np[-1])

    return [u for u in usernames if re.match(r"^[a-zA-Z0-9._-]{3,}$", u)]


def search_username_maigret(username: str, timeout: int = 10, max_sites: int = 200) -> dict:
    import logging as py_logging
    from maigret.maigret import maigret

    py_logging.getLogger().setLevel(py_logging.WARNING)

    db = _get_maigret_db()
    all_sites = db.ranked_sites_dict()
    site_dict = dict(list(all_sites.items())[:max_sites])
    logger.info("Maigret searching %s across top %d sites...", username, len(site_dict))

    results = asyncio.run(maigret(
        username=username,
        site_dict=site_dict,
        logger=py_logging.getLogger(),
        timeout=timeout,
        max_connections=30,
        retries=0,
    ))

    found = {}
    for site, result in results.items():
        status = result.get("status")
        status_str = str(status) if status else ""
        http_status = result.get("http_status")
        if status_str == "Claimed":
            found[site] = {
                "username": result.get("username", ""),
                "url": result.get("url_user", result.get("url_probe", "")),
                "status": status_str,
                "http_status": http_status,
                "site_name": str(result.get("site", site)).split(" (")[0] if " (" in str(result.get("site", site)) else str(result.get("site", site)),
            }

    return {
        "username": username,
        "total_checked": len(results),
        "profiles_found": len(found),
        "profiles": found,
    }


def search_email_holehe(email: str, timeout: int = 15) -> dict:
    try:
        from holehe.core import get_functions, import_submodules, launch_module

        modules = import_submodules("holehe.modules")
        funcs = get_functions(modules)

        async def _check_all():
            sem = asyncio.Semaphore(20)
            async def _check_one(func):
                async with sem:
                    try:
                        return func.__name__, await launch_module(func, email, max(1, timeout // 20))
                    except Exception:
                        return func.__name__, None
            tasks = [_check_one(f) for f in funcs]
            raw = await asyncio.gather(*tasks, return_exceptions=True)
            results = {}
            for item in raw:
                if isinstance(item, tuple):
                    name, result = item
                    if result:
                        results[name] = {
                            "exists": result.get("exists", False),
                            "email": result.get("email", ""),
                            "rateLimit": result.get("rateLimit", False),
                        }
            return results

        results = asyncio.run(_check_all())
        found = {k: v for k, v in results.items() if v.get("exists")}
        return {
            "email": email,
            "total_checked": len(results),
            "registrations_found": len(found),
            "registrations": found,
        }
    except Exception as e:
        logger.warning("Holehe search failed: %s", e)
        return {"email": email, "error": str(e), "registrations_found": 0, "registrations": {}}


def analyze_osint_data_ollama(
    name: str,
    maigret_results: list[dict],
    holehe_results: list[dict],
    search_results: list[dict],
    context: str = "",
    model: str = "",
) -> dict:
    maigret_summary = []
    for r in maigret_results:
        profiles = r.get("profiles", {})
        if profiles:
            sites = [f"{v.get('site_name', k)}({v.get('url', '')})" for k, v in profiles.items()]
            maigret_summary.append(f"Username '{r['username']}': {len(profiles)} profiles - {', '.join(sites[:10])}")

    email_summary = []
    for r in holehe_results:
        regs = r.get("registrations", {})
        if regs:
            sites = [k for k, v in regs.items() if v.get("exists")]
            email_summary.append(f"Email '{r['email']}': registered on {', '.join(sites[:10])}")

    web_summary = []
    for r in search_results[:10]:
        title = r.get("title", "")
        snippet = r.get("snippet", "")
        url = r.get("url", "")
        web_summary.append(f"- {title}: {snippet[:200]} [{url}]")

    findings_parts = []
    if maigret_summary:
        findings_parts.append("=== SOCIAL MEDIA PROFILES ===" + "\n".join(maigret_summary))
    if email_summary:
        findings_parts.append("=== EMAIL REGISTRATIONS ===" + "\n".join(email_summary))
    if web_summary:
        findings_parts.append("=== WEB SEARCH RESULTS ===" + "\n".join(web_summary))

    findings_text = "\n\n".join(findings_parts) if findings_parts else f"No OSINT data found for {name}."

    prompt = (
        f"OSINT investigation findings for: {name}\n"
        f"Context: {context}\n\n"
        f"Raw OSINT data:\n{findings_text}\n\n"
        "Provide a structured intelligence report:\n"
        "1. Subject summary - who this appears to be\n"
        "2. Digital footprint discovered (social profiles, email registrations, web presence)\n"
        "3. Key findings and evidence of identity/location/associations\n"
        "4. Red flags, inconsistencies, or contradictions\n"
        "5. Recommended next investigation steps\n\n"
        "Be specific and reference actual data from the findings."
    )

    kwargs = {}
    if model:
        kwargs["model"] = model

    analysis = _chat(
        system="You are a senior OSINT analyst. Write concise, evidence-based intelligence reports. Cite specific findings.",
        prompt=prompt,
        **kwargs,
    )

    return {
        "analysis": analysis,
        "maigret_results": maigret_results,
        "holehe_results": holehe_results,
        "search_results_count": len(search_results),
    }

