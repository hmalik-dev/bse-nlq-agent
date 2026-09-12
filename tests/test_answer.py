"""The answer writer sees the rows and nothing else, and names every failure."""

from __future__ import annotations

import anthropic
import pytest

from nlq.agent.answer import MAX_TOKENS, AnswerWriter, build_user_turn, count_total
from nlq.agent.errors import ApiKeyError, ModelRateLimited, ModelRefused, ModelTimeout
from nlq.agent.models import AnswerText
from tests.fakes import (
    FAKE_INPUT_TOKENS,
    FAKE_MODEL,
    FAKE_OUTPUT_TOKENS,
    FakeAnthropic,
    FakeResponse,
    FakeTextBlock,
    FakeUsage,
    api_timeout_error,
    rate_limit_error,
    refusal,
)

QUESTION = "What are our top event categories by revenue?"
ASSUMPTIONS = ["Revenue excludes fees, refunds and comps."]
COLUMNS = ["category", "revenue"]
ROWS = [["NBA", 201512122.83], ["Concert", 98000000.5], ["Comedy", None]]


def _write(client: FakeAnthropic, **overrides: object) -> AnswerText:
    fields = dict(
        question=QUESTION,
        assumptions=ASSUMPTIONS,
        columns=COLUMNS,
        rows=ROWS,
        row_count=len(ROWS),
        truncated=False,
    )
    fields.update(overrides)
    return AnswerWriter(client, model="claude-haiku-4-5").write(**fields)


def test_the_call_carries_the_system_prompt_and_one_user_turn() -> None:
    client = FakeAnthropic(["NBA leads with $201,512,122.83 in revenue."])

    result = _write(client)

    call = client.calls[0]
    assert set(call) == {"model", "max_tokens", "system", "messages"}
    assert call["model"] == "claude-haiku-4-5"
    assert call["max_tokens"] == MAX_TOKENS
    rules = ("two sentences", "only the rows", "thousands", "dollar", "truncated", "Total")
    for rule in rules:
        assert rule in call["system"]
    assert len(call["messages"]) == 1 and call["messages"][0]["role"] == "user"
    assert result.text == "NBA leads with $201,512,122.83 in revenue."
    assert (result.model, result.input_tokens, result.output_tokens) == (
        FAKE_MODEL,
        FAKE_INPUT_TOKENS,
        FAKE_OUTPUT_TOKENS,
    )


def test_the_user_turn_holds_the_question_assumptions_columns_and_rows() -> None:
    turn = build_user_turn(QUESTION, ASSUMPTIONS, COLUMNS, ROWS, len(ROWS), truncated=False)

    assert turn.startswith(f"Question: {QUESTION}")
    assert "- Revenue excludes fees, refunds and comps." in turn
    assert "category | revenue" in turn
    assert "NBA | 201512122.83" in turn
    assert "Comedy | NULL" in turn
    assert "SELECT" not in turn


def test_the_user_turn_says_when_rows_were_capped_or_truncated() -> None:
    turn = build_user_turn(QUESTION, [], COLUMNS, ROWS[:2], 500, truncated=True)
    assert "2 of 500 rows shown" in turn
    assert "truncated" in turn

    turn = build_user_turn(QUESTION, [], COLUMNS, ROWS, len(ROWS), truncated=False)
    assert "3 rows" in turn
    assert "truncated" not in turn


BREAKDOWN_COLUMNS = ["name", "event_date", "tickets_sold"]
BREAKDOWN_ROWS = [["Nets vs. Bucks", "2026-12-22", 1204], ["Nets vs. Suns", "2026-11-26", 987]]


def test_a_whole_breakdown_of_counts_ends_with_the_total_counted_in_code() -> None:
    turn = build_user_turn(QUESTION, [], BREAKDOWN_COLUMNS, BREAKDOWN_ROWS, 2, truncated=False)
    assert turn.endswith("\n\nTotal tickets_sold across all 2 rows: 2191")


@pytest.mark.parametrize(
    ("rows", "row_count", "truncated"),
    [
        (BREAKDOWN_ROWS[:1], 1, False),
        (BREAKDOWN_ROWS, 60, False),
        (BREAKDOWN_ROWS, 2, True),
        ([["a", "2026-01-01", 1.5], ["b", "2026-01-02", 2.5]], 2, False),
        ([["a", "2026-01-01", 1], ["b", "2026-01-02", None]], 2, False),
    ],
    ids=["one-row", "rows-capped", "truncated", "floats", "null"],
)
def test_no_total_is_given_when_the_rows_cannot_be_summed_honestly(
    rows: list[list[object]], row_count: int, truncated: bool
) -> None:
    assert count_total(BREAKDOWN_COLUMNS, rows, row_count, truncated) is None
    turn = build_user_turn(QUESTION, [], BREAKDOWN_COLUMNS, rows, row_count, truncated)
    assert "Total" not in turn


@pytest.mark.parametrize(
    ("scripted", "expected", "code"),
    [
        (rate_limit_error(), ModelRateLimited, "rate_limited"),
        (api_timeout_error(), ModelTimeout, "model_timeout"),
        (refusal(), ModelRefused, "model_refused"),
        (
            FakeResponse([FakeTextBlock("I cannot.")], FakeUsage(1, 2), stop_reason="refusal"),
            ModelRefused,
            "model_refused",
        ),
        (FakeResponse([], FakeUsage(1, 0)), ModelRefused, "model_refused"),
    ],
    ids=["rate-limit", "timeout", "refusal", "refusal-with-text", "no-text"],
)
def test_each_api_failure_becomes_a_named_error(
    scripted: object, expected: type, code: str
) -> None:
    with pytest.raises(expected) as raised:
        _write(FakeAnthropic([scripted]))
    assert raised.value.code == code


def test_a_refusal_carries_the_tokens_the_call_was_billed_for() -> None:
    with pytest.raises(ModelRefused) as raised:
        _write(FakeAnthropic([refusal()]))
    assert raised.value.input_tokens == FAKE_INPUT_TOKENS
    assert raised.value.output_tokens == 0


def test_a_missing_key_is_refused_before_any_client_is_built(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")

    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError("anthropic.Anthropic must not be constructed without a key")

    monkeypatch.setattr(anthropic, "Anthropic", refuse)
    with pytest.raises(ApiKeyError) as raised:
        AnswerWriter().write(QUESTION, [], COLUMNS, ROWS, len(ROWS), truncated=False)
    assert raised.value.code == "missing_api_key"
