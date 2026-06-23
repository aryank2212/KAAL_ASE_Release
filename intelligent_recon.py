#!/usr/bin/env python3
"""
Intelligent Recursive OSINT Recon Loop
Combines interactive initialization with strict semantic filtering and dynamic dorking.
"""

import asyncio
import json
import os
import re
import shutil
import time
import httpx
from datetime import datetime

API_BASE = "http://localhost:8000/api/v1/analysis"
OLLAMA_API = "http://localhost:11434/api/chat"

HERE = os.path.dirname(os.path.abspath(__file__))

FIELDS = [
    ("name",               "Full name of subject"),
    ("context",            "Background context"),
    ("phrase",             "Phrase / quote to search"),
    ("links",              "Known links / URLs"),
    ("information_wanted", "What you want to find out"),
    ("anything_you_have",  "Any other info"),
]

MODELS = [
    ("gemma2:2b", "Default (balanced)"),
    ("llama3.2:1b", "Faster, less accurate"),
]

def log(msg):
    print(f"  [{datetime.now().strftime('%H:%M:%S')}] {msg}")

def collect_input() -> dict:
    data = {}
    print("=" * 70)
    print("  KAAL-ASE Intelligent OSINT Investigator")
    print("  Web search + Social media discovery + ML-guided continuous loop")
    print("=" * 70)
    print("\nEnter details (press Enter to skip any field):")
    for key, label in FIELDS:
        val = input(f"  {label}: ").strip()
        if val:
            data[key] = val
            
    print("\n  Model selection:")
    print(f"    {'0':>3}. Default (gemma2:2b)")
    for i, (m, desc) in enumerate(MODELS, 1):
        print(f"    {i:>3}. {m} - {desc}")
    print(f"    {'c':>3}. Custom model name")
    m_choice = input("  Choose model [0]: ").strip().lower()
    
    data["model"] = "gemma2:2b"
    if m_choice == "c":
        custom = input("  Enter model name: ").strip()
        if custom:
            data["model"] = custom
    elif m_choice.isdigit() and int(m_choice) > 0:
        idx = int(m_choice)
        if 1 <= idx <= len(MODELS):
            data["model"] = MODELS[idx - 1][0]
            
    dur = input("\n  Enter duration for loop in seconds [120]: ").strip()
    data["duration"] = int(dur) if dur.isdigit() else 120
    
    return data

async def fetch_url_text(url: str, timeout: int = 10) -> tuple[str, bool]:
    try:
        proc = await asyncio.create_subprocess_exec(
            "curl", "-sL", "--max-time", str(timeout),
            "-A", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            url,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout + 2)
        decoded = stdout.decode("utf-8", errors="replace")

        has_img = bool(re.search(r'<img[^>]+>', decoded, re.IGNORECASE))
        text = re.sub(r"<style[^>]*>.*?</style>", "", decoded, flags=re.DOTALL)
        text = re.sub(r"<script[^>]*>.*?</script>", "", text, flags=re.DOTALL)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text).strip()

        if not text:
            text = decoded[:500]
        return text[:5000], has_img
    except Exception as e:
        return f"[fetch error: {e}]", False

async def call_ollama(prompt: str, model: str, system: str = "You are a senior OSINT analyst.", json_format: bool = False) -> str:
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        "stream": False,
    }
    if json_format:
        payload["format"] = "json"
        
    async with httpx.AsyncClient() as client:
        try:
            r = await client.post(OLLAMA_API, json=payload, timeout=300.0)
            if r.status_code == 200:
                return r.json().get("message", {}).get("content", "")
            return f"[Ollama API Error: {r.status_code}]"
        except Exception as e:
            return f"[Ollama Error: {str(e)}]"

async def check_relevance(text: str, context: str, model: str) -> bool:
    """Semantic drift prevention check."""
    prompt = (
        f"Subject Context: {context}\n\n"
        f"Scraped Text: {text[:2000]}\n\n"
        f"Does the scraped text strongly relate to a modern, living person described by the Subject Context? "
        f"If the text is about historical populations, mythology, TV shows, or 'Indo-Aryan migrations', answer NO. "
        f"Answer ONLY 'YES' or 'NO'."
    )
    resp = await call_ollama(prompt, model, system="You are a strict binary classifier.")
    return "YES" in resp.upper()

async def run_osint_lookup(query: dict) -> dict:
    async with httpx.AsyncClient() as client:
        try:
            r = await client.post(f"{API_BASE}/osint-lookup", json=query, timeout=300.0)
            if r.status_code == 200:
                return r.json()
            return {"error": f"API Error {r.status_code}: {r.text[:200]}"}
        except Exception as e:
            return {"error": str(e)}

async def run():
    user_input = collect_input()
    if not user_input.get("name") and not user_input.get("context"):
        print("Required fields missing. Exiting.")
        return

    model = user_input["model"]
    max_duration = user_input.pop("duration")
    context = user_input.get("context", user_input.get("name", ""))
    
    # State tracking for entity resolution
    all_links_seen = set()
    verified_entities = set()
    all_text_data = []
    
    iteration = 0
    start_time = time.time()

    print(f"\n{'='*70}")
    print(f"  Starting intelligent {max_duration}s loop for: {user_input.get('name', 'Unknown')}")
    print(f"{'='*70}\n")

    while time.time() - start_time < max_duration:
        iteration += 1
        elapsed = int(time.time() - start_time)
        remaining = max_duration - elapsed
        log(f"Iteration {iteration} — {remaining}s remaining")

        log("Running OSINT API lookup...")
        result = await run_osint_lookup(user_input)
        if "error" in result:
            log(f"API error: {result['error']}")
            await asyncio.sleep(2)
            continue

        # Extract entities with high confidence
        for e in result.get("entities", []):
            if e.get("confidence", 0) > 0.75:
                verified_entities.add(e.get("name"))

        # Extract URLs
        urls = set()
        for key in ["web_search", "raw_web_search"]:
            for w in result.get(key, []):
                u = w.get("url", "")
                if u and u not in all_links_seen:
                    urls.add(u)
                    
        for p in result.get("social_profiles", []):
            u = p.get("url", "")
            if u and u not in all_links_seen:
                urls.add(u)

        for mr in result.get("maigret_searches", []):
            for site, info in mr.get("profiles", {}).items():
                u = info.get("url", "")
                if u and u not in all_links_seen:
                    urls.add(u)

        # Ensure any user-provided links are fetched in the first iteration
        if iteration == 1:
            user_provided_urls = re.findall(r"https?://[^\s]+", str(user_input.get("links", "")) + " " + str(user_input.get("anything_you_have", "")))
            for u in user_provided_urls:
                if u not in all_links_seen:
                    urls.add(u)

        log(f"Found {len(urls)} new URLs to fetch")

        # Fetch and validate
        fetch_tasks = []
        target_urls = list(urls)[:10]
        for url in target_urls:
            all_links_seen.add(url)
            fetch_tasks.append(fetch_url_text(url))

        if fetch_tasks:
            fetched = await asyncio.gather(*fetch_tasks, return_exceptions=True)
            for url, res in zip(target_urls, fetched):
                if isinstance(res, Exception):
                    continue
                text, _ = res
                if len(text) > 50:
                    # ML Relevance Check
                    is_relevant = await check_relevance(text, context, model)
                    if is_relevant:
                        log(f"  [RELEVANT] Fetched {url[:60]} ({len(text)} chars)")
                        all_text_data.append(f"=== FROM {url} ===\n{text}\n")
                    else:
                        log(f"  [DISCARDED] Irrelevant text from {url[:60]}")

        # Update loop state via dynamic dorking
        corpus = "\n\n".join(all_text_data[-15:])
        log("Asking AI to formulate next precision searches (dorks)...")
        dork_prompt = (
            f"Subject: {user_input.get('name')}\nContext: {context}\n"
            f"Verified Entities: {list(verified_entities)[:20]}\n\n"
            f"Data gathered so far:\n{corpus[:4000]}\n\n"
            "Formulate 3 specific Google dorks or search phrases to find MORE information. "
            "Output JSON with a key 'queries' containing a list of strings."
        )
        
        dork_response = await call_ollama(dork_prompt, model, json_format=True)
        try:
            parsed_dorks = json.loads(dork_response)
            dorks = parsed_dorks.get("queries", [])
            log(f"AI formulated dorks: {dorks[:2]}")
            # Feed dorks into next input phrase only if we got some
            if dorks:
                user_input["phrase"] = " ".join(dorks)
        except Exception as e:
            log(f"Failed to parse JSON dorks ({e}). Raw response: {dork_response[:100]}")
        
        # Enrich context for next run
        user_input["anything_you_have"] = f"Verified Context: {', '.join(list(verified_entities)[:30])}"
        print(f"  → Verified Entities: {len(verified_entities)}")
        print(f"  → Text corpus: {sum(len(t) for t in all_text_data)} chars\n")

        await asyncio.sleep(1)

    print(f"\n{'='*70}")
    print(f"  LOOP COMPLETE — Generating final intelligence report...")
    print(f"{'='*70}\n")

    final_corpus = "\n\n".join(all_text_data)
    final_prompt = (
        f"COMPREHENSIVE OSINT INVESTIGATION REPORT\n"
        f"Subject: {user_input.get('name', 'Unknown')}\n"
        f"Original context: {context}\n"
        f"Provided Known Links: {user_input.get('links', 'None')}\n"
        f"Information Wanted: {user_input.get('information_wanted', 'None')}\n"
        f"Investigation duration: {max_duration}s\n"
        f"URLs fetched: {len(all_links_seen)}\n"
        f"Verified Entities: {list(verified_entities)}\n\n"
        f"ALL RELEVANT RAW DATA COLLECTED:\n{final_corpus[:15000]}\n\n"
        "Generate a complete intelligence report based STRICTLY on the raw data collected above and the Provided Known Links.\n"
        "CRITICAL INSTRUCTION: DO NOT CONFUSE the subject (a modern living person) with historical groups, mythological figures, or Wikipedia articles about 'Indo-Aryan migrations' unless explicitly relevant to their profession. Focus on their actual digital footprint, social media handles, and provided links.\n"
        "1. SUBJECT IDENTITY (Age, Location, Profile)\n"
        "2. DIGITAL FOOTPRINT (Analyze the specific provided links: Instagram, YouTube, etc.)\n"
        "3. KEY EVIDENCE (include URLs)\n"
        "4. NETWORK MAP\n"
        "5. RECOMMENDATIONS"
    )

    final_report = await call_ollama(final_prompt, model)

    print("\n" + "=" * 70)
    print("  FINAL INTELLIGENCE REPORT")
    print("=" * 70 + "\n")
    print(final_report)
    print("\n" + "=" * 70)

    report_path = os.path.join(HERE, f"reports/intelligent_recon_{int(time.time())}.txt")
    os.makedirs(os.path.join(HERE, "reports"), exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(final_report)
    print(f"\n  Report saved: {report_path}")

if __name__ == "__main__":
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        print("\nQuit.")
