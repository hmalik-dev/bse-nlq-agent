"""The prompt teaches the model the whole database, and the examples really run."""

from __future__ import annotations

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
    assert "is_home_club = 0" in context.system and "LIKE" in context.system
    assert "'2025-26'" in context.system and "'2026'" in context.system
    assert "from 2024-01-01 to 2027-01-09" in context.system


def test_dialect_notes_forbid_date_now(context: PromptContext) -> None:
    assert "DATE_TRUNC" in context.system
    assert "Never call date('now')" in context.system


def test_today_is_stated_as_iso(context: PromptContext) -> None:
    assert "Today is 2026-09-11." in context.system
    assert "Today is 2025-03-02." in build_context(date(2025, 3, 2)).system


def test_the_output_contract_names_both_decline_categories(context: PromptContext) -> None:
    assert '"out_of_scope"' in context.system
    assert '"destructive"' in context.system


def test_the_context_is_cached_per_day() -> None:
    assert build_context(GOLDEN_TODAY) is build_context(GOLDEN_TODAY)
    assert build_context(GOLDEN_TODAY) is not build_context(date(2025, 3, 2))


def test_exactly_nine_examples_load_with_every_field(context: PromptContext) -> None:
    entries = yaml.safe_load(EXAMPLES_PATH.read_text(encoding="utf-8"))
    assert len(entries) == len(context.examples) == 9
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
