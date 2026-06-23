import logging
import re

from app.osint_core import search_username_maigret, _generate_usernames

logger = logging.getLogger(__name__)


def _extract_urls_from_text(text: str) -> list[str]:
    return re.findall(r"https?://[^\s,)]+", text)


def search_social_profiles(name: str, phrase: str = "", extra_links: str = "") -> list[dict]:
    usernames = _generate_usernames(name, phrase)
    profiles = []

    for username in usernames[:3]:
        try:
            result = search_username_maigret(username, timeout=8)
            found_profiles = result.get("profiles", {})
            for site, info in found_profiles.items():
                profiles.append({
                    "platform": info.get("site_name", site),
                    "username": username,
                    "url": info.get("url", ""),
                    "exists": True,
                    "status": info.get("status", "found"),
                    "source": "maigret",
                })
        except Exception as e:
            logger.warning("Maigret search for '%s' failed: %s", username, e)

    profiles.sort(key=lambda p: (p.get("platform", "")))
    return profiles
