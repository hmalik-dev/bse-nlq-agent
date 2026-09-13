"""The prompt teaches the model the whole database, and the examples really run."""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

import pytest
import yaml

from nlq.agent.context import (
    EXAMPLES_PATH,
    GOLDEN_PATH,
    GOLDEN_TODAY,
    PromptContext,
    build_context,
)
from nlq.agent.executor import Executor
from nlq.agent.sql_guard import guard
from nlq.config import DICTIONARY_PATH, SCHEMA_PATH
from nlq.db.seed import seed_database

SCALE = 0.005
MAX_ROWS = 500

SECTION_HEADINGS = (
    "# Role",
    "# Schema",
    "# How the tables join",
    "# Business rules",
    "# Tables and columns",
    "# Known values",
    "# SQLite notes",
    "# Today",
    "# Output",
)


@pytest.fixture(scope="module")
def context() -> PromptContext:
    return build_context(GOLDEN_TODAY)


@pytest.fixture(scope="module")
def db_path(tmp_path_factory: pytest.TempPathFactory) -> Path:
    path = tmp_path_factory.mktemp("data") / "tickets.db"
    seed_database(path, today=GOLDEN_TODAY, scale=SCALE)
    return path


def test_sections_appear_in_the_documented_order(context: PromptContext) -> None:
    positions = [context.system.index(heading) for heading in SECTION_HEADINGS]
    assert positions == sorted(positions)


def test_the_schema_ddl_is_included_verbatim(context: PromptContext) -> None:
    assert SCHEMA_PATH.read_text(encoding="utf-8").rstrip() in context.system


def test_every_join_path_is_spelled_out(context: PromptContext) -> None:
    for path in (
        "tickets.order_id = orders.order_id",
        "orders.customer_id = customers.customer_id",
        "tickets.event_id = events.event_id",
        "events.home_team_id = teams.team_id",
        "events.away_team_id = teams.team_id",
        "events.venue_id = venues.venue_id",
    ):
        assert path in context.system


def test_every_dictionary_rule_and_column_is_rendered(context: PromptContext) -> None:
    dictionary = yaml.safe_load(DICTIONARY_PATH.read_text(encoding="utf-8"))
    for rule in dictionary["business_rules"]:
        assert rule.strip() in context.system
    for table, spec in dictionary["tables"].items():
        assert f"## {table}: {spec['description'].strip()}" in context.system
        for column, text in spec["columns"].items():
            assert f"- {column}: {text.strip()}" in context.system


def test_known_values_and_the_data_window_are_stated(context: PromptContext) -> None:
    for value in ("'Family Show'", "'group_sales'", "'comp'", "'General Admission'"):
        assert value in context.system
    assert "'Brooklyn Nets', 'New York Liberty'" in context.system
    assert "is_home_team = 0" in context.system and "LIKE" in context.system
    assert "'2025-26'" in context.system and "'2026'" in context.system
    assert "from 2024-01-01 to 2027-01-10" in context.system


def test_dialect_notes_forbid_date_now(context: PromptContext) -> None:
    assert "DATE_TRUNC" in context.system
    assert "Never call date('now')" in context.system


def test_today_is_stated_as_iso(context: PromptContext) -> None:
    assert "Today is 2026-09-12." in context.system
    assert "Today is 2025-03-02." in build_context(date(2025, 3, 2)).system


def test_the_output_contract_names_both_decline_categories(context: PromptContext) -> None:
    assert '"out_of_scope"' in context.system
    assert '"destructive"' in context.system


def test_a_total_row_leads_with_the_values_it_filters_on(context: PromptContext) -> None:
    assert "A total row names what it totals" in context.system
    assert "(the year, season label, team name or category)" in context.system
    assert "alias (year, season, team, category), followed by the measure" in context.system
    assert "selects strftime('%Y', the date) AS\n  year and groups by it" in context.system


def test_the_context_is_cached_per_day() -> None:
    assert build_context(GOLDEN_TODAY) is build_context(GOLDEN_TODAY)
    assert build_context(GOLDEN_TODAY) is not build_context(date(2025, 3, 2))


def test_the_rules_break_a_short_run_of_events_down_and_keep_one_row_for_one_thing(
    context: PromptContext,
) -> None:
    assert "one named team's home games or one\n  named venue's events" in context.system
    assert "per event (name, event_date and the measure)" in context.system
    assert "with no LIMIT" in context.system
    assert "(yesterday's sales, last month's sales)" in context.system
    assert "stays one total row" in context.system
    assert "returns that one\n  row (LIMIT 1)" in context.system


def test_the_worked_examples_teach_both_the_breakdown_and_the_scalar_count(
    context: PromptContext,
) -> None:
    by_question = {example.question: example.plan.sql or "" for example in context.examples}
    breakdown = by_question["How many tickets did we sell for Liberty home games last month?"]
    scalar = by_question["How many tickets did we sell last month?"]
    assert breakdown.startswith("SELECT e.name, e.event_date, COUNT(*) AS tickets_sold")
    assert "GROUP BY e.event_id" in breakdown and "LIMIT" not in breakdown
    assert scalar.startswith("SELECT COUNT(*) AS tickets_sold") and "GROUP BY" not in scalar


def test_exactly_ten_examples_load_with_every_field(context: PromptContext) -> None:
    entries = yaml.safe_load(EXAMPLES_PATH.read_text(encoding="utf-8"))
    assert len(entries) == len(context.examples) == 11
    for entry in entries:
        assert set(entry) == {
            "question",
            "answerable",
            "sql",
            "assumptions",
            "decline_reason",
            "decline_category",
        }
    declined = [example.plan for example in context.examples if not example.plan.answerable]
    assert sorted(plan.decline_category for plan in declined) == ["destructive", "out_of_scope"]


def test_the_prompt_matches_the_golden_snapshot(context: PromptContext) -> None:
    # Regenerate with: uv run python -m nlq.agent.context --write-golden
    assert context.system == GOLDEN_PATH.read_text(encoding="utf-8")


def test_every_answerable_example_runs_against_the_schema(
    context: PromptContext, db_path: Path
) -> None:
    executor = Executor(db_path)
    for example in context.examples:
        if not example.plan.answerable:
            continue
        guarded = guard(example.plan.sql or "", max_rows=MAX_ROWS)
        result = executor.run(guarded.sql)
        assert len(result.columns) >= 1, example.question


def test_the_today_placeholder_is_filled_with_the_date_passed_in() -> None:
    raw = EXAMPLES_PATH.read_text(encoding="utf-8")
    assert "{today}" in raw
    assert not re.search(r"'20\d\d-\d\d-\d\d'", _sql_lines(raw)), (
        "a literal date stands in for today"
    )
    for day in (GOLDEN_TODAY, date(2025, 3, 2)):
        sql = "\n".join(example.plan.sql or "" for example in build_context(day).examples)
        assert "{today}" not in sql
        assert sql.count(f"'{day.isoformat()}'") >= 5


def _sql_lines(raw: str) -> str:
    """The example SQL minus the calendar-year bounds a question names itself (in 2024, in 2025)."""
    return "\n".join(line for line in raw.splitlines() if "-01-01'" not in line)


def test_last_season_is_worked_out_per_team_from_the_data_and_today(
    context: PromptContext, db_path: Path
) -> None:
    by_question = {example.question: example.plan.sql or "" for example in context.examples}
    executor = Executor(db_path)

    nets = _rows(executor, by_question["How many tickets did the Nets sell last season?"])
    both = _rows(executor, by_question["How many tickets did we sell last season?"])

    assert [(team, season) for team, season, _ in nets] == [("Brooklyn Nets", "2025-26")]
    assert [(team, season) for team, season, _ in both] == [
        ("Brooklyn Nets", "2025-26"),
        ("New York Liberty", "2025"),
    ]


def test_no_season_label_is_written_into_the_rules_or_the_examples(
    context: PromptContext,
) -> None:
    """The schema DDL's column comment shows the label format and is left as it is."""
    rules = context.system.replace(SCHEMA_PATH.read_text(encoding="utf-8").rstrip(), "")
    sql = "\n".join(example.plan.sql or "" for example in context.examples)
    for label in ("'2024-25'", "'2025-26'", "'2026-27'", "'2025'", "'2026'"):
        assert label not in rules, label
        assert label not in sql, label


def _rows(executor: Executor, sql: str) -> list[list]:
    return executor.run(guard(sql, max_rows=MAX_ROWS).sql).rows


def test_the_both_teams_example_assumes_both_teams_and_playoffs_in_one_sentence(
    context: PromptContext,
) -> None:
    (plan,) = [
        e.plan
        for e in context.examples
        if e.question == "How many tickets did we sell last season?"
    ]
    assert any("both teams" in line and "playoff" in line for line in plan.assumptions)


def test_the_prompt_says_team_and_names_club_only_as_a_seat_tier(context: PromptContext) -> None:
    assert "one named team's home games" in context.system
    assert "is_home_team = 1" in context.system
    club_lines = [
        line for line in context.system.splitlines() if re.search(r"\bclubs?\b", line, re.I)
    ]
    assert len(club_lines) == 3
    assert all("Suite" in line and "Lower Bowl" in line for line in club_lines), club_lines
