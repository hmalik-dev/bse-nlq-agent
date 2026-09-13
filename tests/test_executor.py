"""The executor is the latch behind the guard: read-only, bounded, timed out."""

from __future__ import annotations

import logging
import sqlite3
import time
from datetime import date
from pathlib import Path

import pytest

from nlq.agent.errors import DatabaseMissing, QueryFailed, QueryTimeout
from nlq.agent.executor import MAX_RESULT_BYTES, Executor
from nlq.agent.sql_guard import guard
from nlq.db.connection import MAX_COLUMNS, MAX_VALUE_BYTES, open_read_only
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


def test_the_limit_the_guard_appends_actually_bounds_the_query(db_path: Path) -> None:
    # The guard's text and the executor's cap have to agree, so this runs the
    # guard's own output: an appended LIMIT that SQLite ignores would show up
    # here as a full scan reported as truncated.
    guarded = guard("SELECT ticket_id FROM tickets -- every one", max_rows=5)
    result = Executor(db_path, max_rows=1000).run(guarded.sql)
    assert result.row_count == 6
    assert not result.truncated


def test_a_runaway_query_is_stopped_at_the_deadline(db_path: Path) -> None:
    started = time.monotonic()
    with pytest.raises(QueryTimeout):
        Executor(db_path, timeout_ms=100).run(RUNAWAY_SQL)
    assert time.monotonic() - started < 1.0


def test_a_cartesian_join_over_tickets_is_stopped_at_the_deadline(db_path: Path) -> None:
    started = time.monotonic()
    with pytest.raises(QueryTimeout):
        Executor(db_path, timeout_ms=100).run("SELECT COUNT(*) FROM tickets AS a, tickets AS b")
    assert time.monotonic() - started < 1.0


def test_a_cartesian_join_returning_rows_stops_at_the_row_cap(db_path: Path) -> None:
    result = Executor(db_path, max_rows=5).run("SELECT a.ticket_id FROM tickets AS a, tickets AS b")
    assert result.row_count == 5
    assert result.truncated


def test_a_broken_query_stays_repairable_even_past_the_deadline(db_path: Path) -> None:
    # The deadline says whether it interrupted anything; the clock does not. A
    # real SQL error must not be relabeled a timeout, or the repair loop gives
    # up on a query it could have fixed.
    with pytest.raises(QueryFailed) as error:
        Executor(db_path, timeout_ms=0).run("SELECT nonexistent_column FROM tickets")
    assert "nonexistent_column" in error.value.message


def test_rows_that_add_up_past_the_byte_budget_are_refused_rather_than_held_in_memory(
    db_path: Path,
) -> None:
    # Each value stays under SQLite's length limit; together they pass MAX_RESULT_BYTES.
    per_row = MAX_VALUE_BYTES // 4 * 2  # hex() doubles the blob
    rows_needed = MAX_RESULT_BYTES // per_row + 1
    with pytest.raises(QueryFailed) as error:
        Executor(db_path, max_rows=rows_needed + 5).run(
            f"SELECT hex(zeroblob({MAX_VALUE_BYTES // 4})) FROM tickets"
        )
    assert error.value.message.startswith(f"The result is larger than {MAX_RESULT_BYTES} bytes.")


def test_a_value_over_the_length_limit_fails_inside_sqlite_before_python_holds_it(
    db_path: Path,
) -> None:
    started = time.monotonic()
    with pytest.raises(QueryFailed, match="too big"):
        Executor(db_path).run(f"SELECT length(hex(zeroblob({MAX_VALUE_BYTES}))) AS n")
    assert time.monotonic() - started < 1.0


def test_a_value_under_the_length_limit_still_runs(db_path: Path) -> None:
    half = MAX_VALUE_BYTES // 4  # hex() doubles it
    assert Executor(db_path).run(f"SELECT length(hex(zeroblob({half}))) AS n").rows == [[half * 2]]


def test_a_result_wider_than_the_column_limit_is_refused(db_path: Path) -> None:
    columns = ", ".join(f"{n} AS c{n}" for n in range(MAX_COLUMNS + 1))
    with pytest.raises(QueryFailed, match="too many columns"):
        Executor(db_path).run(f"SELECT {columns}")


def test_blobs_come_back_as_text_or_their_repr_never_raw_bytes(db_path: Path) -> None:
    result = Executor(db_path).run(
        "SELECT CAST('Nets' AS BLOB) AS text_blob, X'FF00' AS binary_blob"
    )
    assert result.rows == [["Nets", "b'\\xff\\x00'"]]


def test_a_write_handed_straight_to_the_executor_is_refused(db_path: Path) -> None:
    before = _ticket_count(db_path)
    with pytest.raises(QueryFailed) as error:
        Executor(db_path).run("DELETE FROM tickets")
    assert error.value.repairable
    assert _ticket_count(db_path) == before


def test_the_connection_itself_refuses_a_write_with_the_guard_and_query_only_both_gone(
    db_path: Path,
) -> None:
    before = _ticket_count(db_path)
    connection = open_read_only(db_path)
    try:
        connection.execute(
            "PRAGMA query_only = 0"
        )  # lift the second latch; mode=ro must still hold
        with pytest.raises(sqlite3.OperationalError, match="readonly"):
            connection.execute("DELETE FROM tickets")
    finally:
        connection.close()
    assert _ticket_count(db_path) == before


def test_the_connection_opens_with_query_only_on(db_path: Path) -> None:
    connection = open_read_only(db_path)
    try:
        assert connection.execute("PRAGMA query_only").fetchone()[0] == 1
    finally:
        connection.close()


def test_the_widest_row_sqlite_allows_stays_within_twice_the_result_budget() -> None:
    # The byte budget is counted after SQLite and Python hold a row, and one call
    # over a huge value cannot be interrupted, so the value limit bounds both.
    assert MAX_COLUMNS * MAX_VALUE_BYTES <= 2 * MAX_RESULT_BYTES


@pytest.mark.parametrize("folder", ["a#b", "a?mode=rwc"])
def test_a_database_path_with_uri_characters_still_opens_read_only(
    db_path: Path, tmp_path: Path, folder: str
) -> None:
    copy = tmp_path / folder / "tickets.db"
    copy.parent.mkdir()
    copy.write_bytes(db_path.read_bytes())
    connection = open_read_only(copy)
    try:
        connection.execute("PRAGMA query_only = 0")
        assert connection.execute("SELECT COUNT(*) FROM tickets").fetchone()[0] > 0
        with pytest.raises(sqlite3.OperationalError, match="readonly"):
            connection.execute("DELETE FROM tickets")
    finally:
        connection.close()


def test_a_missing_database_is_reported_from_run_not_from_the_constructor(
    tmp_path: Path,
) -> None:
    executor = Executor(tmp_path / "absent.db")
    with pytest.raises(DatabaseMissing):
        executor.run("SELECT 1")


def test_a_missing_database_names_the_seed_command_and_logs_the_path_only(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    missing = tmp_path / "absent.db"
    with caplog.at_level(logging.WARNING, logger="nlq"), pytest.raises(DatabaseMissing) as raised:
        Executor(missing).run("SELECT 1")

    assert raised.value.message == "No database found. Create it with: uv run python -m nlq.db.seed"
    assert str(missing) not in raised.value.message
    logged = [record for record in caplog.records if record.name == "nlq"]
    assert len(logged) == 1
    assert logged[0].levelno == logging.WARNING
    assert str(missing) in logged[0].getMessage()


def test_a_broken_query_carries_sqlites_own_message(db_path: Path) -> None:
    with pytest.raises(QueryFailed) as error:
        Executor(db_path).run("SELECT nonexistent_column FROM tickets")
    assert "nonexistent_column" in error.value.message
