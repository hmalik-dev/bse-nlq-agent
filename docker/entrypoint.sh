#!/usr/bin/env bash
# Seed the database when the container has none (or NLQ_RESEED=1), then serve.
# The dataset is generated relative to today, which is why it is built here
# rather than baked into the image.
set -euo pipefail

export NLQ_DATABASE_PATH="${NLQ_DATABASE_PATH:-/data/tickets.db}"

if [[ ! -f "$NLQ_DATABASE_PATH" || "${NLQ_RESEED:-0}" == "1" ]]; then
  echo "Seeding the database at $NLQ_DATABASE_PATH (about a minute) ..."
  python -m nlq.db.seed
  echo "Seed finished. Starting the server."
else
  echo "Using the existing database at $NLQ_DATABASE_PATH (set NLQ_RESEED=1 to rebuild it)."
fi

exec uvicorn nlq.api:app --host 0.0.0.0 --port "${PORT:-8000}"
