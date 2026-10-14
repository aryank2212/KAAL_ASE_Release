#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$ROOT/.env"

if [[ -e "$ENV_FILE" ]]; then
  echo "Refusing to overwrite existing $ENV_FILE" >&2
  exit 1
fi
if ! command -v openssl >/dev/null 2>&1; then
  echo "OpenSSL is required to generate secrets." >&2
  exit 1
fi

umask 077
cat > "$ENV_FILE" <<EOF
KAAL_API_KEY=$(openssl rand -hex 32)
POSTGRES_PASSWORD=$(openssl rand -hex 32)
NEO4J_PASSWORD=$(openssl rand -hex 32)
MINIO_ROOT_USER=kaal-minio-admin
MINIO_ROOT_PASSWORD=$(openssl rand -hex 32)
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
OLLAMA_MODEL=gemma2:2b
OLLAMA_EMBED_MODEL=nomic-embed-text
WORKER_POLL_SECONDS=2
EOF
chmod 600 "$ENV_FILE"
echo "Created $ENV_FILE with fresh secrets (permissions: 600). Keep it private."
