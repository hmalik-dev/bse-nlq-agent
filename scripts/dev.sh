#!/usr/bin/env bash
# One command from a clone to the app in a browser: install what is missing,
# seed on first run only, start the API on :8000, then the Vite dev server on
# :4000, which opens the browser and proxies /api to the API. Ctrl+C stops both.
# Stops before anything runs when there is no API key. Run as `npm run dev`.
set -euo pipefail
cd "$(dirname "$0")/.."

API_PORT=8000
UI_PORT=4000
READY_TIMEOUT_S=30
NODE_MAJOR_REQUIRED=24 # the major CI uses (.github/workflows/ci.yml)

# Name a missing tool and how to get it, before anything runs.
require() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "$1 is not installed: $2" >&2
    exit 1
  fi
}
require uv "curl -LsSf https://astral.sh/uv/install.sh | sh"
require node "install Node $NODE_MAJOR_REQUIRED from https://nodejs.org/en/download"
require npm "it ships with Node: https://nodejs.org/en/download"
node_version=$(node --version)
node_major=${node_version#v}
node_major=${node_major%%.*}
if [[ ! "$node_major" =~ ^[0-9]+$ ]] || ((node_major < NODE_MAJOR_REQUIRED)); then
  echo "Node $NODE_MAJOR_REQUIRED or newer is required; found $node_version: https://nodejs.org/en/download" >&2
  exit 1
fi

source scripts/require-key.sh

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
