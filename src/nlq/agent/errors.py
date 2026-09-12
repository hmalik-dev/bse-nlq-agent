"""The failures the agent can produce, each with a code the API and UI show.

Repairable errors are the ones worth sending back to the model: it wrote
something the database rejected and can try again. The rest are final.
"""

from __future__ import annotations


class NlqError(Exception):
    """Base class for every failure the agent reports to its caller."""

    code: str = "nlq_error"
    repairable: bool = False

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class UnsafeSql(NlqError):
    """The statement was write-shaped or otherwise out of bounds. Never retried."""

    code = "unsafe_sql"


class InvalidSql(NlqError):
    """The statement does not parse, or names a table the schema does not have."""

    code = "invalid_sql"
    repairable = True


class QueryFailed(NlqError):
    """SQLite refused to run the statement; `message` is SQLite's own wording."""

    code = "query_failed"
    repairable = True


class QueryTimeout(NlqError):
    """The query ran past its deadline and was interrupted."""

    code = "query_timeout"


class DatabaseMissing(NlqError):
    """There is no database file to read. Run the seed."""

    code = "database_missing"
