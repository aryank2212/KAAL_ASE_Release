# KAAL-ASE — The All Seeing Eye

KAAL-ASE is an OSINT research and evidence-management project built around a Python/FastAPI API, public-source search adapters, local Ollama analysis, and structured case/evidence records.

> Responsible use: Use this tool only for lawful, authorized research. Prefer public-interest and consent-based investigations. Do not use it to stalk, harass, dox, discriminate against, or infer sensitive traits about private people. Treat generated matches as unverified leads, not facts.

## Status

The API supports case/profile/evidence records, LLM-assisted analysis, and a saved lookup store. The vector-search and graph endpoints are currently placeholders. The frontend is represented by a Git submodule entry that is not configured in this repository, so the web Compose profile remains opt-in.

## Requirements

- Python 3.10+
- Docker Engine and Docker Compose plugin
- Ollama on the host, with a chat model and nomic-embed-text available

Pull the default models on the host:

    ollama pull gemma2:2b
    ollama pull nomic-embed-text

## Secure local setup

Generate a private .env with fresh secrets:

    ./scripts/init_env.sh

The script refuses to overwrite an existing .env and restricts it to the current user. Keep that file private. If you prefer manual setup, copy .env.example to .env and set each required secret to a strong, random, URL-safe value; openssl rand -hex 32 is suitable.

Start the API and infrastructure:

    docker compose up --build -d
    docker compose ps
    docker compose logs -f api

Start the persistent ingestion worker as well:

    docker compose --profile worker up --build -d

By default, published service ports bind to 127.0.0.1 only. Do not change them to public interfaces without adding an appropriate deployment boundary, TLS, a secrets manager, and stronger user-level access control.

The API uses X-API-Key for every /api/* endpoint. Health and documentation endpoints are public; data routes fail with HTTP 503 when KAAL_API_KEY is missing and HTTP 401 for a missing or incorrect key.

Example:

    set -a
    source .env
    set +a
    curl -sS http://127.0.0.1:8000/api/v1/search \
      -H "Content-Type: application/json" \
      -H "X-API-Key: $KAAL_API_KEY" \
      -d '{"case_id":"00000000-0000-0000-0000-000000000000","query":"example"}'

The example case ID is deliberately synthetic. Use a case created in your own local instance.

## Direct Python development

Install the dependencies:

    python -m venv .venv
    source .venv/bin/activate
    pip install -r services/api/requirements.txt

For direct execution, export a valid DATABASE_URL for your local PostgreSQL instance and the same KAAL_API_KEY you use for the CLI scripts. Then:

    cd services/api
    uvicorn app.main:app --host 127.0.0.1 --port 8000

On Windows, activate the virtual environment using its Scripts activation command.

The Maigret database is resolved from the installed package by default. Set MAIGRET_DB_PATH if you maintain a separate data.json file. Set KAAL_LOOKUP_DIR to change where runtime investigation JSON files are stored.

## Important operational notes

- Generated lookup records are runtime data and must not be committed. They are ignored under data/; keep backups in private storage.
- Removing leaked files from the current tree does not erase them from Git history, forks, caches, or existing clones. Follow docs/SECURITY_CLEANUP.md to complete history cleanup and rotate any exposed credentials.
- Outbound page fetching validates HTTP(S) destinations, blocks non-public IP ranges, and revalidates each redirect. Keep network-level egress controls enabled in deployed environments as an additional SSRF defense.
- A shared API key is a basic perimeter control, not multi-user authentication or case-level authorization. Do not expose KAAL to the internet until per-user identity, roles, case membership checks, audit review, and a deployment security review are implemented.
- The current search and graph API routes return placeholders. Do not treat their presence as evidence that vector or graph search is implemented.
- API and database schema changes currently need to be coordinated carefully; use versioned migrations before operational deployment.

## Project layout

- services/api/: FastAPI API, analysis, models, extraction, and ingestion worker
- infra/postgres/: initial PostgreSQL schema
- api/openapi.yaml: API contract
- intelligent_recon.py, lookup_name.py, recon_loop.py: CLI entry points
- data/, reports/: local runtime outputs (ignored)

## License

See the repository license file if present. Third-party tools retain their own licenses.
