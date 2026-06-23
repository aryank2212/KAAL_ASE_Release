#!/usr/bin/env python3
"""
Recursive OSINT Recon Loop
  Input → Search → Fetch URLs → Extract text/screenshots → Enrich → Repeat (2 min)
"""

import asyncio
import json
import os
import re
import shutil
import subprocess
import sys
import textwrap
import time
import urllib.parse
from datetime import datetime

API_BASE = "http://localhost:8000/api/v1/analysis/osint-lookup"
OLLAMA_API = "http://localhost:11434/api/chat"

HERE = os.path.dirname(os.path.abspath(__file__))
VENV_PYTHON = os.path.join(HERE, "venv/bin/python")
sys.path.insert(0, os.path.join(HERE, "services/api"))


def log(msg):
    print(f"  [{datetime.now().strftime('%H:%M:%S')}] {msg}")


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

        # Check for images before stripping
        has_img = bool(re.search(r'<img[^>]+>', decoded, re.IGNORECASE))

        # Strip HTML tags to get visible text
        text = re.sub(r"<style[^>]*>.*?</style>", "", decoded, flags=re.DOTALL)
        text = re.sub(r"<script[^>]*>.*?</script>", "", text, flags=re.DOTALL)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text).strip()

        if not text:
            text = decoded[:500]  # fallback if stripping removed everything
        return text[:5000], has_img
    except Exception as e:
        return f"[fetch error: {e}]", False


async def screenshot_page(url: str) -> str | None:
    """Try to screenshot a page using available tools."""
    # Try wkhtmltoimage
    wkhtml = shutil.which("wkhtmltoimage")
    if wkhtml:
        outpath = f"/tmp/recon_screenshot_{int(time.time())}.png"
        try:
            proc = await asyncio.create_subprocess_exec(
                wkhtml, "--width", "1280", url, outpath,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await asyncio.wait_for(proc.wait(), timeout=15)
            if os.path.exists(outpath) and os.path.getsize(outpath) > 1000:
                return outpath
        except Exception:
            pass

    # Try puppeteer/chromium via CLI
    chrome = shutil.which("chromium-browser") or shutil.which("chromium") or shutil.which("google-chrome") or shutil.which("google-chrome-stable")
    if chrome:
        outpath = f"/tmp/recon_screenshot_{int(time.time())}.png"
        try:
            proc = await asyncio.create_subprocess_exec(
                chrome, "--headless", "--disable-gpu", "--no-sandbox",
                f"--screenshot={outpath}",
                f"--window-size=1280,1024",
                url,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await asyncio.wait_for(proc.wait(), timeout=20)
            if os.path.exists(outpath) and os.path.getsize(outpath) > 1000:
                return outpath
        except Exception:
            pass

    return None


async def call_ollama(prompt: str, model: str = "gemma4") -> str:
    payload = json.dumps({
        "model": model,
        "messages": [
            {"role": "system", "content": "You are a senior OSINT analyst extracting intelligence from all available data."},
            {"role": "user", "content": prompt},
        ],
        "stream": False,
    }).encode()
    try:
        proc = await asyncio.create_subprocess_exec(
            "curl", "-s", "--max-time", "60",
            "-X", "POST",
            "-H", "Content-Type: application/json",
            "-d", payload.decode(),
            OLLAMA_API,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=65)
        data = json.loads(stdout)
        return data.get("message", {}).get("content", "")
    except Exception as e:
        return f"[Ollama error: {e}]"


async def run_osint_lookup(query: dict) -> dict:
    payload = json.dumps(query).encode()
    try:
        proc = await asyncio.create_subprocess_exec(
            "curl", "-s", "--max-time", "120",
            "-X", "POST",
            "-H", "Content-Type: application/json",
            "-d", payload.decode(),
            API_BASE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=125)
        return json.loads(stdout)
    except Exception as e:
        return {"error": str(e)}


async def run():
    print("=" * 70)
    print("  KAAL-ASE RECURSIVE OSINT RECON LOOP")
    print("  Searches, fetches URLs, screenshots, re-searches — for 2 minutes")
    print("=" * 70)

    # Show models
    print("\nAvailable Ollama models:")
    proc = await asyncio.create_subprocess_exec(
        "ollama", "list",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
    )
    stdout, _ = await proc.communicate()
    for line in stdout.decode().strip().split("\n"):
        print(f"  {line}")

    # Parse CLI args / defaults
    import argparse
    parser = argparse.ArgumentParser(description="Recursive OSINT Recon Loop")
    parser.add_argument("--name", default="johnwick")
    parser.add_argument("--context", default="fictional character assassin")
    parser.add_argument("--extra", default="")
    parser.add_argument("--model", default="")
    parser.add_argument("--duration", type=int, default=120)
    args = parser.parse_args()

    default_model = "gemma4" if "gemma4" in stdout.decode() else "gemma2:2b"
    model = args.model or default_model
    name = args.name
    context = args.context
    extra = args.extra
    max_duration = args.duration

    print(f"  Target: {name}")
    print(f"  Context: {context}")
    print(f"  Model: {model}")
    print(f"  Duration: {max_duration}s")

    user_input = {
        "name": name,
        "context": context,
        "phrase": "",
        "links": extra,
        "information_wanted": "everything available about this subject",
        "anything_you_have": extra,
        "model": model,
    }

    all_links_seen = set()
    all_text_data = []
    iteration = 0
    start_time = time.time()


    print(f"\n{'='*70}")
    print(f"  Starting 2-minute recursive investigation loop for: {name}")
    print(f"{'='*70}\n")

    while time.time() - start_time < max_duration:
        iteration += 1
        elapsed = int(time.time() - start_time)
        remaining = max_duration - elapsed
        log(f"Iteration {iteration} — {remaining}s remaining")

        # Run OSINT lookup
        log("Running OSINT lookup...")
        result = await run_osint_lookup(user_input)
        if "error" in result:
            log(f"API error: {result['error']}")
            await asyncio.sleep(2)
            continue

        # Extract all URLs from results
        urls = set()

        # Web search URLs
        for w in result.get("web_search", []):
            u = w.get("url", "")
            if u and u not in all_links_seen:
                urls.add(u)

        # Raw web search
        for w in result.get("raw_web_search", []):
            u = w.get("url", "")
            if u and u not in all_links_seen:
                urls.add(u)

        # Social profile URLs
        for p in result.get("social_profiles", []):
            u = p.get("url", "")
            if u and u not in all_links_seen:
                urls.add(u)

        # Maigret profile URLs
        for mr in result.get("maigret_searches", []):
            for site, info in mr.get("profiles", {}).items():
                u = info.get("url", "")
                if u and u not in all_links_seen:
                    urls.add(u)

        log(f"Found {len(urls)} new URLs to fetch")

        # Fetch URLs
        fetch_tasks = []
        for url in list(urls)[:10]:  # Max 10 per iteration
            all_links_seen.add(url)
            fetch_tasks.append(fetch_url_text(url))

        if fetch_tasks:
            fetched = await asyncio.gather(*fetch_tasks, return_exceptions=True)
            for url, (text, has_img) in zip(list(urls)[:10], fetched):
                if isinstance(text, str) and len(text) > 50:
                    log(f"  Fetched {url[:80]} ({len(text)} chars)")
                    all_text_data.append(f"=== FROM {url} ===\n{text}\n")

                    # Screenshot if page has images
                    if has_img:
                        log(f"  Images detected at {url[:60]} — screenshotting...")
                        ss_path = await screenshot_page(url)
                        if ss_path:
                            log(f"  Screenshot saved: {ss_path}")

        # Extract AI analysis from current results
        analysis = result.get("llm_analysis", "")
        if analysis:
            all_text_data.append(f"=== AI ANALYSIS (iteration {iteration}) ===\n{analysis}\n")

        # Build enriched input for next iteration
        corpus = "\n\n".join(all_text_data[-20:])  # Last 20 items
        enriched_context = f"{context}\n\nRaw data from investigation so far:\n{corpus[:8000]}"

        # Use Ollama to identify new search directions
        log("Asking AI for next investigation directions...")
        direction_prompt = (
            f"Subject: {name}\nOriginal context: {context}\n\n"
            f"Data gathered so far:\n{corpus[:4000]}\n\n"
            "Based on ALL data above, what specific search queries, usernames, emails, or URLs "
            "should I investigate NEXT? Be very specific. Return ONLY a JSON array of strings."
        )
        ai_directions = await call_ollama(direction_prompt, model)
        log(f"AI suggests: {ai_directions[:200]}")

        # Extract entities, handles, emails from AI response
        new_entities = re.findall(r'["\']([^"\']+)["\']', ai_directions)
        new_handles = re.findall(r'@(\w+)', ai_directions + corpus)
        new_emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', corpus)

        # Update user_input for next iteration
        user_input["context"] = enriched_context[:2000]
        user_input["anything_you_have"] = " ".join([
            extra,
            " ".join(new_handles[:10]),
            " ".join(new_emails[:5]),
            " ".join(new_entities[:10]),
        ]).strip()[:1000]

        # Show progress
        print(f"  → New handles: {new_handles[:5]}")
        print(f"  → New emails: {new_emails[:3]}")
        print(f"  → Links gathered: {len(all_links_seen)}")
        print(f"  → Text corpus: {sum(len(t) for t in all_text_data)} chars")
        print()

        await asyncio.sleep(1)

    # Time's up — generate final comprehensive report
    print(f"\n{'='*70}")
    print(f"  2-MINUTE LOOP COMPLETE — Generating final intelligence report...")
    print(f"{'='*70}\n")

    final_corpus = "\n\n".join(all_text_data)
    final_prompt = (
        f"COMPREHENSIVE OSINT INVESTIGATION REPORT\n"
        f"Subject: {name}\n"
        f"Original context: {context}\n"
        f"Investigation duration: 2 minutes\n"
        f"URLs fetched: {len(all_links_seen)}\n"
        f"Iterations: {iteration}\n\n"
        f"ALL RAW DATA COLLECTED:\n{final_corpus[:12000]}\n\n"
        "Generate a complete intelligence report:\n"
        "1. SUBJECT IDENTITY — who this appears to be\n"
        "2. DIGITAL FOOTPRINT — all social profiles, email registrations, web presence\n"
        "3. KEY EVIDENCE — specific findings with source URLs\n"
        "4. NETWORK MAP — associations, relationships, linked accounts\n"
        "5. RED FLAGS — inconsistencies, contradictions, suspicious findings\n"
        "6. DATA QUALITY — which sources are reliable, which are noise\n"
        "7. RECOMMENDATIONS — specific next steps for deeper investigation"
    )

    final_report = await call_ollama(final_prompt, model)

    print("\n" + "=" * 70)
    print("  FINAL INTELLIGENCE REPORT")
    print("=" * 70 + "\n")
    print(final_report)
    print("\n" + "=" * 70)

    # Save report
    report_path = os.path.join(HERE, f"reports/recon_{name}_{int(time.time())}.txt")
    os.makedirs(os.path.join(HERE, "reports"), exist_ok=True)
    with open(report_path, "w") as f:
        f.write(f"Recursive OSINT Recon Report\n")
        f.write(f"Subject: {name}\n")
        f.write(f"Date: {datetime.now().isoformat()}\n")
        f.write(f"Iterations: {iteration}\n")
        f.write(f"URLs fetched: {len(all_links_seen)}\n")
        f.write(f"Model: {model}\n\n")
        f.write(final_report)
    print(f"\n  Report saved: {report_path}")


if __name__ == "__main__":
    asyncio.run(run())
