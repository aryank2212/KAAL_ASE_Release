import datetime
import email.utils
import logging
import re
import urllib.parse
import xml.etree.ElementTree as ET

import httpx

logger = logging.getLogger(__name__)

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

HTML_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate",
    "DNT": "1",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}

def _parse_rfc2822(date_str: str) -> datetime.datetime | None:
    if not date_str:
        return None
    try:
        dt = email.utils.parsedate_to_datetime(date_str)
        return dt.replace(tzinfo=None)
    except Exception:
        return None


def _sort_by_recency(results: list[dict], max_days: int = 7) -> list[dict]:
    now = datetime.datetime.utcnow()
    cutoff = now - datetime.timedelta(days=max_days)
    with_date = []
    without_date = []
    for r in results:
        dt = _parse_rfc2822(r.get("published", ""))
        if dt:
            if dt >= cutoff:
                with_date.append((dt, r))
        else:
            without_date.append(r)
    with_date.sort(key=lambda x: x[0], reverse=True)
    return [r for _, r in with_date] + without_date


SITE_SPECIFIC = {
    "Reddit": "site:reddit.com",
    "Quora": "site:quora.com",
    "X / Twitter": "site:x.com OR site:twitter.com",
}


def search_web(query: str, max_results: int = 5) -> list[dict]:
    results = []
    seen_urls: set[str] = set()

    def add(r: dict):
        u = r.get("url", "")
        if u and u not in seen_urls:
            seen_urls.add(u)
            results.append(r)

    ddg_ok = False
    try:
        resp = httpx.get(
            "https://api.duckduckgo.com/",
            params={"q": query, "format": "json", "no_html": 1, "skip_disambig": 1},
            timeout=5,
            follow_redirects=True,
        )
        if resp.status_code in (200, 202):
            data = resp.json()
            ddg_ok = True
            title = data.get("AbstractTitle") or data.get("Heading", "")
            abstract = data.get("AbstractText", "")
            if abstract:
                add({
                    "title": title,
                    "snippet": abstract,
                    "source": data.get("AbstractSource", "DuckDuckGo"),
                    "url": data.get("AbstractURL", ""),
                })
            for topic in data.get("RelatedTopics", []):
                if "Topics" in topic:
                    for sub in topic["Topics"]:
                        if len(results) >= max_results * 2:
                            break
                        add({
                            "title": sub.get("Text", "").split(" - ")[0],
                            "snippet": sub.get("Text", ""),
                            "source": "DuckDuckGo",
                            "url": sub.get("FirstURL", ""),
                        })
                else:
                    if len(results) >= max_results * 2:
                        break
                    add({
                        "title": topic.get("Text", "").split(" - ")[0],
                        "snippet": topic.get("Text", ""),
                        "source": "DuckDuckGo",
                        "url": topic.get("FirstURL", ""),
                    })
    except Exception as e:
        logger.debug("DuckDuckGo API search failed: %s", e)

    if len(results) < max_results and not ddg_ok:
        try:
            html_results = _search_html_fallback(query, max_results)
            for r in html_results:
                add(r)
        except Exception as e:
            logger.debug("HTML search fallback failed: %s", e)

    try:
        news_results = _search_google_news(query, max_results * 2)
        for r in news_results:
            add(r)
    except Exception as e:
        logger.debug("Google News search failed: %s", e)

    results = _sort_by_recency(results, max_days=30)

    if len(results) < max_results:
        try:
            wiki_results = _search_wikipedia(query, max_results)
            for r in wiki_results:
                add(r)
        except Exception as e:
            logger.debug("Wikipedia search failed: %s", e)

    results = _sort_by_recency(results, max_days=30)
    return results[:max_results]


def search_recent(query: str, max_results: int = 5) -> list[dict]:
    return search_web(query, max_results)


def _search_html_fallback(query: str, max_results: int = 5) -> list[dict]:
    results = []
    try:
        resp = httpx.get(
            "https://html.duckduckgo.com/html/",
            params={"q": query, "df": "y"},
            timeout=5,
            follow_redirects=True,
            headers=HTML_HEADERS,
        )
        if resp.status_code == 200:
            for m in re.finditer(
                r'<a[^>]*class="result__a"[^>]*href="([^"]*)"[^>]*>(.*?)</a>',
                resp.text,
                re.DOTALL,
            ):
                url = m.group(1)
                title = re.sub(r"<[^>]+>", "", m.group(2)).strip()
                snippet_m = re.search(
                    r'<a[^>]*class="result__snippet"[^>]*>(.*?)</a>',
                    resp.text[m.end():m.end() + 500],
                    re.DOTALL,
                )
                snippet = re.sub(r"<[^>]+>", "", snippet_m.group(1)).strip() if snippet_m else ""
                if url.startswith("//"):
                    url = "https:" + url
                parsed = urllib.parse.urlparse(url)
                if "duckduckgo.com/l/" in parsed.netloc or "duckduckgo.com/l" in parsed.path:
                    qs = urllib.parse.parse_qs(parsed.query)
                    if "uddg" in qs:
                        url = qs["uddg"][0]
                results.append({"title": title, "snippet": snippet, "source": "Web", "url": url})
                if len(results) >= max_results:
                    break
    except Exception as e:
        logger.warning("HTML search fallback failed: %s", e)
    return results


def _search_wikipedia(query: str, max_results: int = 5) -> list[dict]:
    results = []
    try:
        resp = httpx.get(
            "https://en.wikipedia.org/w/api.php",
            params={
                "action": "query",
                "list": "search",
                "srsearch": query,
                "format": "json",
                "srlimit": max_results,
                "srprop": "snippet|timestamp",
            },
            timeout=5,
            follow_redirects=True,
            headers={"User-Agent": "KAAL-ASE-OSINT/1.0 (OSINT research project; kaal@example.com)"},
        )
        if resp.status_code == 200:
            data = resp.json()
            for item in data.get("query", {}).get("search", []):
                title = item.get("title", "")
                snippet = re.sub(r"<[^>]+>", "", item.get("snippet", ""))
                url = f"https://en.wikipedia.org/wiki/{urllib.parse.quote(title.replace(' ', '_'))}"
                results.append({
                    "title": title,
                    "snippet": snippet,
                    "source": "Wikipedia",
                    "url": url,
                })
    except Exception as e:
        logger.debug("Wikipedia search failed: %s", e)
    return results


def _search_google_news(query: str, max_results: int = 5) -> list[dict]:
    results = []
    try:
        resp = httpx.get(
            "https://news.google.com/rss/search",
            params={"q": query, "hl": "en-US", "gl": "US", "ceid": "US:en"},
            timeout=8,
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
        )
        if resp.status_code != 200:
            return results
        root = ET.fromstring(resp.content)
        for item in root.iter("item"):
            title = ""
            title_elem = item.find("title")
            if title_elem is not None and title_elem.text:
                title = title_elem.text
            link = ""
            link_elem = item.find("link")
            if link_elem is not None and link_elem.text:
                link = link_elem.text
            snippet = ""
            desc_elem = item.find("description")
            if desc_elem is not None and desc_elem.text:
                clean = re.sub(r"<[^>]+>", " ", desc_elem.text)
                snippet = re.sub(r"\s+", " ", clean).strip()
            source = ""
            source_elem = item.find("source")
            if source_elem is not None:
                source = source_elem.text or ""
            pub_date = ""
            pub_elem = item.find("pubDate")
            if pub_elem is not None and pub_elem.text:
                pub_date = pub_elem.text
            results.append({
                "title": title,
                "snippet": snippet[:300],
                "source": f"Google News ({source})" if source else "Google News",
                "url": link or "",
                "published": pub_date,
            })
            if len(results) >= max_results:
                break
    except Exception as e:
        logger.debug("Google News search failed: %s", e)
    return results


def fetch_page_text(url: str) -> dict | None:
    try:
        resp = httpx.get(
            url,
            timeout=10,
            follow_redirects=True,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
            },
        )
        if resp.status_code != 200:
            return None
        text = resp.text
        title_m = re.search(r"<title>(.*?)</title>", text, re.IGNORECASE | re.DOTALL)
        title = title_m.group(1).strip() if title_m else ""
        for tag in ("script", "style", "nav", "footer", "header", "noscript"):
            text = re.sub(rf"<{tag}[^>]*>.*?</{tag}>", "", text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        lines = [l.strip() for l in text.split("\n") if l.strip() and len(l.strip()) > 30]
        body = "\n".join(lines[:30])
        if body:
            return {"url": url, "title": title, "text": body[:5000]}
    except Exception as e:
        logger.warning("Failed to fetch %s: %s", url, e)
    return None


def check_url_exists(url: str, timeout: int = 5) -> dict:
    try:
        resp = httpx.head(url, timeout=timeout, follow_redirects=True)
        return {"url": url, "status": resp.status_code, "exists": resp.status_code < 400}
    except Exception as e:
        return {"url": url, "status": 0, "exists": False, "error": str(e)}
