#!/usr/bin/env bash
set -euo pipefail

PROJECT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"
PORT="${PORT:-8000}"

if [[ -f "$PROJECT/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$PROJECT/.env"
  set +a
fi

: "${KAAL_API_KEY:?Set KAAL_API_KEY in .env (run ./scripts/init_env.sh)}"
: "${POSTGRES_PASSWORD:?Set POSTGRES_PASSWORD in .env}"
export DATABASE_URL="${DATABASE_URL:-postgresql+psycopg://kaal:${POSTGRES_PASSWORD}@127.0.0.1:5432/kaal_ase}"

cd "$PROJECT/services/api"
"$PYTHON_BIN" -m uvicorn app.main:app --host 127.0.0.1 --port "$PORT" --log-level warning >/tmp/kaal-api.log 2>&1 &
SERVER_PID=$!
cleanup() { kill "$SERVER_PID" 2>/dev/null || true; }
trap cleanup EXIT INT TERM

for i in $(seq 1 20); do
  if curl -fsS "http://127.0.0.1:$PORT/health" >/dev/null 2>&1; then
    echo "Server ready (attempt $i)"
    break
  fi
  if ! kill -0 "$SERVER_PID" 2>/dev/null; then
    echo "Server exited during startup"
    cat /tmp/kaal-api.log
    exit 1
  fi
  if [[ "$i" -eq 20 ]]; then
    echo "Server failed to start"
    cat /tmp/kaal-api.log
    exit 1
  fi
  sleep 1
done

api() {
  curl -fsS --max-time 120 "http://127.0.0.1:$PORT$1" \
    -H "X-API-Key: $KAAL_API_KEY" \
    -H 'Content-Type: application/json' \
    -d "$2"
  echo
}

echo "=== 1. Health ==="
curl -fsS "http://127.0.0.1:$PORT/health"
echo

echo "=== 2. Chat ==="
api "/api/v1/analysis/chat" '{"prompt":"say hello in one word"}'

echo "=== 3. Summarize ==="
api "/api/v1/analysis/summarize" '{"text":"A fictional test record for API validation."}'

echo "=== 4. Entities ==="
api "/api/v1/analysis/extract-entities" '{"text":"Fictional Example called Sample Person from Sample City."}'

echo "=== 5. Sentiment ==="
api "/api/v1/analysis/sentiment" '{"text":"The test completed successfully."}'

echo "=== 6. Classify ==="
api "/api/v1/analysis/classify" '{"text":"A sample fictional report used for testing."}'

echo "=== 7. Inconsistencies ==="
api "/api/v1/analysis/detect-inconsistencies" '{"text":"The test record contains two intentionally conflicting fictional statements."}'

echo "=== 8. Name Suggestions ==="
api "/api/v1/analysis/name-suggestions" '{"partial_name":"Sample Pers"}'

echo "=== 9. Embeddings ==="
api "/api/v1/analysis/embeddings" '{"text":"test text"}'

echo "=== API smoke tests completed ==="
