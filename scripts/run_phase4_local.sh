#!/usr/bin/env bash
set -euo pipefail

API_HOST="${API_HOST:-0.0.0.0}"
API_PORT="${API_PORT:-8000}"
WEB_PORT="${WEB_PORT:-3000}"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cd "$ROOT_DIR"

echo "Starting FastAPI on ${API_HOST}:${API_PORT}"
"${PYTHON_BIN:-.venv/bin/python}" -m uvicorn deploy_api:app --host "$API_HOST" --port "$API_PORT" &
API_PID=$!
cleanup() {
  kill "$API_PID" 2>/dev/null || true
}
trap cleanup EXIT

for _ in $(seq 1 60); do
  if curl -fsS "http://127.0.0.1:${API_PORT}/api/health" >/dev/null; then
    break
  fi
  sleep 1
done

if ! curl -fsS "http://127.0.0.1:${API_PORT}/api/health" >/dev/null; then
  echo "FastAPI did not become healthy" >&2
  exit 1
fi

echo "FastAPI healthy. Running Phase 4 e2e..."
API_BASE_URL="http://127.0.0.1:${API_PORT}" "${PYTHON_BIN:-.venv/bin/python}" scripts/e2e_phase4_api.py

echo "To run Web v2 in another shell:"
echo "  cd web && NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:${API_PORT} npm run dev -- --port ${WEB_PORT}"
