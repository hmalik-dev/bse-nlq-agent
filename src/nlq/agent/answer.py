"""The second model call: a plain-English answer written from the rows alone.

The writer never sees the database or the SQL. It is handed the question, the
assumptions and a small table, and asked to describe what is there.
"""

from __future__ import annotations

import time
from collections.abc import Sequence
from typing import Any

import anthropic

from nlq import config
from nlq.agent.errors import ModelRefused
from nlq.agent.llm import connect, map_api_error
from nlq.agent.models import AnswerText

MAX_TOKENS = 400
SYSTEM_PROMPT = """\
You write the answer to a business user's question from a table of query results.

- Answer in at most two sentences, using only the rows given. Never add facts,
  estimates or context that are not in the table.
- Format numbers with thousands separators, and currency with a dollar sign.
- The assumptions describe how the question was interpreted; reflect them where
  they change the meaning of the answer.
- When the result was truncated, say that only the first rows are shown."""


class AnswerWriter:
    """Turns query rows into one or two sentences."""

    def __init__(
        self,
        client: Any = None,
        *,
        model: str | None = None,
        timeout_s: float | None = None,
    ) -> None:
        self._client = client
        self.model = model or config.answer_model()
        self.timeout_s = config.llm_timeout_s() if timeout_s is None else timeout_s

    def write(
        self,
        question: str,
        assumptions: Sequence[str],
        columns: Sequence[str],
        rows: Sequence[Sequence[object]],
        row_count: int,
        truncated: bool,
    ) -> AnswerText:
        """Return the model's answer for `question`, or raise a typed error."""
        if self._client is None:
            self._client = connect(self.timeout_s)
        user_turn = build_user_turn(question, assumptions, columns, rows, row_count, truncated)
        started = time.monotonic()
        try:
            response = self._client.messages.create(
                model=self.model,
                max_tokens=MAX_TOKENS,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_turn}],
            )
        except anthropic.AnthropicError as error:
            raise map_api_error(error) from error
        return _result(response, started)


def build_user_turn(
    question: str,
    assumptions: Sequence[str],
    columns: Sequence[str],
    rows: Sequence[Sequence[object]],
    row_count: int,
    truncated: bool,
) -> str:
    """The question, the assumptions and the rows as a compact pipe-separated table."""
    lines = [f"Question: {question}", ""]
    if assumptions:
        lines.append("Assumptions:")
        lines.extend(f"- {assumption}" for assumption in assumptions)
        lines.append("")
    lines.append(f"Results ({_row_summary(len(rows), row_count, truncated)}):")
    lines.append(" | ".join(columns))
    lines.extend(" | ".join(_cell(value) for value in row) for row in rows)
    return "\n".join(lines)


def _row_summary(shown: int, row_count: int, truncated: bool) -> str:
    counted = f"{shown} of {row_count} rows shown" if shown < row_count else f"{row_count} rows"
    return f"{counted}, and the query result itself was truncated" if truncated else counted


def _cell(value: object) -> str:
    return "NULL" if value is None else str(value)


def _result(response: Any, started: float) -> AnswerText:
    text = "".join(block.text for block in response.content if block.type == "text").strip()
    if response.stop_reason == "refusal" or not text:
        raise ModelRefused("The model did not write an answer.")
    return AnswerText(
        text=text,
        model=response.model,
        input_tokens=response.usage.input_tokens,
        output_tokens=response.usage.output_tokens,
        elapsed_ms=int((time.monotonic() - started) * 1000),
    )
