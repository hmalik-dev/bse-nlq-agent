#!/usr/bin/env bash
# Seed the database when the container has none (or NLQ_RESEED=1), then serve.
# NLQ_SEED_SCALE shrinks the seed (the hosted demo uses 0.2); full scale is the default.
# The dataset is generated relative to today, which is why it is built here
# rather than baked into the image.
set -euo pipefail

export NLQ_DATABASE_PATH="${NLQ_DATABASE_PATH:-/data/tickets.db}"

if [[ ! -f "$NLQ_DATABASE_PATH" || "${NLQ_RESEED:-0}" == "1" ]]; then
  data_dir="$(dirname "$NLQ_DATABASE_PATH")"
  if [[ ! -w "$data_dir" ]]; then
    # A volume created by an older image, which ran as root, stays root-owned.
    echo "Cannot write $data_dir as $(id -un). If it is a volume from an older image," >&2
    echo "remove it (docker volume rm bse-data) and start again." >&2
    exit 1
  fi
  scale="${NLQ_SEED_SCALE:-1.0}"
  echo "Seeding the database at $NLQ_DATABASE_PATH at scale $scale (about a minute at 1.0) ..."
  python -m nlq.db.seed --scale "$scale"
  echo "Seed finished. Starting the server."
else
  echo "Using the existing database at $NLQ_DATABASE_PATH (set NLQ_RESEED=1 to rebuild it)."
fi

exec uvicorn nlq.api:app --host 0.0.0.0 --port "${PORT:-8000}"
