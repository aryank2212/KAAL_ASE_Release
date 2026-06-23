#!/bin/bash
set -e

PROJECT="/mnt/d/BACKUP/KAAL (ASE)"
VENV="$PROJECT/venv"
cd "$PROJECT/services/api"

fuser -k 8000/tcp 2>/dev/null || true
sleep 1

"$VENV/bin/python" -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --log-level warning > /tmp/kaal-api.log 2>&1 &
SERVER_PID=$!

for i in $(seq 1 15); do
    if curl -s http://localhost:8000/health > /dev/null 2>&1; then
        echo "Server ready (attempt $i)"
        break
    fi
    if [ $i -eq 15 ]; then
        echo "Server failed to start after 15 attempts"
        cat /tmp/kaal-api.log
        kill $SERVER_PID 2>/dev/null
        exit 1
    fi
    sleep 2
done

echo "=== 1. Health ==="
curl -s http://localhost:8000/health
echo ""

echo "=== 2. Chat ==="
curl -s -m 120 -X POST http://localhost:8000/api/v1/analysis/chat \
  -H 'Content-Type: application/json' \
  -d '{"prompt":"say hello in one word"}'
echo ""

echo "=== 3. Summarize ==="
curl -s -m 120 -X POST http://localhost:8000/api/v1/analysis/summarize \
  -H 'Content-Type: application/json' \
  -d '{"text":"John Smith was last seen on March 15th 2024 in New York City. He was driving a black Toyota Camry."}'
echo ""

echo "=== 4. Entities ==="
curl -s -m 120 -X POST http://localhost:8000/api/v1/analysis/extract-entities \
  -H 'Content-Type: application/json' \
  -d '{"text":"John Smith called Jane Doe from New York."}'
echo ""

echo "=== 5. Sentiment ==="
curl -s -m 120 -X POST http://localhost:8000/api/v1/analysis/sentiment \
  -H 'Content-Type: application/json' \
  -d '{"text":"The operation was a complete success. All civilians are safe."}'
echo ""

echo "=== 6. Classify ==="
curl -s -m 120 -X POST http://localhost:8000/api/v1/analysis/classify \
  -H 'Content-Type: application/json' \
  -d '{"text":"URGENT: Bomb threat reported at downtown courthouse."}'
echo ""

echo "=== 7. Inconsistencies ==="
curl -s -m 120 -X POST http://localhost:8000/api/v1/analysis/detect-inconsistencies \
  -H 'Content-Type: application/json' \
  -d '{"text":"He said he was at home. GPS shows he was 20 miles away."}'
echo ""

echo "=== 8. Name Suggestions ==="
curl -s -m 120 -X POST http://localhost:8000/api/v1/analysis/name-suggestions \
  -H 'Content-Type: application/json' \
  -d '{"partial_name":"John Sm"}'
echo ""

echo "=== 9. Embeddings ==="
curl -s -m 30 -X POST http://localhost:8000/api/v1/analysis/embeddings \
  -H 'Content-Type: application/json' \
  -d '{"text":"test text"}'
echo ""

kill $SERVER_PID 2>/dev/null
echo ""
echo "=== ALL TESTS DONE ==="
