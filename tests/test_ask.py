"""The command line prints the result as JSON and only a missing key changes the exit code."""

from __future__ import annotations

import json

import pytest

from nlq.agent.models import AskResult, ErrorInfo, Trace
from nlq.ask import EXIT_MISSING_KEY, EXIT_USAGE, USAGE, main

TRACE = Trace(
    steps=[], repairs=0, model="fake", total_ms=1, input_tokens=0, output_tokens=0, cost_usd=0.0
)


class StubAgent:
    def __init__(self, result: AskResult) -> None:
        self.result = result
        self.questions: list[str] = []

    def ask(self, question: str) -> AskResult:
        self.questions.append(question)
        return self.result


def test_a_result_is_printed_as_indented_json(capsys: pytest.CaptureFixture[str]) -> None:
    agent = StubAgent(AskResult(status="empty", question="q", trace=TRACE))

    code = main(["How many tickets did we sell last month?"], agent=agent)

    assert code == 0
    assert agent.questions == ["How many tickets did we sell last month?"]
    printed = capsys.readouterr().out
    assert json.loads(printed)["status"] == "empty"
    assert printed.startswith("{\n  ")


def test_a_missing_key_exits_two_with_one_line(capsys: pytest.CaptureFixture[str]) -> None:
    error = ErrorInfo(code="missing_api_key", message="ANTHROPIC_API_KEY is not set.")
    agent = StubAgent(AskResult(status="error", question="q", trace=TRACE, error=error))

    code = main(["q"], agent=agent)

    assert code == EXIT_MISSING_KEY
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "ANTHROPIC_API_KEY is not set.\n"


def test_any_other_error_still_exits_zero() -> None:
    error = ErrorInfo(code="rate_limited", message="Try again shortly.")
    agent = StubAgent(AskResult(status="error", question="q", trace=TRACE, error=error))
    assert main(["q"], agent=agent) == 0


def test_a_question_over_the_length_cap_is_refused_before_the_agent_runs(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("NLQ_MAX_QUESTION_CHARS", "10")
    agent = StubAgent(AskResult(status="empty", question="q", trace=TRACE))

    code = main(["x" * 11], agent=agent)

    assert code == EXIT_USAGE
    assert agent.questions == []
    assert capsys.readouterr().err == "The question must be at most 10 characters.\n"


def test_a_question_at_the_length_cap_is_asked_trimmed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NLQ_MAX_QUESTION_CHARS", "10")
    agent = StubAgent(AskResult(status="empty", question="q", trace=TRACE))

    assert main(["  " + "x" * 10 + "  "], agent=agent) == 0
    assert agent.questions == ["x" * 10]


def test_the_question_is_required(capsys: pytest.CaptureFixture[str]) -> None:
    assert (
        main([], agent=StubAgent(AskResult(status="empty", question="q", trace=TRACE)))
        == EXIT_USAGE
    )
    assert "usage" in capsys.readouterr().err


def test_a_blank_question_is_a_usage_error(capsys: pytest.CaptureFixture[str]) -> None:
    agent = StubAgent(AskResult(status="empty", question="q", trace=TRACE))

    assert main(["   "], agent=agent) == EXIT_USAGE
    assert agent.questions == []
    assert capsys.readouterr().err == USAGE + "\n"
