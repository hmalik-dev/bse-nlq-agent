"""The SQL writer sends what the prompt design says, and names every failure."""

from __future__ import annotations

import json

import anthropic
import pytest

from nlq.agent.context import GOLDEN_TODAY, PromptContext, build_context
from nlq.agent.errors import (
    ApiKeyError,
    ModelError,
    ModelRateLimited,
    ModelRefused,
    ModelTimeout,
)
from nlq.agent.llm import MAX_TOKENS, SqlWriter
from nlq.agent.models import Attempt, SqlPlan
from tests.fakes import (
    FAKE_INPUT_TOKENS,
    FAKE_MODEL,
    FAKE_OUTPUT_TOKENS,
    FakeAnthropic,
    api_connection_error,
    api_status_error,
    api_timeout_error,
    authentication_error,
    rate_limit_error,
    refusal,
)

QUESTION = "How many tickets did we sell in July?"
PLAN = SqlPlan(
    answerable=True,
    sql="SELECT COUNT(*) FROM tickets WHERE status = 'sold'",
    assumptions=["Sold means status = 'sold'."],
)


@pytest.fixture(scope="module")
def context() -> PromptContext:
    return build_context(GOLDEN_TODAY)


def test_the_happy_path_sends_the_prompt_and_asks_for_a_plan(
    context: PromptContext, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("NLQ_SQL_MODEL", "claude-haiku-4-5")
    client = FakeAnthropic([PLAN])

    result = SqlWriter(client).write(QUESTION, context=context)

    assert result.plan == PLAN
    call = client.calls[0]
    assert call["model"] == "claude-haiku-4-5"
    assert call["max_tokens"] == MAX_TOKENS
    assert call["system"] == context.system
    assert call["output_config"] == {
        "format": {"type": "json_schema", "schema": anthropic.transform_schema(SqlPlan)}
    }
    assert "answerable" in call["output_config"]["format"]["schema"]["properties"]
    assert set(call) == {"model", "max_tokens", "system", "messages", "output_config"}


def test_the_examples_precede_the_question_as_alternating_turns(
    context: PromptContext,
) -> None:
    client = FakeAnthropic([PLAN])
    SqlWriter(client).write(QUESTION, context=context)

    messages = client.calls[0]["messages"]
    assert len(messages) == 2 * len(context.examples) + 1
    for index, example in enumerate(context.examples):
        user, assistant = messages[2 * index], messages[2 * index + 1]
        assert user == {"role": "user", "content": example.question}
        assert assistant["role"] == "assistant"
        assert SqlPlan.model_validate(json.loads(assistant["content"])) == example.plan
    assert messages[-1] == {"role": "user", "content": QUESTION}


def test_a_repair_turn_lists_each_prior_sql_and_its_error(context: PromptContext) -> None:
    client = FakeAnthropic([PLAN])
    attempts = [
        Attempt(sql="SELECT * FROM ticket", error="no such table: ticket"),
        Attempt(sql="SELECT COUNT(*) FROM tickets WHERE sold = 1", error="no such column: sold"),
    ]

    SqlWriter(client).write(QUESTION, context=context, attempts=attempts)

    final = client.calls[0]["messages"][-1]["content"]
    assert final.startswith(QUESTION)
    for attempt in attempts:
        assert attempt.sql in final
        assert attempt.error in final
    assert "corrected query" in final


def test_the_result_carries_the_model_token_counts_and_elapsed_time(
    context: PromptContext,
) -> None:
    result = SqlWriter(FakeAnthropic([PLAN])).write(QUESTION, context=context)
    assert result.model == FAKE_MODEL
    assert result.input_tokens == FAKE_INPUT_TOKENS
    assert result.output_tokens == FAKE_OUTPUT_TOKENS
    assert result.elapsed_ms >= 0


@pytest.mark.parametrize(
    ("scripted", "expected", "code"),
    [
        (authentication_error(), ApiKeyError, "missing_api_key"),
        (rate_limit_error(), ModelRateLimited, "rate_limited"),
        (api_timeout_error(), ModelTimeout, "model_timeout"),
        (api_connection_error(), ModelTimeout, "model_timeout"),
        (api_status_error(500), ModelError, "model_error"),
        (refusal(), ModelRefused, "model_refused"),
        ("not a plan", ModelRefused, "model_refused"),
    ],
    ids=["auth", "rate-limit", "timeout", "connection", "status", "refusal", "no-plan"],
)
def test_each_api_failure_becomes_a_named_error(
    context: PromptContext, scripted: object, expected: type, code: str
) -> None:
    with pytest.raises(expected) as raised:
        SqlWriter(FakeAnthropic([scripted])).write(QUESTION, context=context)
    assert raised.value.code == code


@pytest.mark.parametrize(
    ("scripted", "output_tokens"),
    [
        (refusal(), 0),
        ("not a plan", FAKE_OUTPUT_TOKENS),
        ('{"answerable": true, "sql": ""}', FAKE_OUTPUT_TOKENS),
    ],
    ids=["refusal", "not-json", "off-schema"],
)
def test_a_refusal_carries_the_tokens_the_call_was_billed_for(
    context: PromptContext, scripted: object, output_tokens: int
) -> None:
    with pytest.raises(ModelRefused) as raised:
        SqlWriter(FakeAnthropic([scripted])).write(QUESTION, context=context)
    assert raised.value.input_tokens == FAKE_INPUT_TOKENS
    assert raised.value.output_tokens == output_tokens


def test_an_sdk_error_carries_no_tokens_because_nothing_came_back(
    context: PromptContext,
) -> None:
    with pytest.raises(ModelRateLimited) as raised:
        SqlWriter(FakeAnthropic([rate_limit_error()])).write(QUESTION, context=context)
    assert not hasattr(raised.value, "input_tokens")


def test_a_missing_key_is_refused_before_any_client_is_built(
    context: PromptContext, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "  ")

    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError("anthropic.Anthropic must not be constructed without a key")

    monkeypatch.setattr(anthropic, "Anthropic", refuse)
    with pytest.raises(ApiKeyError) as raised:
        SqlWriter().write(QUESTION, context=context)
    assert raised.value.code == "missing_api_key"


def test_the_real_client_is_built_lazily_with_the_timeout_and_one_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    built: list[dict] = []
    monkeypatch.setattr(anthropic, "Anthropic", lambda **kwargs: built.append(kwargs) or object())

    writer = SqlWriter(timeout_s=7)
    assert built == []
    writer._get_client()
    assert built == [{"timeout": 7, "max_retries": 1}]
