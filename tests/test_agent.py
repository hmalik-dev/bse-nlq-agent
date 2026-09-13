"""Every status the agent can return, produced end to end through the fake client."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import anthropic
import pytest

from nlq.agent.agent import (
    ANSWER_ROW_CAP,
    BLOCKED_ANSWER,
    EMPTY_SUGGESTIONS,
    INTERNAL_MESSAGE,
    Agent,
    chart_for,
)
from nlq.agent.answer import AnswerWriter
from nlq.agent.context import build_context, load_examples
from nlq.agent.executor import Executor, QueryResult
from nlq.agent.fake import FakeAgent
from nlq.agent.llm import SqlWriter
from nlq.agent.models import AnswerText, AskResult, SqlPlan
from nlq.db.seed import seed_database
from nlq.pricing import cost_usd
from tests.fakes import (
    FAKE_INPUT_TOKENS,
    FAKE_OUTPUT_TOKENS,
    FakeAnthropic,
    rate_limit_error,
    refusal,
)

TODAY = date(2026, 9, 11)
SCALE = 0.005
SQL_MODEL = "claude-haiku-4-5"
ANSWER_MODEL = "claude-sonnet-5"
QUESTION = "How many tickets sold per category?"
ANSWER = "NBA sold the most tickets."

STEP_NAMES = ["Reading schema", "Writing SQL", "Checking safety", "Running query", "Writing answer"]
RESULT_KEYS = {
    "status",
    "question",
    "answer",
    "assumptions",
    "sql",
    "columns",
    "rows",
    "row_count",
    "truncated",
    "chart",
    "trace",
    "error",
    "suggestions",
}
TRACE_KEYS = {"steps", "repairs", "model", "total_ms", "input_tokens", "output_tokens", "cost_usd"}

TWO_COLUMN_SQL = "SELECT category, COUNT(*) AS events FROM events GROUP BY category"
THREE_COLUMN_SQL = "SELECT name, category, event_date FROM events LIMIT 5"
EMPTY_SQL = "SELECT name FROM events WHERE category = 'Opera'"
UNKNOWN_TABLE_SQL = "SELECT COUNT(*) FROM ticket"
UNKNOWN_COLUMN_SQL = "SELECT sold FROM tickets"
RUNAWAY_SQL = (
    "WITH RECURSIVE c(x) AS (SELECT 1 UNION ALL SELECT x + 1 FROM c) SELECT COUNT(*) FROM c"
)


def plan(sql: str, *assumptions: str) -> SqlPlan:
    return SqlPlan(answerable=True, sql=sql, assumptions=list(assumptions))


def decline(reason: str, category: str) -> SqlPlan:
    return SqlPlan(answerable=False, decline_reason=reason, decline_category=category)


@dataclass
class RecordingAnswerWriter:
    """Stands in for `AnswerWriter` when the test needs to see what it was handed."""

    model: str = ANSWER_MODEL
    calls: list[dict] = field(default_factory=list)

    def write(self, question, assumptions, columns, rows, row_count, truncated) -> AnswerText:
        self.calls.append(dict(rows=rows, row_count=row_count, truncated=truncated))
        return AnswerText(
            text=ANSWER, model=self.model, input_tokens=10, output_tokens=5, elapsed_ms=1
        )


@pytest.fixture(scope="module")
def db_path(tmp_path_factory: pytest.TempPathFactory) -> Path:
    path = tmp_path_factory.mktemp("data") / "tickets.db"
    seed_database(path, today=TODAY, scale=SCALE)
    return path


def make_agent(
    db_path: Path,
    sql_responses: list,
    answer_responses: list | None = None,
    *,
    executor: Executor | None = None,
    answer_writer: object | None = None,
) -> tuple[Agent, FakeAnthropic, FakeAnthropic]:
    sql_client = FakeAnthropic(sql_responses)
    answer_client = FakeAnthropic([ANSWER] if answer_responses is None else answer_responses)
    agent = Agent(
        SqlWriter(sql_client, model=SQL_MODEL),
        executor or Executor(db_path),
        answer_writer or AnswerWriter(answer_client, model=ANSWER_MODEL),
        today=TODAY,
    )
    return agent, sql_client, answer_client


def test_answered_with_a_chart_when_two_columns_fit_one(db_path: Path) -> None:
    agent, _, answer_client = make_agent(db_path, [plan(TWO_COLUMN_SQL, "All events.")])

    result = agent.ask(QUESTION)

    assert result.status == "answered"
    assert result.answer == ANSWER
    assert result.assumptions == ["All events."]
    assert result.sql is not None and result.sql.startswith(TWO_COLUMN_SQL)
    assert result.columns == ["category", "events"]
    assert 2 <= result.row_count <= 25 and len(result.rows) == result.row_count
    assert not result.truncated
    assert result.chart is not None
    assert result.chart.model_dump() == {"type": "bar", "x": "category", "y": "events"}
    assert result.error is None and result.suggestions == []
    assert len(answer_client.calls) == 1


@pytest.mark.parametrize(
    ("columns", "rows"),
    [
        (["year", "tickets"], [[2025, 10], [2026, 12]]),  # the label column is not text
        (["category", "top_event"], [["NBA", "Nets vs Knicks"], ["WNBA", "Liberty vs Aces"]]),
        (["category", "tickets"], [["NBA", 10]]),  # one bar is not a comparison
        (["category", "tickets"], [[f"c{n}", n] for n in range(26)]),  # too many bars to read
    ],
    ids=["numeric-labels", "text-values", "one-row", "twenty-six-rows"],
)
def test_no_chart_is_offered_for_an_ambiguous_shape(columns: list[str], rows: list[list]) -> None:
    query = QueryResult(
        columns=columns, rows=rows, row_count=len(rows), truncated=False, elapsed_ms=1
    )
    assert chart_for(query) is None


def test_answered_without_a_chart_when_there_are_three_columns(db_path: Path) -> None:
    agent, _, _ = make_agent(db_path, [plan(THREE_COLUMN_SQL)])
    result = agent.ask(QUESTION)
    assert result.status == "answered"
    assert result.columns == ["name", "category", "event_date"]
    assert result.chart is None


def test_empty_carries_the_sql_the_columns_and_three_example_questions(db_path: Path) -> None:
    agent, _, answer_client = make_agent(db_path, [plan(EMPTY_SQL)])

    result = agent.ask(QUESTION)

    assert result.status == "empty"
    assert result.answer == ""
    assert result.sql is not None and result.sql.startswith(EMPTY_SQL)
    assert result.columns == ["name"]
    assert result.rows == [] and result.row_count == 0
    answerable = [example.question for example in load_examples() if example.plan.answerable]
    assert result.suggestions == answerable[:3] == EMPTY_SUGGESTIONS
    assert answer_client.calls == []


def test_every_empty_suggestion_asked_through_the_fake_client_is_answerable(
    db_path: Path,
) -> None:
    empty_agent, _, _ = make_agent(db_path, [plan(EMPTY_SQL)])
    suggestions = empty_agent.ask(QUESTION).suggestions
    worked_plans = {example.question: example.plan for example in build_context(TODAY).examples}

    statuses = {}
    for suggestion in suggestions:
        agent, _, _ = make_agent(db_path, [worked_plans[suggestion]])
        statuses[suggestion] = agent.ask(suggestion).status

    assert len(statuses) == 3
    assert all(status in {"answered", "empty"} for status in statuses.values()), statuses


def test_every_empty_suggestion_the_fake_agent_offers_is_answerable() -> None:
    fake = FakeAgent()
    suggestions = fake.ask("Show me nothing at all").suggestions
    assert suggestions == EMPTY_SUGGESTIONS
    assert len(suggestions) == 3
    assert all(fake.ask(suggestion).status != "unanswerable" for suggestion in suggestions)


def test_unanswerable_returns_the_reason_and_three_example_questions(db_path: Path) -> None:
    reason = "The data holds no weather."
    agent, _, _ = make_agent(db_path, [decline(reason, "out_of_scope")])

    result = agent.ask("What was the weather like?")

    assert result.status == "unanswerable"
    assert result.answer == reason
    assert result.sql is None
    answerable = [example.question for example in load_examples() if example.plan.answerable]
    assert result.suggestions == answerable[:3]
    assert len(result.suggestions) == 3


def test_blocked_by_the_model_declining_a_destructive_request(db_path: Path) -> None:
    agent, _, _ = make_agent(db_path, [decline("That would delete data.", "destructive")])
    result = agent.ask("Delete every refunded ticket.")
    assert result.status == "blocked"
    assert result.sql is None
    assert result.answer == BLOCKED_ANSWER
    assert "read-only" in result.answer


def test_blocked_by_the_guard_keeps_the_rejected_statement(db_path: Path) -> None:
    agent, sql_client, _ = make_agent(db_path, [plan("DELETE FROM tickets")])

    result = agent.ask("Delete every ticket.")

    assert result.status == "blocked"
    assert result.sql == "DELETE FROM tickets"
    assert result.answer == BLOCKED_ANSWER
    assert result.trace.repairs == 0
    assert len(sql_client.calls) == 1


def test_a_repaired_query_succeeds_and_the_repair_turn_carries_the_error(db_path: Path) -> None:
    agent, sql_client, _ = make_agent(db_path, [plan(UNKNOWN_TABLE_SQL), plan(TWO_COLUMN_SQL)])

    result = agent.ask(QUESTION)

    assert result.status == "answered"
    assert result.trace.repairs == 1
    assert [step.name for step in result.trace.steps] == STEP_NAMES  # a repair adds time, not steps
    assert len(sql_client.calls) == 2
    repair_turn = sql_client.calls[1]["messages"][-1]["content"]
    assert UNKNOWN_TABLE_SQL in repair_turn
    assert "no table named ticket" in repair_turn


def test_repairs_are_exhausted_after_the_third_writer_call(db_path: Path) -> None:
    plans = [plan(UNKNOWN_TABLE_SQL), plan(UNKNOWN_COLUMN_SQL), plan(UNKNOWN_COLUMN_SQL)]
    agent, sql_client, answer_client = make_agent(db_path, plans)

    result = agent.ask(QUESTION)

    assert result.status == "error"
    assert result.error is not None
    assert result.error.code == "repairs_exhausted"
    assert "sold" in result.error.message
    assert result.sql is not None and result.sql.startswith(UNKNOWN_COLUMN_SQL)
    assert result.trace.repairs == 2
    assert len(sql_client.calls) == 3
    assert answer_client.calls == []


def test_a_rate_limited_writer_is_reported_not_raised(db_path: Path) -> None:
    agent, _, _ = make_agent(db_path, [rate_limit_error()])
    result = agent.ask(QUESTION)
    assert result.status == "error"
    assert result.error is not None and result.error.code == "rate_limited"
    assert result.sql is None
    assert [step.name for step in result.trace.steps] == ["Reading schema", "Writing SQL"]
    assert (result.trace.input_tokens, result.trace.output_tokens) == (0, 0)
    assert result.trace.cost_usd == 0.0


def test_a_missing_database_is_reported_after_the_guard(tmp_path: Path) -> None:
    missing = tmp_path / "nowhere.db"
    agent, sql_client, answer_client = make_agent(
        missing, [plan(TWO_COLUMN_SQL)], executor=Executor(missing)
    )

    result = agent.ask(QUESTION)

    assert result.status == "error"
    assert result.error is not None and result.error.code == "database_missing"
    assert len(sql_client.calls) == 1
    assert answer_client.calls == []
    assert [step.name for step in result.trace.steps] == STEP_NAMES[:4]


def test_a_query_timeout_is_not_repaired(db_path: Path) -> None:
    agent, sql_client, _ = make_agent(
        db_path, [plan(RUNAWAY_SQL)], executor=Executor(db_path, timeout_ms=50)
    )

    result = agent.ask(QUESTION)

    assert result.status == "error"
    assert result.error is not None and result.error.code == "query_timeout"
    assert len(sql_client.calls) == 1
    assert result.trace.repairs == 0


def test_the_answer_writer_sees_at_most_fifty_rows_of_a_truncated_result(db_path: Path) -> None:
    writer = RecordingAnswerWriter()
    agent, _, _ = make_agent(
        db_path,
        [plan("SELECT ticket_id FROM tickets")],
        executor=Executor(db_path, max_rows=500),
        answer_writer=writer,
    )

    result = agent.ask(QUESTION)

    assert result.status == "answered"
    assert result.truncated and result.row_count == 500 and len(result.rows) == 500
    handed = writer.calls[0]
    assert len(handed["rows"]) == ANSWER_ROW_CAP
    assert handed["row_count"] == 500 and handed["truncated"] is True


def test_the_trace_lists_the_steps_in_order_with_tokens_and_cost(db_path: Path) -> None:
    agent, _, _ = make_agent(db_path, [plan(TWO_COLUMN_SQL)])

    trace = agent.ask(QUESTION).trace

    assert [step.name for step in trace.steps] == STEP_NAMES
    assert all(step.ms >= 0 for step in trace.steps)
    assert trace.total_ms > 0
    assert trace.model == SQL_MODEL
    assert trace.input_tokens == 2 * FAKE_INPUT_TOKENS
    assert trace.output_tokens == 2 * FAKE_OUTPUT_TOKENS
    expected = cost_usd(SQL_MODEL, FAKE_INPUT_TOKENS, FAKE_OUTPUT_TOKENS) + cost_usd(
        ANSWER_MODEL, FAKE_INPUT_TOKENS, FAKE_OUTPUT_TOKENS
    )
    assert trace.cost_usd == round(expected, 6)


def test_calls_made_before_an_error_are_still_priced(db_path: Path) -> None:
    agent, _, _ = make_agent(db_path, [plan(UNKNOWN_TABLE_SQL), rate_limit_error()])

    trace = agent.ask(QUESTION).trace

    assert trace.repairs == 1
    assert trace.input_tokens == FAKE_INPUT_TOKENS
    assert trace.cost_usd == cost_usd(SQL_MODEL, FAKE_INPUT_TOKENS, FAKE_OUTPUT_TOKENS)


def test_a_plan_that_fails_validation_is_still_priced(db_path: Path) -> None:
    agent, _, answer_client = make_agent(db_path, ['{"answerable": true, "sql": ""}'])

    result = agent.ask(QUESTION)

    assert result.status == "error"
    assert result.error is not None and result.error.code == "model_refused"
    assert result.trace.input_tokens == FAKE_INPUT_TOKENS
    assert result.trace.output_tokens == FAKE_OUTPUT_TOKENS
    assert result.trace.cost_usd == cost_usd(SQL_MODEL, FAKE_INPUT_TOKENS, FAKE_OUTPUT_TOKENS)
    assert answer_client.calls == []


def test_a_refusal_is_priced_for_the_prompt_it_read(db_path: Path) -> None:
    agent, _, _ = make_agent(db_path, [refusal()])

    result = agent.ask(QUESTION)

    assert result.status == "error"
    assert result.error is not None and result.error.code == "model_refused"
    assert result.trace.input_tokens == FAKE_INPUT_TOKENS
    assert result.trace.output_tokens == 0
    assert result.trace.cost_usd == cost_usd(SQL_MODEL, FAKE_INPUT_TOKENS, 0)


def test_an_answer_refusal_is_priced_on_top_of_the_sql_call(db_path: Path) -> None:
    agent, _, _ = make_agent(db_path, [plan(TWO_COLUMN_SQL)], [refusal()])

    result = agent.ask(QUESTION)

    assert result.status == "error"
    assert result.error is not None and result.error.code == "model_refused"
    assert result.trace.input_tokens == 2 * FAKE_INPUT_TOKENS
    assert result.trace.output_tokens == FAKE_OUTPUT_TOKENS
    expected = cost_usd(SQL_MODEL, FAKE_INPUT_TOKENS, FAKE_OUTPUT_TOKENS) + cost_usd(
        ANSWER_MODEL, FAKE_INPUT_TOKENS, 0
    )
    assert result.trace.cost_usd == round(expected, 6)


def test_an_unexpected_exception_is_logged_once_and_reported_as_internal(
    db_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    class BrokenWriter:
        model = SQL_MODEL

        def write(self, *args: object, **kwargs: object) -> None:
            raise RuntimeError("secret detail")

    agent = Agent(BrokenWriter(), Executor(db_path), RecordingAnswerWriter(), today=TODAY)

    with caplog.at_level(logging.ERROR, logger="nlq"):
        result = agent.ask(QUESTION)

    assert result.status == "error"
    assert result.error is not None
    assert result.error.code == "internal"
    assert result.error.message == INTERNAL_MESSAGE
    assert "secret detail" not in result.model_dump_json()
    errors = [record for record in caplog.records if record.name == "nlq"]
    assert len(errors) == 1
    assert "secret detail" in errors[0].exc_text


def test_the_result_dumps_the_documented_keys(db_path: Path) -> None:
    agent, _, _ = make_agent(db_path, [plan(TWO_COLUMN_SQL)])
    dumped = agent.ask(QUESTION).model_dump()
    assert set(dumped) == RESULT_KEYS
    assert set(dumped["trace"]) == TRACE_KEYS
    assert set(dumped["trace"]["steps"][0]) == {"name", "ms"}


def test_from_env_never_raises_and_reports_a_missing_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")

    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError("no real client may be built in a test")

    monkeypatch.setattr(anthropic, "Anthropic", refuse)
    agent = Agent.from_env(today=TODAY)

    result = agent.ask(QUESTION)

    assert isinstance(result, AskResult)
    assert result.status == "error"
    assert result.error is not None and result.error.code == "missing_api_key"
