"""The executor is the latch behind the guard: read-only, row-capped, timed out."""

from __future__ import annotations

import sqlite3
import time
from datetime import date
from pathlib import Path

import pytest

from nlq.agent.errors import DatabaseMissing, QueryFailed, QueryTimeout
from nlq.agent.executor import Executor
from nlq.db.seed import seed_database

TODAY = date(2026, 9, 11)
SCALE = 0.005

# A query with no exit condition: the only thing that can stop it is the deadline.
RUNAWAY_SQL = (
    "WITH RECURSIVE c(x) AS (SELECT 1 UNION ALL SELECT x + 1 FROM c) SELECT COUNT(*) FROM c"
)


@pytest.fixture(scope="module")
def db_path(tmp_path_factory: pytest.TempPathFactory) -> Path:
    path = tmp_path_factory.mktemp("data") / "tickets.db"
    seed_database(path, today=TODAY, scale=SCALE)
    return path


def _ticket_count(path: Path) -> int:
    conn = sqlite3.connect(path)
    try:
        return conn.execute("SELECT COUNT(*) FROM tickets").fetchone()[0]
    finally:
        conn.close()


def test_a_read_returns_columns_rows_and_elapsed_time(db_path: Path) -> None:
    result = Executor(db_path).run("SELECT name, category FROM events LIMIT 3")
    assert result.columns == ["name", "category"]
    assert result.row_count == len(result.rows) == 3
    assert all(isinstance(row[0], str) for row in result.rows)
    assert not result.truncated
    assert result.elapsed_ms >= 0


def test_the_row_cap_truncates_and_says_so(db_path: Path) -> None:
    result = Executor(db_path, max_rows=5).run("SELECT ticket_id FROM tickets")
    assert result.row_count == 5
    assert len(result.rows) == 5
    assert result.truncated


def test_a_runaway_query_is_stopped_at_the_deadline(db_path: Path) -> None:
    started = time.monotonic()
    with pytest.raises(QueryTimeout):
        Executor(db_path, timeout_ms=100).run(RUNAWAY_SQL)
    assert time.monotonic() - started < 1.0


def test_a_write_handed_straight_to_the_executor_is_refused(db_path: Path) -> None:
    before = _ticket_count(db_path)
    with pytest.raises(QueryFailed) as error:
        Executor(db_path).run("DELETE FROM tickets")
    assert error.value.repairable
    assert _ticket_count(db_path) == before


def test_a_missing_database_is_reported_from_run_not_from_the_constructor(
    tmp_path: Path,
) -> None:
    executor = Executor(tmp_path / "absent.db")
    with pytest.raises(DatabaseMissing):
        executor.run("SELECT 1")


def test_a_broken_query_carries_sqlites_own_message(db_path: Path) -> None:
    with pytest.raises(QueryFailed) as error:
        Executor(db_path).run("SELECT nonexistent_column FROM tickets")
    assert "nonexistent_column" in error.value.message
