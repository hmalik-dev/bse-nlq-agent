"""A stand-in Anthropic client for `eval.run --fake`.

It answers each golden question the way a perfect model would - the reference
query, or the right kind of decline - and raises on one question, so a fake
sweep walks the runner through every status without a key or a network.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import anthropic
import httpx2

from eval.score import GoldenEntry
from nlq.agent.models import SqlPlan

ERROR_ENTRY_ID = "tickets-sold-yesterday"
FAKE_ANSWER = "This is a fake answer written without a model."
SQL_CALL_TOKENS = (4000, 120)
ANSWER_CALL_TOKENS = (600, 60)


@dataclass
class _Usage:
    input_tokens: int
    output_tokens: int


@dataclass
class _TextBlock:
    text: str
    type: str = "text"


@dataclass
class _Response:
    content: list[_TextBlock]
    usage: _Usage
    model: str
    stop_reason: str = "end_turn"


@dataclass
class _Messages:
    """Stands in for `client.messages`, keyed by the question in the final user turn."""

    by_question: dict[str, GoldenEntry]
    calls: list[dict] = field(default_factory=list)

    def create(self, **kwargs) -> _Response:
        self.calls.append(kwargs)
        if "output_config" in kwargs:
            return self._plan(kwargs)
        return _Response([_TextBlock(FAKE_ANSWER)], _Usage(*ANSWER_CALL_TOKENS), kwargs["model"])

    def _plan(self, kwargs: dict) -> _Response:
        """The SQL call: the one that asks for a structured plan."""
        question = kwargs["messages"][-1]["content"].splitlines()[0]
        entry = self.by_question[question]
        if entry.id == ERROR_ENTRY_ID:
            raise anthropic.APIConnectionError(request=_request())
        plan = plan_for(entry)
        return _Response(
            [_TextBlock(plan.model_dump_json())], _Usage(*SQL_CALL_TOKENS), kwargs["model"]
        )


class GoldenFakeClient:
    """`GoldenFakeClient(entries)` answers every golden question from its own entry."""

    def __init__(self, entries: list[GoldenEntry]) -> None:
        self.messages = _Messages({entry.question: entry for entry in entries})

    @property
    def calls(self) -> list[dict]:
        return self.messages.calls


def plan_for(entry: GoldenEntry) -> SqlPlan:
    """The plan a perfect model would return for `entry`."""
    if entry.expect == "unanswerable":
        return SqlPlan(
            answerable=False,
            decline_reason="The data cannot answer this.",
            decline_category="out_of_scope",
        )
    if entry.expect == "blocked":
        return SqlPlan(
            answerable=False,
            decline_reason="This tool only reads data.",
            decline_category="destructive",
        )
    return SqlPlan(answerable=True, sql=entry.sql, assumptions=["Reference query."])


def _request() -> httpx2.Request:
    return httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
