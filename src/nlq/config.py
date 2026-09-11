"""Filesystem paths and environment-driven settings.

Secrets are only ever read from the environment, never hardcoded.
"""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_DIR.parents[1]

SCHEMA_PATH = PACKAGE_DIR / "db" / "schema.sql"
DICTIONARY_PATH = PACKAGE_DIR / "db" / "dictionary.yaml"
DATABASE_PATH = PROJECT_ROOT / "data" / "tickets.db"


def today() -> date:
    """The date the agent treats as "now" when resolving relative wording.

    NLQ_TODAY pins it so evaluation runs are reproducible; unset means the real
    current date.
    """
    pinned = os.environ.get("NLQ_TODAY", "").strip()
    if not pinned:
        return date.today()
    return date.fromisoformat(pinned)
