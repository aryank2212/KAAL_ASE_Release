import httpx, json

API = "http://localhost:8000/api/v1/analysis"

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

def show_banner():
    print("=" * 60)
    print("  KAAL-ASE OSINT Investigator")
    print("  Web search + Social media discovery + AI analysis")
    print("=" * 60)

def collect_input() -> dict:
    data = {}
    print("\nEnter details (press Enter to skip any field):")
    print("  At least ONE field must be filled.")
    print()
    for key, label in FIELDS:
        val = input(f"  {label}: ").strip()
        if val:
            data[key] = val
    print()
    print("  Model selection:")
    print(f"    {'0':>3}. Default (gemma2:2b)")
    for i, (m, desc) in enumerate(MODELS, 1):
        print(f"    {i:>3}. {m} - {desc}")
    print(f"    {'c':>3}. Custom model name")
    m_choice = input("  Choose model [0]: ").strip().lower()
    if m_choice == "c":
        custom = input("  Enter model name: ").strip()
        if custom:
            data["model"] = custom
    elif m_choice.isdigit():
        idx = int(m_choice)
        if 1 <= idx <= len(MODELS):
            data["model"] = MODELS[idx - 1][0]
    return data

def run_lookup(data: dict):
    if not data:
        print("No data provided.")
        return

    print("\nRunning OSINT lookup...")

    try:
        r = httpx.post(f"{API}/osint-lookup", json=data, timeout=300)
        if r.status_code != 200:
            print(f"ERROR {r.status_code}")
            print(r.text[:500])
            return
        result = r.json()
    except Exception as e:
        print(f"FAILED: {e}")
        return

    print(f"\n{'='*60}")
    print("  OSINT INVESTIGATION REPORT")
    print(f"{'='*60}")

    inp = result.get("input", {})
    name = inp.get("name", "") or "unknown"
    print(f"  Subject: {name}")
    if inp.get("context"):         print(f"  Context: {inp['context']}")
    if inp.get("phrase"):          print(f"  Phrase:  {inp['phrase']}")
    if inp.get("links"):           print(f"  Links:   {inp['links']}")
    if inp.get("information_wanted"): print(f"  Wanted:  {inp['information_wanted']}")
    if inp.get("anything_you_have"):  print(f"  Extra:   {inp['anything_you_have']}")
    print()

    goal = result.get("goal_analysis", {})
    if goal:
        print(f"  INVESTIGATION PLAN:")
        print(f"    Goal: {goal.get('goal', 'N/A')}")
        queries = goal.get("search_queries", [])
        if queries:
            print(f"    Search queries:")
            for q in queries:
                print(f"      - {q}")
        dels = goal.get("deliverables", [])
        if dels:
            print(f"    Deliverables:")
            for d in dels:
                print(f"      - {d}")
        print()

    plan = result.get("plan", [])
    if plan:
        print(f"  EXECUTION PLAN ({len(plan)} steps):")
        for p in plan:
            icon = {"search_agent": "🔍", "social_agent": "👤", "analyze_agent": "🧠", "summary_agent": "📋"}.get(p.get("agent", ""), "  ")
            print(f"    {icon} {p.get('name', '?')}")
        print()

    social = result.get("social_profiles", [])
    existing = [p for p in social if p.get("exists")]
    if existing:
        print(f"  SOCIAL MEDIA PROFILES FOUND ({len(existing)} from Maigret scan):")
        for p in existing[:15]:
            print(f"    [{p['platform']}] {p['url']}")
        if len(existing) > 15:
            print(f"    ... and {len(existing)-15} more")
        print()

    maigret = result.get("maigret_searches", [])
    for mr in maigret:
        uname = mr.get("username", "?")
        profiles = mr.get("profiles", {})
        print(f"  MAIGRET SCAN: '{uname}' — {mr.get('profiles_found', 0)} sites found (of {mr.get('total_checked', 0)} checked)")
        for site, info in list(profiles.items())[:8]:
            print(f"    ✓ {info.get('site_name', site):25s} {info.get('url', '')}")
        if len(profiles) > 8:
            print(f"    ... and {len(profiles)-8} more")
        print()

    holehe = result.get("holehe_searches", [])
    for hr in holehe:
        regs = hr.get("registrations", {})
        print(f"  HOLEHE SCAN: '{hr.get('email', '?')}' — {hr.get('registrations_found', 0)} registrations found")
        for site, info in regs.items():
            print(f"    ✓ Registered on {site}")
        print()

    raw = result.get("raw_web_search", [])
    if raw:
        print(f"  RAW WEB RESULTS ({len(raw)}):")
        for i, w in enumerate(raw, 1):
            src = w.get("source", "?")
            title = (w.get("title") or "")[:100]
            pub = w.get("published", "")
            tag = f" [{pub}]" if pub else ""
            print(f"    {i:>2}. [{src}]{tag} {title}")
            url = w.get("url", "")
            if url:
                print(f"        {url}")
        print()

    web = result.get("web_search", [])
    if web:
        print(f"  WEB SEARCH RESULTS ({len(web)}):")
        for i, w in enumerate(web, 1):
            src = w.get("source", "")
            src_tag = f"[{src}]" if src and src != "?" else ""
            title = w.get("title", "") or w.get("snippet", "")[:60]
            print(f"    {i}. {src_tag} {title}")
            if w.get("url"): print(f"       {w['url']}")
        print()

    names = result.get("name_suggestions", [])
    if names:
        print(f"  NAME VARIATIONS / ALIASES ({len(names)}):")
        for n in names:
            print(f"    - {n.get('suggested_name', n.get('name', ''))} ({n.get('type', 'alias')})")
            if n.get("rationale"):
                print(f"      {n['rationale']}")
        print()

    entities = result.get("entities", [])
    if entities:
        print(f"  ENTITIES EXTRACTED ({len(entities)}):")
        for e in entities:
            print(f"    [{e.get('type','?')}] {e.get('name','')} (conf: {e.get('confidence',0)})")
        print()

    sent = result.get("sentiment", {})
    if sent:
        print(f"  SENTIMENT: {sent.get('sentiment', '?')} (confidence: {sent.get('confidence', 0)})")

    cls = result.get("classification", {})
    if cls:
        tags = cls.get("tags", [])
        print(f"  CLASSIFICATION: {cls.get('category', '?')} / {cls.get('subcategory', '')}")
        if tags: print(f"  TAGS: {', '.join(tags[:8])}")
    print()

    inc = result.get("inconsistencies", [])
    if inc:
        print(f"  INCONSISTENCIES DETECTED ({len(inc)}):")
        for i in inc:
            desc = i.get("description", "")
            sev = i.get("severity", "medium")
            print(f"    [{sev}] {desc}")
        print()

    analysis = result.get("llm_analysis", "")
    if analysis:
        print(f"  AI ANALYSIS:")
        for line in analysis.strip().split("\n"):
            print(f"    {line}")
        print()

    lid = result.get("lookup_id", "")
    if lid:
        print(f"  Lookup saved as: {lid}")
    print(f"{'='*60}")

def main():
    show_banner()
    while True:
        try:
            data = collect_input()
            if not data:
                print("Nothing to do. Exiting.")
                break
            run_lookup(data)
            again = input("\nAnother lookup? (y/n): ").strip().lower()
            if again not in ("y", "yes"):
                break
        except KeyboardInterrupt:
            print("\nQuit.")
            break

if __name__ == "__main__":
    main()
