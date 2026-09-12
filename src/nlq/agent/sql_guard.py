"""The first line of defence: only one bounded read ever reaches the database.

The model is asked for a single SELECT, but asking is not a guarantee. Every
statement is parsed and inspected before it is run, and whatever the model
wrote, only a read over a known table with a row limit survives.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass

import sqlglot
from sqlglot import exp
from sqlglot.optimizer.scope import traverse_scope

from nlq.agent.errors import InvalidSql, UnsafeSql
from nlq.config import SCHEMA_PATH

DIALECT = "sqlite"

# Statement shapes that write, reshape, or reach outside the database. One of
# these anywhere in the tree - in a CTE, in a subquery - rejects the whole text.
WRITE_NODES = (
    exp.Insert,
    exp.Update,
    exp.Delete,
    exp.Drop,
    exp.Create,
    exp.Alter,
    exp.Command,
    exp.Pragma,
    exp.Attach,
    exp.Detach,
    exp.Transaction,
)
# `SetOperation` is the base of UNION, EXCEPT and INTERSECT, which are all reads.
READ_ROOTS = (exp.Select, exp.SetOperation)

# SQLite functions that touch the filesystem or load code.
BANNED_FUNCTIONS = frozenset({"load_extension", "readfile", "writefile", "edit", "fts3_tokenizer"})

_CREATE_TABLE = re.compile(r"CREATE\s+TABLE\s+([A-Za-z_][A-Za-z0-9_]*)", re.IGNORECASE)


def _allowed_tables() -> frozenset[str]:
    """The table names the schema declares, read once at import.

    Built from `schema.sql` rather than listed here, so a table added to the
    schema is queryable without a second edit and can never drift out of step.
    """
    schema = SCHEMA_PATH.read_text(encoding="utf-8")
    return frozenset(name.lower() for name in _CREATE_TABLE.findall(schema))


ALLOWED_TABLES = _allowed_tables()


@dataclass(frozen=True)
class GuardedSql:
    """SQL that passed the guard, with the row limit applied."""

    sql: str
    tables: list[str]


def guard(sql: str, *, max_rows: int) -> GuardedSql:
    """Accept exactly one read statement, bounded to `max_rows` + 1 rows.

    Raises `UnsafeSql` for anything write-shaped, which is final, and
    `InvalidSql` for text that does not parse or names an unknown table, which
    is repairable: the model gets the message back and tries again.
    """
    statement = _parse_single_statement(sql)
    _reject_writes(statement)
    tables = _referenced_tables(statement)
    return GuardedSql(sql=_apply_limit(sql, statement, max_rows), tables=tables)


def _parse_single_statement(sql: str) -> exp.Expression:
    """Parse `sql` and insist it is one statement with a read at its root."""
    try:
        statements = sqlglot.parse(sql, dialect=DIALECT)
    # SqlglotError, not ParseError: an unterminated comment or string fails in
    # the tokenizer, and a TokenError is not a ParseError.
    except sqlglot.errors.SqlglotError as error:
        raise InvalidSql(f"That SQL does not parse: {error}") from error
    if len(statements) != 1 or statements[0] is None:
        raise UnsafeSql("Only one statement may be run at a time.")
    statement = statements[0]
    if not isinstance(statement, READ_ROOTS):
        raise UnsafeSql("Only SELECT statements are allowed.")
    return statement


def _reject_writes(statement: exp.Expression) -> None:
    """Refuse any node that writes, reshapes the database, or reaches outside it."""
    for node in statement.walk():
        if isinstance(node, WRITE_NODES):
            raise UnsafeSql(f"{node.key.upper()} is not allowed; this agent only reads.")
        if isinstance(node, exp.Select) and node.args.get("into"):
            raise UnsafeSql("SELECT ... INTO writes a table and is not allowed.")
        name = _function_name(node)
        if name in BANNED_FUNCTIONS:
            raise UnsafeSql(f"The function {name} is not allowed.")


def _function_name(node: exp.Expression) -> str | None:
    """The lowercased name of a function call, or None for anything else.

    `.name` rather than `str(node.this)`, so a quoted call - SQLite accepts
    `"load_extension"(...)` - does not slip past the list with its quotes on.
    """
    if isinstance(node, exp.Anonymous):
        return node.name.lower()
    if isinstance(node, exp.Func):
        return node.sql_name().lower()
    return None


def _referenced_tables(statement: exp.Expression) -> list[str]:
    """The real tables the statement reads, rejecting any the schema lacks."""
    cte_references = _cte_reference_ids(statement)
    tables: set[str] = set()
    for table in statement.find_all(exp.Table):
        if id(table) in cte_references:
            continue
        name = table.name.lower()
        if name not in ALLOWED_TABLES:
            raise InvalidSql(
                f"There is no table named {table.name}. "
                f"The database has: {', '.join(sorted(ALLOWED_TABLES))}."
            )
        tables.add(name)
    return sorted(tables)


def _cte_reference_ids(statement: exp.Expression) -> set[int]:
    """The table nodes that name a CTE visible in their own scope, not a real table.

    A CTE name looks like a table to the parser, so those references have to be
    exempt from the allowlist - but only where the CTE is actually in scope.
    Subtracting every CTE name across the whole tree would let
    `SELECT * FROM sqlite_master WHERE 1 IN (WITH sqlite_master AS (...) SELECT ...)`
    exempt the outer read of a table the allowlist never permitted.

    If sqlglot cannot resolve the scopes, nothing is exempted and every table is
    checked, which errs towards refusing rather than allowing.
    """
    try:
        scopes = traverse_scope(statement)
    except Exception:
        return set()
    return {
        id(table)
        for scope in scopes
        for table in scope.tables
        if not isinstance(scope.sources.get(table.alias_or_name), exp.Table)
        and table.alias_or_name in scope.sources
    }


def _apply_limit(sql: str, statement: exp.Expression, max_rows: int) -> str:
    """Bound the statement to `max_rows` + 1 rows.

    The extra row is how the executor tells a full result from a truncated one.
    When a limit has to be added, the model's own text is kept and the clause is
    appended on a new line: the interface shows that text, re-rendering it
    through sqlglot would discard formatting the model chose deliberately, and a
    statement ending in a `--` comment would swallow a clause appended inline.
    """
    cap = max_rows + 1
    limit = statement.args.get("limit")
    if limit is None:
        return f"{sql.rstrip().removesuffix(';').rstrip()}\nLIMIT {cap}"
    if _limit_rows(limit) <= cap:
        return sql
    limit.set("expression", exp.Literal.number(cap))
    return statement.sql(dialect=DIALECT)


def _limit_rows(limit: exp.Expression) -> int:
    """The row count of a LIMIT clause; anything unreadable counts as unbounded."""
    expression = limit.expression
    if isinstance(expression, exp.Literal) and expression.is_int:
        return int(expression.name)
    return sys.maxsize
