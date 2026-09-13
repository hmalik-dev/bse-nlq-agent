#!/usr/bin/env bash
# One command from a clone to the app in a browser: install what is missing,
# seed on first run only, start the API on :8000, then the Vite dev server on
# :4000, which opens the browser and proxies /api to the API. Ctrl+C stops both.
# Uses the fake agent when there is no API key. Run as `npm run dev`.
set -euo pipefail
cd "$(dirname "$0")/.."

API_PORT=8000
UI_PORT=4000
READY_TIMEOUT_S=30

# The key and the fake flag may each be in the shell or in .env (the app reads
# .env itself).
in_env() { grep -qE "^$1=$2\$" .env 2>/dev/null; }
if [[ "${NLQ_FAKE_AGENT:-}" != 1 ]] && ! in_env NLQ_FAKE_AGENT 1 \
  && [[ -z "${ANTHROPIC_API_KEY:-}" ]] && ! in_env ANTHROPIC_API_KEY '.+'; then
  export NLQ_FAKE_AGENT=1
  echo "ANTHROPIC_API_KEY is not set: using the fake agent (canned answers)."
fi

echo "==> uv sync"
uv sync
if [[ ! -d node_modules ]]; then
  echo "==> npm ci"
  npm ci
fi

database=$(uv run python -c 'from nlq.config import DATABASE_PATH; print(DATABASE_PATH)')
if [[ -f "$database" ]]; then
  echo "==> using the existing database at $database"
else
  echo "==> seeding $database at scale 0.2 (first run only)"
  uv run python -m nlq.db.seed --scale 0.2
fi

API_PID=""
stop_api() {
  if [[ -n "$API_PID" ]]; then
    kill "$API_PID" 2>/dev/null || true
    wait "$API_PID" 2>/dev/null || true
  fi
}
trap stop_api EXIT

# A server already on the port would answer the health check in place of ours.
if (exec 3<>"/dev/tcp/127.0.0.1/$API_PORT") 2>/dev/null; then
  echo "FAIL: port $API_PORT is already in use (lsof -i :$API_PORT)." >&2
  exit 1
fi
echo "==> starting the API on port $API_PORT"
uv run uvicorn nlq.api:app --reload --host 127.0.0.1 --port "$API_PORT" &
API_PID=$!

ready=0
for _ in $(seq 1 "$READY_TIMEOUT_S"); do
  if ! kill -0 "$API_PID" 2>/dev/null; then
    API_PID=""
    echo "FAIL: the API did not start. Is port $API_PORT already in use? (lsof -i :$API_PORT)" >&2
    exit 1
  fi
  if curl -fsS "http://127.0.0.1:$API_PORT/api/health" 2>/dev/null | grep -q '"database":true'; then
    ready=1
    break
  fi
  sleep 1
done
if [[ "$ready" != 1 ]]; then
  echo "FAIL: /api/health on port $API_PORT did not report database: true within ${READY_TIMEOUT_S}s" >&2
  exit 1
fi

echo "==> opening http://localhost:$UI_PORT (Ctrl+C stops everything)"
npm run -w web dev -- --port "$UI_PORT" --strictPort --open
