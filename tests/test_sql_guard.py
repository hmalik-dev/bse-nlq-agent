"""Whatever the model writes, only one bounded read may get through."""

from __future__ import annotations

import pytest

from nlq.agent.errors import InvalidSql, UnsafeSql
from nlq.agent.sql_guard import ALLOWED_TABLES, guard

MAX_ROWS = 500
CAP = MAX_ROWS + 1


def _guard(sql: str, *, max_rows: int = MAX_ROWS) -> str:
    return guard(sql, max_rows=max_rows).sql


def test_allowlist_comes_from_the_schema_file() -> None:
    assert ALLOWED_TABLES == {"venues", "teams", "events", "customers", "orders", "tickets"}


def test_drop_is_refused() -> None:
    with pytest.raises(UnsafeSql):
        _guard("DROP TABLE tickets")


def test_delete_is_refused() -> None:
    with pytest.raises(UnsafeSql):
        _guard("DELETE FROM tickets")


def test_update_is_refused() -> None:
    with pytest.raises(UnsafeSql):
        _guard("UPDATE tickets SET price = 0")


def test_insert_is_refused() -> None:
    with pytest.raises(UnsafeSql):
        _guard("INSERT INTO tickets (ticket_id, order_id) VALUES (1, 1)")


def test_attach_is_refused() -> None:
    with pytest.raises(UnsafeSql):
        _guard("ATTACH DATABASE 'x' AS y")


def test_pragma_is_refused() -> None:
    with pytest.raises(UnsafeSql):
        _guard("PRAGMA writable_schema = 1")


def test_a_second_statement_is_refused() -> None:
    with pytest.raises(UnsafeSql):
        _guard("SELECT 1; SELECT 2")


def test_a_write_hidden_in_a_cte_is_refused() -> None:
    with pytest.raises(UnsafeSql):
        _guard("WITH x AS (DELETE FROM tickets RETURNING *) SELECT * FROM x")


def test_load_extension_is_refused() -> None:
    with pytest.raises(UnsafeSql):
        _guard("SELECT load_extension('x')")


def test_select_into_is_refused() -> None:
    with pytest.raises(UnsafeSql):
        _guard("SELECT * INTO copies FROM tickets")


def test_an_unknown_table_is_repairable() -> None:
    with pytest.raises(InvalidSql) as error:
        _guard("SELECT * FROM users")
    assert error.value.repairable
    assert "users" in error.value.message


def test_unparsable_text_is_repairable() -> None:
    with pytest.raises(InvalidSql) as error:
        _guard("SELECT FROM WHERE ((")
    assert error.value.repairable


def test_a_join_is_accepted_and_reports_its_tables() -> None:
    guarded = guard(
        "SELECT e.name FROM tickets t JOIN events e ON e.event_id = t.event_id",
        max_rows=MAX_ROWS,
    )
    assert guarded.tables == ["events", "tickets"]


def test_a_cte_is_accepted_and_its_name_is_not_a_table() -> None:
    guarded = guard(
        "WITH sold AS (SELECT event_id FROM tickets) SELECT event_id FROM sold",
        max_rows=MAX_ROWS,
    )
    assert guarded.tables == ["tickets"]


def test_a_union_is_accepted() -> None:
    guarded = guard(
        "SELECT name FROM events UNION SELECT name FROM teams",
        max_rows=MAX_ROWS,
    )
    assert guarded.tables == ["events", "teams"]


def test_a_missing_limit_is_appended_and_the_original_text_is_kept() -> None:
    sql = "SELECT   event_id,\n       COUNT(*)\n  FROM tickets\n GROUP BY event_id"
    assert _guard(sql) == f"{sql} LIMIT {CAP}"


def test_a_limit_is_appended_after_a_trailing_semicolon_is_stripped() -> None:
    assert _guard("SELECT * FROM tickets;  ") == f"SELECT * FROM tickets LIMIT {CAP}"


def test_a_limit_above_the_cap_is_lowered() -> None:
    lowered = _guard("SELECT * FROM tickets LIMIT 100000")
    assert f"LIMIT {CAP}" in lowered
    assert "100000" not in lowered


def test_a_limit_within_the_cap_is_left_alone() -> None:
    sql = "SELECT * FROM tickets LIMIT 10"
    assert _guard(sql) == sql
