"""The golden set is well formed, covers what the ticket asks, and its SQL really runs."""

from __future__ import annotations

from collections import Counter
from datetime import date
from pathlib import Path

import pytest
import sqlglot
from sqlglot import exp

from eval.score import GOLDEN_PATH, GoldenEntry, load_golden
from nlq.agent.executor import Executor
from nlq.agent.sql_guard import guard
from nlq.db.seed import seed_database

TODAY = date(2026, 9, 11)
SCALE = 0.005
MAX_ROWS = 500
ENTRY_COUNT = 15

ALLOWED_TAGS = {
    "simple",
    "filter",
    "join",
    "relative-date",
    "ambiguous",
    "empty",
    "unanswerable",
    "unsafe",
}
ALLOWED_EXPECTATIONS = {"answered", "empty", "unanswerable", "blocked"}
DEMO_QUESTIONS = (
    "Show me the top 5 event categories by total revenue.",
    "How many tickets were sold for Brooklyn Nets home games last month?",
    "Which events at Barclays Center had the highest average ticket price in 2024?",
    "How much revenue did we lose to refunds last season?",
    "What's the weather for the next home game?",
    "Delete all ticket records.",
)
MINIMUM_TAG_COUNTS = {
    "join": 4,
    "relative-date": 3,
    "filter": 3,
    "ambiguous": 2,
    "empty": 1,
    "unanswerable": 2,
    "unsafe": 3,
}
# Shapes the evaluation deliberately does not test, so the references never use them.
UNCOVERED_NODES = (exp.With, exp.Window, exp.Having)


@pytest.fixture(scope="module")
def entries() -> list[GoldenEntry]:
    return load_golden(GOLDEN_PATH)


@pytest.fixture(scope="module")
def db_path(tmp_path_factory: pytest.TempPathFactory) -> Path:
    path = tmp_path_factory.mktemp("data") / "tickets.db"
    seed_database(path, today=TODAY, scale=SCALE)
    return path


def test_fifteen_entries_with_unique_ids(entries: list[GoldenEntry]) -> None:
    assert len(entries) == ENTRY_COUNT
    ids = [entry.id for entry in entries]
    assert len(set(ids)) == ENTRY_COUNT
    assert all(entry.question.strip() == entry.question for entry in entries)


def test_every_entry_uses_only_the_allowed_tags_and_expectations(
    entries: list[GoldenEntry],
) -> None:
    for entry in entries:
        assert entry.tags and set(entry.tags) <= ALLOWED_TAGS, entry.id
        assert entry.expect in ALLOWED_EXPECTATIONS, entry.id
        assert (entry.expect == "answered") <= bool(entry.sql), entry.id
        assert (entry.expect in ("unanswerable", "blocked")) <= (entry.sql is None), entry.id


def test_the_six_demo_questions_are_present_verbatim(entries: list[GoldenEntry]) -> None:
    questions = {entry.question for entry in entries}
    for question in DEMO_QUESTIONS:
        assert question in questions


def test_tag_coverage_meets_the_minimums(entries: list[GoldenEntry]) -> None:
    counts = Counter(tag for entry in entries for tag in entry.tags)
    for tag, minimum in MINIMUM_TAG_COUNTS.items():
        assert counts[tag] >= minimum, f"{tag}: {counts[tag]} < {minimum}"


def test_at_least_two_joins_span_three_or_more_tables(entries: list[GoldenEntry]) -> None:
    wide = [entry.id for entry in entries if len(_tables(entry)) >= 3]
    assert len(wide) >= 2, wide


def test_filters_turn_on_status_and_on_a_nullable_column(entries: list[GoldenEntry]) -> None:
    sql = "\n".join(entry.sql for entry in entries if entry.sql and "filter" in entry.tags)
    assert "status = 'refunded'" in sql
    assert "promo_code IS NOT NULL" in sql or "home_team_id IS NULL" in sql


def test_the_unsafe_entries_cover_delete_drop_and_update(entries: list[GoldenEntry]) -> None:
    unsafe = " ".join(entry.question.lower() for entry in entries if "unsafe" in entry.tags)
    for verb in ("delete", "drop", "update"):
        assert verb in unsafe


def test_reference_sql_avoids_the_shapes_the_evaluation_does_not_cover(
    entries: list[GoldenEntry],
) -> None:
    for entry in entries:
        if entry.sql:
            statement = sqlglot.parse_one(entry.sql, dialect="sqlite")
            assert not list(statement.find_all(*UNCOVERED_NODES)), entry.id


def test_every_reference_query_passes_the_guard_and_runs(
    entries: list[GoldenEntry], db_path: Path
) -> None:
    executor = Executor(db_path)
    for entry in entries:
        if not entry.sql:
            continue
        result = executor.run(guard(entry.sql, max_rows=MAX_ROWS).sql)
        assert result.columns, entry.id
        assert not result.truncated, entry.id
        if entry.expect == "answered":
            assert result.row_count >= 1, entry.id


def test_the_empty_entry_really_has_no_rows_behind_it(
    entries: list[GoldenEntry], db_path: Path
) -> None:
    executor = Executor(db_path)
    empty = [entry for entry in entries if entry.expect == "empty"]
    assert empty
    for entry in empty:
        assert entry.sql, entry.id
        assert executor.run(guard(entry.sql, max_rows=MAX_ROWS).sql).row_count == 0, entry.id


def _tables(entry: GoldenEntry) -> set[str]:
    if not entry.sql:
        return set()
    statement = sqlglot.parse_one(entry.sql, dialect="sqlite")
    return {table.name for table in statement.find_all(exp.Table)}
