import re
from typing import Any

from app.models import Evidence

EXTRACTOR_NAME = "social-indicator-extractor"
EXTRACTOR_VERSION = "0.1.0"

SOCIAL_DOMAINS = {
    "facebook.com": "Facebook",
    "fb.com": "Facebook",
    "twitter.com": "X/Twitter",
    "x.com": "X/Twitter",
    "instagram.com": "Instagram",
    "linkedin.com": "LinkedIn",
    "tiktok.com": "TikTok",
    "youtube.com": "YouTube",
    "youtu.be": "YouTube",
    "reddit.com": "Reddit",
    "snapchat.com": "Snapchat",
    "pinterest.com": "Pinterest",
    "telegram.org": "Telegram",
    "t.me": "Telegram",
    "discord.com": "Discord",
    "discord.gg": "Discord",
    "github.com": "GitHub",
    "gitlab.com": "GitLab",
    "whatsapp.com": "WhatsApp",
    "wa.me": "WhatsApp",
    "signal.org": "Signal",
    "threads.net": "Threads",
    "bsky.app": "Bluesky",
    "mastodon.social": "Mastodon",
    "weibo.com": "Weibo",
    "qq.com": "QQ",
    "vk.com": "VK",
    "ok.ru": "Odnoklassniki",
}

URL_PATTERN = re.compile(r"https?://(?:www\.)?([^\s/]+)")
HANDLE_PATTERN = re.compile(r"(?:^|\s)(@\w{2,30})")
EMAIL_PATTERN = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
PHONE_PATTERN = re.compile(
    r"(?:\+?\d{1,3}[-.\s]?)?\(?\d{2,4}\)?[-.\s]?\d{2,4}[-.\s]?\d{2,9}"
)


def extract_observations(evidence: Evidence) -> list[dict]:
    source_text = evidence.filename
    if evidence.sha256:
        source_text += f" ({evidence.sha256[:12]})"

    observations: list[dict] = []

    if evidence.storage_uri:
        uri_obs = _check_url(evidence.storage_uri)
        if uri_obs:
            observations.append(uri_obs)

    return observations


def extract_social_indicators(text: str) -> list[dict]:
    observations: list[dict] = []
    seen: set[tuple[str, str]] = set()

    for match in URL_PATTERN.finditer(text):
        domain = match.group(1).lower()
        for soc_domain, platform in SOCIAL_DOMAINS.items():
            if soc_domain in domain or domain in soc_domain:
                url = match.group(0).rstrip(").,;:!?")
                key = ("social_url", url)
                if key not in seen:
                    seen.add(key)
                    observations.append({
                        "observation_type": "indicator.social_url",
                        "value": {
                            "platform": platform,
                            "url": url,
                            "domain": domain,
                        },
                        "confidence": _url_confidence(url, domain),
                        "extractor": EXTRACTOR_NAME,
                        "extractor_version": EXTRACTOR_VERSION,
                    })
                break

    for match in HANDLE_PATTERN.finditer(text):
        handle = match.group(1)
        key = ("social_handle", handle)
        if key not in seen:
            seen.add(key)
            observations.append({
                "observation_type": "indicator.social_handle",
                "value": {
                    "handle": handle,
                    "platforms": _guess_platform_from_handle(handle),
                },
                "confidence": 0.5,
                "extractor": EXTRACTOR_NAME,
                "extractor_version": EXTRACTOR_VERSION,
            })

    for match in EMAIL_PATTERN.finditer(text):
        email = match.group(0).rstrip(".).,;:!?")
        key = ("contact_email", email)
        if key not in seen:
            seen.add(key)
            observations.append({
                "observation_type": "contact.email",
                "value": {"email": email},
                "confidence": 0.9,
                "extractor": EXTRACTOR_NAME,
                "extractor_version": EXTRACTOR_VERSION,
            })

    return observations


def _check_url(url: str) -> dict | None:
    domain = url.split("/")[2] if "://" in url else url.split("/")[0]
    for soc_domain, platform in SOCIAL_DOMAINS.items():
        if soc_domain in domain or domain in soc_domain:
            return {
                "observation_type": "evidence.storage_social",
                "value": {
                    "platform": platform,
                    "uri": url,
                },
                "confidence": 0.8,
                "extractor": EXTRACTOR_NAME,
                "extractor_version": EXTRACTOR_VERSION,
            }
    return None


def _url_confidence(url: str, domain: str) -> float:
    if "profile" in url.lower() or "user" in url.lower():
        return 0.9
    if "post" in url.lower() or "status" in url.lower():
        return 0.8
    return 0.6


def _guess_platform_from_handle(handle: str) -> list[str]:
    h = handle.lower()
    if h in ("@everyone", "@here"):
        return ["Discord"]
    if h.startswith("@elonmusk") or h.startswith("@realdonald"):
        return ["X/Twitter"]
    return []
