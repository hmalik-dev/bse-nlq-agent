"""The agent core: guard, execute, and the errors both raise.

Nothing in this package imports the API or the interface. Every caller goes
through these types.
"""

from nlq.agent.errors import (
    DatabaseMissing,
    InvalidSql,
    NlqError,
    QueryFailed,
    QueryTimeout,
    UnsafeSql,
)
from nlq.agent.executor import Executor, QueryResult
from nlq.agent.sql_guard import GuardedSql, guard

__all__ = [
    "DatabaseMissing",
    "Executor",
    "GuardedSql",
    "InvalidSql",
    "NlqError",
    "QueryFailed",
    "QueryResult",
    "QueryTimeout",
    "UnsafeSql",
    "guard",
]
