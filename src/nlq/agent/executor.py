"""The second line of defence: run guarded SQL, bounded in rows and in time."""

from __future__ import annotations

import sqlite3
import time
from collections.abc import Callable
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
        deadline = started + self.timeout_ms / 1000
        connection = open_read_only(self.path)
        try:
            connection.set_progress_handler(_deadline_handler(deadline), PROGRESS_INSTRUCTIONS)
            columns, fetched = _fetch(connection, sql, self.max_rows + 1)
        except sqlite3.Error as error:
            if time.monotonic() >= deadline:
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


def _deadline_handler(deadline: float) -> Callable[[], int]:
    """A progress callback that aborts the query once `deadline` has passed.

    SQLite has no statement timeout. Returning non-zero from the progress
    handler is the interrupt it does offer, and it surfaces as an
    `OperationalError` reading "interrupted".
    """

    def handler() -> int:
        return 1 if time.monotonic() >= deadline else 0

    return handler


def _fetch(connection: sqlite3.Connection, sql: str, limit: int) -> tuple[list[str], list[tuple]]:
    """Run `sql` and read back at most `limit` rows with their column names."""
    cursor = connection.execute(sql)
    try:
        rows = cursor.fetchmany(limit)
        columns = [description[0] for description in cursor.description or ()]
        return columns, rows
    finally:
        cursor.close()


def _json_safe(value: object) -> object:
    """Coerce a SQLite value into something the API can serialise."""
    if isinstance(value, bytes):
        try:
            return value.decode("utf-8")
        except UnicodeDecodeError:
            return repr(value)
    return value
