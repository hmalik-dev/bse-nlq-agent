"""The only way the agent reaches the database: one read-only connection."""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

from nlq.agent.errors import DatabaseMissing

# The caller sees this sentence; the path it was looking at goes to the log only.
MISSING_MESSAGE = "No database found. Create it with: uv run python -m nlq.db.seed"

logger = logging.getLogger("nlq")


def open_read_only(path: Path) -> sqlite3.Connection:
    """Open `path` for reading and nothing else.

    The `mode=ro` URI is the guarantee; `PRAGMA query_only` is the second latch,
    so a write is refused by SQLite itself rather than by the SQL guard alone.
    Read-only mode will not create a missing file, and the error SQLite raises
    for one ("unable to open database file") says nothing useful, so the missing
    file is reported here instead.
    """
    if not path.is_file():
        logger.warning("No database file at %s", path)
        raise DatabaseMissing(MISSING_MESSAGE)
    connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    connection.execute("PRAGMA query_only = 1")
    return connection
