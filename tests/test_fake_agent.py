"""The fake agent reaches every status, from real schema names, without a key or a database."""

from __future__ import annotations

import pytest

from nlq.agent import fake
from nlq.agent.agent import BLOCKED_ANSWER, EMPTY_SUGGESTIONS
from nlq.agent.context import CATEGORIES
from nlq.agent.fake import CATEGORY_SQL, EMPTY_SQL, NETS_SQL, FakeAgent
from nlq.agent.models import AskResult
from nlq.agent.sql_guard import guard
from nlq.db.seed import NBA_OPPONENTS
from nlq.examples import EXAMPLE_QUESTIONS

STEP_NAMES = ["Reading schema", "Writing SQL", "Checking safety", "Running query", "Writing answer"]
ALL_STATUSES = {"answered", "empty", "unanswerable", "blocked", "error"}

# question -> (status, error code)
KEYWORD_OUTCOMES = {
    "Delete every ticket": ("blocked", None),
    "DROP the orders table": ("blocked", None),
    "Update prices to zero": ("blocked", None),
    "What's the weather for the next home game?": ("unanswerable", None),
    "Show me nothing at all": ("empty", None),
    "Trigger a rate limit": ("error", "rate_limited"),
    "Pretend there is no key": ("error", "missing_api_key"),
    "Pretend there is no database": ("error", "database_missing"),
    "Pretend the key is out of credit": ("error", "usage_exhausted"),
    "How many tickets for Nets home games last month?": ("answered", None),
    "Top 5 event categories by total revenue": ("answered", None),
}


@pytest.fixture
def agent() -> FakeAgent:
    return FakeAgent()


@pytest.mark.parametrize(("question", "expected"), KEYWORD_OUTCOMES.items())
def test_a_keyword_picks_the_outcome_and_the_result_validates(
    agent: FakeAgent, question: str, expected: tuple[str, str | None]
) -> None:
    status, code = expected

    result = agent.ask(question)

    assert result.status == status
    assert result.question == question
    assert (result.error.code if result.error else None) == code
    assert AskResult.model_validate(result.model_dump()) == result


def test_every_status_is_reachable(agent: FakeAgent) -> None:
    statuses = {agent.ask(question).status for question in KEYWORD_OUTCOMES}
    assert statuses == ALL_STATUSES


def test_results_are_deterministic(agent: FakeAgent) -> None:
    for question in KEYWORD_OUTCOMES:
        assert agent.ask(question) == agent.ask(question)


def test_blocked_shows_the_rejected_statement_and_the_fixed_refusal(agent: FakeAgent) -> None:
    result = agent.ask("Delete all ticket records")
    assert result.sql == "DELETE FROM tickets"
    assert result.answer == BLOCKED_ANSWER


def test_unanswerable_offers_three_example_questions(agent: FakeAgent) -> None:
    result = agent.ask("What's the weather like?")
    assert result.answer and "weather" in result.answer
    assert result.suggestions == [example.question for example in EXAMPLE_QUESTIONS[:3]]


def test_empty_keeps_the_sql_the_columns_and_the_two_suggestions(agent: FakeAgent) -> None:
    result = agent.ask("Show nothing")
    assert result.sql == EMPTY_SQL
    assert result.columns == ["name", "event_date"]
    assert result.rows == [] and result.row_count == 0
    assert result.suggestions == EMPTY_SUGGESTIONS


def test_nets_is_an_eight_row_table_of_real_fixtures_repaired_once(agent: FakeAgent) -> None:
    result = agent.ask("How many tickets did we sell for Nets home games last month?")

    assert result.columns == ["event", "event_date", "tickets_sold", "avg_price", "gate_revenue"]
    assert result.row_count == 8 and len(result.rows) == 8
    opponents = {name for name, _ in NBA_OPPONENTS}
    for event, event_date, sold, avg_price, gate in result.rows:
        assert event.removeprefix("Brooklyn Nets vs. ") in opponents
        assert "2026-10-01" <= event_date <= "2027-04-30"
        assert gate == round(sold * avg_price, 2)
    assert len(result.assumptions) == 2
    assert result.chart is None
    assert result.trace.repairs == 1
    assert result.sql == NETS_SQL


def test_the_default_is_a_five_category_bar_chart_with_a_twelve_line_query(
    agent: FakeAgent,
) -> None:
    result = agent.ask("Top 5 event categories by total revenue")

    assert result.columns == ["category", "revenue"]
    assert [row[0] for row in result.rows] == ["NBA", "Concert", "WNBA", "Family Show", "Comedy"]
    assert set(row[0] for row in result.rows) <= set(CATEGORIES)
    assert result.row_count == 5
    assert len(result.assumptions) == 2
    assert result.chart is not None
    assert result.chart.model_dump() == {"type": "bar", "x": "category", "y": "revenue"}
    assert result.sql == CATEGORY_SQL
    assert len(CATEGORY_SQL.splitlines()) == 12
    assert "JOIN" in CATEGORY_SQL and "GROUP BY" in CATEGORY_SQL


def test_the_trace_has_the_five_steps_the_fake_model_and_the_documented_total(
    agent: FakeAgent,
) -> None:
    trace = agent.ask("Top 5 event categories by total revenue").trace
    assert [step.name for step in trace.steps] == STEP_NAMES
    assert all(step.ms > 0 for step in trace.steps)
    assert sum(step.ms for step in trace.steps) == trace.total_ms == 2160
    assert trace.model == "fake"
    assert trace.repairs == 0
    assert trace.cost_usd == 0.0


@pytest.mark.parametrize("sql", [NETS_SQL, CATEGORY_SQL, EMPTY_SQL])
def test_the_canned_sql_is_a_valid_read_against_the_real_schema(sql: str) -> None:
    assert guard(sql, max_rows=500).sql.startswith(sql)


def test_slow_waits_two_seconds_then_gives_the_default_answer(
    agent: FakeAgent, monkeypatch: pytest.MonkeyPatch
) -> None:
    slept: list[float] = []
    monkeypatch.setattr(fake.time, "sleep", slept.append)

    result = agent.ask("Be slow about it")

    assert slept == [2]
    assert result.status == "answered"
    assert result.chart is not None
