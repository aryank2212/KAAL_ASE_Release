"""KAAL ASE sourced-briefing demo: pipeline core (stdlib only).

Agents follow the KAAL ASE contract: each returns
{job_id, outputs, source_references, confidence, warnings, requires_human_review}.
No agent writes an accepted fact. Claims are verbatim sentences from public
Wikipedia revisions, so every claim carries a permalink and a quote by construction.

Scope guardrail: topics, organisations, places, events and technologies only.
Pages about people (Wikidata instance-of human) are refused.
"""
import hashlib
import json
import re
import time
import urllib.parse
import urllib.request
import uuid

UA = "RedCloveBriefing/0.1 (https://redclove.space; mail.redclove@gmail.com)"
WP = "https://en.wikipedia.org/w/api.php"
WD = "https://www.wikidata.org/w/api.php"
MAX_PAGES = 3
MAX_CLAIMS = 8
MAX_CHARS_PER_PAGE = 60_000
MIN_COVERAGE = 0.34

STOP = set("""a an the of in on at to for from by with and or is are was were be been being what who whom whose which
when where why how does do did has have had it its this that these those as about into over under tell me give
explain describe please can could would should will than then there their they them his her he she i you we us our""".split())

QUESTION_WORDS = {"what", "who", "when", "where", "why", "how", "which", "tell", "explain", "describe", "give"}


def _get(url, params):
    full = url + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(full, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode("utf-8"))


def tokens(text):
    return [w for w in re.findall(r"[a-z0-9]+", text.lower()) if w not in STOP and len(w) > 1]


def split_sentences(text):
    out = []
    for para in text.split("\n"):
        para = para.strip()
        if not para or para.startswith("="):
            continue
        for s in re.split(r"(?<=[.!?])\s+(?=[A-Z0-9\"'(])", para):
            s = s.strip()
            if 40 <= len(s) <= 400:
                out.append(s)
    return out


def score_sentence(sentence, qterms):
    """Coverage of distinct query terms, small bonus for adjacent-pair matches. Heuristic, not a probability."""
    if not qterms:
        return 0.0
    st = tokens(sentence)
    sset = set(st)
    cov = sum(1 for t in set(qterms) if t in sset) / len(set(qterms))
    pairs = {(a, b) for a, b in zip(qterms, qterms[1:])}
    bonus = 0.15 if pairs and any((a, b) in pairs for a, b in zip(st, st[1:])) else 0.0
    return min(1.0, cov + bonus)


def contract(agent, outputs, refs=None, confidence=1.0, warnings=None, review=True):
    return {
        "agent": agent,
        "job_id": uuid.uuid4().hex[:12],
        "outputs": outputs,
        "source_references": refs or [],
        "confidence": round(confidence, 2),
        "warnings": warnings or [],
        "requires_human_review": review,
    }


# ---- agents -----------------------------------------------------------------

def plan(question):
    topic_terms = [w for w in tokens(question) if w not in QUESTION_WORDS]
    queries = [question.strip()]
    topic = " ".join(topic_terms)
    if topic and topic != question.strip().lower():
        queries.append(topic)
    return contract("planner", {"queries": queries, "terms": topic_terms}, review=False)


def discover(queries):
    seen, titles = set(), []
    for q in queries:
        data = _get(WP, {"action": "query", "list": "search", "srsearch": q, "srlimit": 4, "format": "json"})
        for hit in data.get("query", {}).get("search", []):
            if hit["title"] not in seen:
                seen.add(hit["title"])
                titles.append(hit["title"])
    return contract("web_discovery", {"titles": titles[:6]}, [f"{WP}?list=search"], review=False)


def is_human(qid):
    if not qid:
        return False
    data = _get(WD, {"action": "wbgetentities", "ids": qid, "props": "claims", "format": "json"})
    claims = data.get("entities", {}).get(qid, {}).get("claims", {}).get("P31", [])
    for c in claims:
        val = c.get("mainsnak", {}).get("datavalue", {}).get("value", {})
        if isinstance(val, dict) and val.get("id") == "Q5":
            return True
    return False


def fetch_page(title):
    data = _get(WP, {
        "action": "query", "titles": title, "prop": "extracts|pageprops|revisions|info",
        "explaintext": 1, "rvprop": "ids|timestamp", "inprop": "url", "ppprop": "wikibase_item",
        "redirects": 1, "format": "json",
    })
    page = next(iter(data["query"]["pages"].values()))
    if "missing" in page:
        return None
    rev = page["revisions"][0]
    return {
        "title": page["title"],
        "qid": page.get("pageprops", {}).get("wikibase_item"),
        "text": (page.get("extract") or "")[:MAX_CHARS_PER_PAGE],
        "revid": rev["revid"],
        "revision_time": rev["timestamp"],
        "permalink": f"https://en.wikipedia.org/w/index.php?title={urllib.parse.quote(page['title'].replace(' ', '_'))}&oldid={rev['revid']}",
    }


def collect(titles):
    pages, warnings = [], []
    for i, t in enumerate(titles):
        if len(pages) >= MAX_PAGES:
            break
        p = fetch_page(t)
        if not p or not p["text"]:
            continue
        if is_human(p["qid"]):
            if i == 0:
                return None, [f"'{p['title']}' is a page about a person. This demo covers topics, organisations, places and events only."]
            warnings.append(f"Skipped '{p['title']}' (page about a person).")
            continue
        pages.append(p)
    return pages, warnings


def judge_and_extract(pages, terms):
    """Score every sentence, keep those above threshold. Claims are verbatim quotes."""
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    claims = []
    for rank, p in enumerate(pages):
        for s in split_sentences(p["text"]):
            sc = score_sentence(s, terms)
            if sc >= MIN_COVERAGE:
                claims.append({
                    "id": hashlib.sha1((p["permalink"] + s).encode()).hexdigest()[:12],
                    "text": s, "quote": s, "source_title": p["title"], "source_url": p["permalink"],
                    "revision_time": p["revision_time"], "retrieved_at": now,
                    "extractor": "extractive-v1", "confidence": round(sc * (1.0 - 0.1 * rank), 2),
                    "status": "proposed",
                })
    claims.sort(key=lambda c: -c["confidence"])
    seen, uniq = set(), []
    for c in claims:
        if c["text"] not in seen:
            seen.add(c["text"])
            uniq.append(c)
    return uniq[:MAX_CLAIMS]


def run(question):
    question = (question or "").strip()
    if len(question) < 4 or len(question) > 200:
        raise ValueError("Ask a question between 4 and 200 characters.")
    trace = []
    p = plan(question)
    trace.append(p)
    if not p["outputs"]["terms"]:
        raise ValueError("Add a few topic words to the question.")
    d = discover(p["outputs"]["queries"])
    trace.append(d)
    pages, warnings = collect(d["outputs"]["titles"])
    if pages is None:
        trace.append(contract("review", {"refused": True}, warnings=warnings, review=False))
        return {"question": question, "refused": True, "warnings": warnings, "claims": [], "trace": trace}
    claims = judge_and_extract(pages, p["outputs"]["terms"])
    trace.append(contract("entity_judge_extract", {"claims": len(claims), "pages": [x["title"] for x in pages]},
                          [x["permalink"] for x in pages],
                          confidence=(sum(c["confidence"] for c in claims) / len(claims)) if claims else 0.0,
                          warnings=warnings))
    if not claims:
        warnings.append("No sentence in the retrieved pages matched the question well enough. Nothing is claimed.")
    return {"question": question, "refused": False, "warnings": warnings, "claims": claims, "trace": trace}
