#!/usr/bin/env bash
# Prove the local path end to end: install, build the interface, seed a
# temporary database, start the server, and check that one question is
# answered. Uses the fake agent when there is no API key, the real one when
# there is. Exit 0 means the README's instructions work on this machine.
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

# The key and the fake flag may each be in the shell or in .env (the app reads
# .env itself). The banner says which agent the server will actually use.
in_env() { grep -qE "^$1=$2\$" .env 2>/dev/null; }
if [[ "${NLQ_FAKE_AGENT:-}" == 1 ]] || in_env NLQ_FAKE_AGENT 1; then
  echo "NLQ_FAKE_AGENT=1: running against the fake agent."
elif [[ -z "${ANTHROPIC_API_KEY:-}" ]] && ! in_env ANTHROPIC_API_KEY '.+'; then
  export NLQ_FAKE_AGENT=1
  echo "ANTHROPIC_API_KEY is not set: running against the fake agent."
else
  echo "ANTHROPIC_API_KEY is set: running against the real agent."
fi

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
