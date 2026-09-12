"""The second line of defence: run guarded SQL, bounded in rows, bytes and time."""

from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path

from nlq.agent.errors import QueryFailed, QueryTimeout
from nlq.config import max_rows as configured_max_rows
from nlq.config import query_timeout_ms as configured_timeout_ms
from nlq.db.connection import open_read_only

# How often SQLite calls the progress handler, in virtual machine instructions.
# Small enough that a runaway query is stopped promptly, large enough that the
# callback costs nothing on a query that returns quickly.
PROGRESS_INSTRUCTIONS = 1000

# The row cap bounds how many rows come back, not how large one row is:
# `SELECT hex(zeroblob(20000000))` returns a handful of rows, finishes inside
# the deadline, and still exhausts memory. This bounds the result in bytes too.
MAX_RESULT_BYTES = 8_000_000
_ASSUMED_VALUE_BYTES = 8  # numbers and NULLs, which are not worth measuring


@dataclass(frozen=True)
class QueryResult:
    """One query's rows, already bounded and JSON-safe."""

    columns: list[str]
    rows: list[list[object]]
    row_count: int
    truncated: bool
    elapsed_ms: int


class Executor:
    """Runs one guarded statement at a time against a read-only database."""

    def __init__(
        self,
        path: Path,
        *,
        timeout_ms: int | None = None,
        max_rows: int | None = None,
    ) -> None:
        self.path = path
        self.timeout_ms = configured_timeout_ms() if timeout_ms is None else timeout_ms
        self.max_rows = configured_max_rows() if max_rows is None else max_rows

    def run(self, sql: str) -> QueryResult:
        """Execute `sql` and return at most `max_rows` rows.

        A fresh connection is opened per call and closed again: a `sqlite3`
        connection belongs to the thread that created it, and the API runs this
        on FastAPI's worker threads. It also means a missing database is
        reported from here rather than from the constructor.
        """
        started = time.monotonic()
        deadline = _Deadline(self.timeout_ms)
        connection = open_read_only(self.path)
        try:
            connection.set_progress_handler(deadline, PROGRESS_INSTRUCTIONS)
            columns, fetched = _fetch(connection, sql, self.max_rows + 1)
        except sqlite3.Error as error:
            # Ask the deadline, not the clock: a query that fails for its own
            # reasons after the deadline has passed is still a QueryFailed, and
            # the repair loop needs that distinction to know it may retry.
            if deadline.expired:
                raise QueryTimeout(
                    f"The query ran longer than {self.timeout_ms} ms and was stopped."
                ) from error
            raise QueryFailed(str(error)) from error
        finally:
            connection.close()

        truncated = len(fetched) > self.max_rows
        rows = [[_json_safe(value) for value in row] for row in fetched[: self.max_rows]]
        elapsed_ms = int((time.monotonic() - started) * 1000)
        return QueryResult(
            columns=columns,
            rows=rows,
            row_count=len(rows),
            truncated=truncated,
            elapsed_ms=elapsed_ms,
        )


class _Deadline:
    """A progress callback that aborts the query once its deadline has passed.

    SQLite has no statement timeout: `busy_timeout` only covers lock contention,
    and a runaway recursive CTE holds no lock. Returning non-zero from the
    progress handler is the interrupt SQLite does offer. The callback records
    that it fired, so an interrupt is told apart from an unrelated SQLite error
    that merely happened to arrive after the deadline.
    """

    def __init__(self, timeout_ms: int) -> None:
        self.at = time.monotonic() + timeout_ms / 1000
        self.expired = False

    def __call__(self) -> int:
        if time.monotonic() < self.at:
            return 0
        self.expired = True
        return 1


def _fetch(connection: sqlite3.Connection, sql: str, limit: int) -> tuple[list[str], list[tuple]]:
    """Run `sql` and read back at most `limit` rows, within the byte budget."""
    cursor = connection.execute(sql)
    try:
        rows: list[tuple] = []
        remaining_bytes = MAX_RESULT_BYTES
        for row in cursor:
            remaining_bytes -= sum(_value_bytes(value) for value in row)
            if remaining_bytes < 0:
                raise QueryFailed(
                    f"The result is larger than {MAX_RESULT_BYTES} bytes. "
                    "Select fewer columns, or aggregate."
                )
            rows.append(row)
            if len(rows) == limit:
                break
        return [description[0] for description in cursor.description or ()], rows
    finally:
        cursor.close()


def _value_bytes(value: object) -> int:
    """Roughly how much memory one cell holds."""
    if isinstance(value, (str, bytes)):
        return len(value)
    return _ASSUMED_VALUE_BYTES


def _json_safe(value: object) -> object:
    """Coerce a SQLite value into something the API can serialise."""
    if isinstance(value, bytes):
        try:
            return value.decode("utf-8")
        except UnicodeDecodeError:
            return repr(value)
    return value
