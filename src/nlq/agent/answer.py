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
from nlq.agent.llm import connect, map_api_error, response_text, response_usage
from nlq.agent.models import AnswerText

MAX_TOKENS = 400
# A result up to this many rows names every row; past it, the sentence names the
# top few and points at the table, which carries the rest at full precision.
LIST_EVERY_ROW_LIMIT = 5
TOP_ROWS_PAST_LIMIT = 3
SYSTEM_PROMPT = f"""\
You write the answer to a business user's question from a table of query results.
The table and a chart sit directly below your sentence and keep the exact values.

- Answer in at most two sentences, using only the rows given. Never add facts,
  estimates or context that are not in the table.
- Format numbers with thousands separators, and currency with a dollar sign.
- When the result has more than one row, write money of $10K or more compactly,
  with one decimal and K, M or B: $203.1M, $57.5M, $48.3K, $1.2B. Money under $10K
  stays exact ($84.50). Counts are never compacted (48,210 tickets).
- When the result has one row, state every figure exactly ($1,284,310.42).
- The assumptions describe how the question was interpreted; reflect them where
  they change the meaning of the answer.
- When the question asks how many or how much and the results end with a Total
  line, state that total first. Never add up rows yourself.
- For a ranking or breakdown, name the leader with its figure, then the rest in
  order with their figures in parentheses, in one sentence.
- Up to {LIST_EVERY_ROW_LIMIT} rows, name every row. Past that, give the total (or the leader),
  name only the top {TOP_ROWS_PAST_LIMIT}, and end with "and N more in the results below".
- When the result was truncated, say that only the first rows are shown, and end
  with "see the results below", never a count of rows you cannot see.
- Follow the Answer shape line: it is counted for you, so never count rows yourself.

Examples (the figures are illustrative):
- 5 rows: NBA leads event revenue at $203.1M, followed by WNBA ($137.5M), Concert ($57.5M), \
Family Show ($10.8M) and Boxing ($10.3M).
- 16 rows with a Total line: We sold 67,522 tickets for 16 Nets home games last month, \
led by Brooklyn Nets vs. New York Knicks (6,210), Brooklyn Nets vs. Boston Celtics (5,880) \
and Brooklyn Nets vs. Miami Heat (5,402), and 13 more in the results below."""


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
    lines.extend([answer_shape(len(rows), row_count, truncated), ""])
    lines.append(f"Results ({_row_summary(len(rows), row_count, truncated)}):")
    lines.append(" | ".join(columns))
    lines.extend(" | ".join(_cell(value) for value in row) for row in rows)
    total = count_total(columns, rows, row_count, truncated)
    if total is not None:
        lines.extend(["", total])
    return "\n".join(lines)


def count_total(
    columns: Sequence[str],
    rows: Sequence[Sequence[object]],
    row_count: int,
    truncated: bool,
) -> str | None:
    """The sum of a whole-number last column, when every row of a breakdown is shown.

    Counted in code so the sentence can never disagree with the table; averages,
    percentages and money are floats and are never summed.
    """
    if truncated or len(rows) < 2 or len(rows) != row_count:
        return None
    values = [row[-1] for row in rows]
    if not all(isinstance(value, int) and not isinstance(value, bool) for value in values):
        return None
    return f"Total {columns[-1]} across all {row_count} rows: {sum(values)}"


def answer_shape(shown: int, row_count: int, truncated: bool) -> str:
    """How much of the result the sentence names, decided in code so the model never counts."""
    if truncated or shown < row_count:
        return (
            f"Answer shape: only the first rows are shown, so name the top {TOP_ROWS_PAST_LIMIT}, "
            'say that only the first rows are shown, and end with "see the results below".'
        )
    if row_count <= 1:
        return "Answer shape: one row, so state every figure exactly."
    if row_count <= LIST_EVERY_ROW_LIMIT:
        return f"Answer shape: {row_count} rows, so name every row."
    more = row_count - TOP_ROWS_PAST_LIMIT
    return (
        f"Answer shape: {row_count} rows, so name the top {TOP_ROWS_PAST_LIMIT} "
        f'and end with "and {more} more in the results below".'
    )


def _row_summary(shown: int, row_count: int, truncated: bool) -> str:
    counted = f"{shown} of {row_count} rows shown" if shown < row_count else f"{row_count} rows"
    return f"{counted}, and the query result itself was truncated" if truncated else counted


def _cell(value: object) -> str:
    return "NULL" if value is None else str(value)


def _result(response: Any, started: float) -> AnswerText:
    usage = response_usage(response)
    text = response_text(response)
    if response.stop_reason == "refusal" or not text:
        raise ModelRefused("The model did not write an answer.", **usage)
    return AnswerText(
        text=text,
        model=response.model,
        elapsed_ms=int((time.monotonic() - started) * 1000),
        **usage,
    )
