#!/usr/bin/env bash
# Prove the local path end to end: install, build the interface, seed a
# temporary database, start the server, and check that one question is
# answered by the real agent (one question, about $0.02). Stops before anything
# runs when there is no API key. Exit 0 means the README's instructions work on this machine.
set -euo pipefail
cd "$(dirname "$0")/.."

PORT=18000
BASE_URL="http://127.0.0.1:$PORT"
READY_TIMEOUT_S=60
QUESTION="Top 5 event categories by total revenue"
export NLQ_DATABASE_PATH="data/smoke-$$.db"

SERVER_PID=""
cleanup() {
  if [[ -n "$SERVER_PID" ]]; then
    kill "$SERVER_PID" 2>/dev/null || true
    wait "$SERVER_PID" 2>/dev/null || true
  fi
  rm -f "$NLQ_DATABASE_PATH"
}
trap cleanup EXIT

source scripts/require-key.sh

echo "==> uv sync"
uv sync
echo "==> npm ci"
npm ci
echo "==> npm run -w web build"
npm run -w web build
echo "==> seeding a temporary database at $NLQ_DATABASE_PATH"
uv run python -m nlq.db.seed

echo "==> starting the server on port $PORT"
uv run uvicorn nlq.api:app --port "$PORT" &
SERVER_PID=$!

ready=0
for _ in $(seq 1 "$READY_TIMEOUT_S"); do
  if curl -fsS "$BASE_URL/api/health" 2>/dev/null | grep -q '"database":true'; then
    ready=1
    break
  fi
  sleep 1
done
if [[ "$ready" != 1 ]]; then
  echo "FAIL: /api/health did not report database: true within ${READY_TIMEOUT_S}s"
  exit 1
fi
echo "==> /api/health reports database: true"

examples=$(curl -fsS "$BASE_URL/api/examples")
count=$(uv run python -c 'import json, sys; print(len(json.load(sys.stdin)))' <<<"$examples")
if [[ "$count" != 6 ]]; then
  echo "FAIL: /api/examples returned $count entries, expected 6"
  exit 1
fi
echo "==> /api/examples returns 6 entries"

body=$(uv run python -c 'import json, sys; print(json.dumps({"question": sys.argv[1]}))' "$QUESTION")
result=$(curl -fsS -H 'Content-Type: application/json' -d "$body" "$BASE_URL/api/ask")
status=$(uv run python -c 'import json, sys; print(json.load(sys.stdin)["status"])' <<<"$result")
if [[ "$status" != answered ]]; then
  echo "FAIL: POST /api/ask returned status $status, expected answered"
  echo "$result"
  exit 1
fi
answer=$(uv run python -c 'import json, sys; print(json.load(sys.stdin)["answer"])' <<<"$result")
echo "==> POST /api/ask answered: $answer"
echo "SMOKE PASSED"
