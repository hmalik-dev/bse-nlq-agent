"""One call that turns a question into an answer: the fixed pipeline, end to end.

Build the prompt, ask for SQL, check it, run it, write the answer. When the SQL
fails, the error goes back to the model at most twice. Every outcome is one of
five statuses, and nothing raised inside ever escapes `ask`.
"""

from __future__ import annotations

import logging
import math
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import date
from typing import Any

from nlq import config
from nlq.agent.answer import AnswerWriter
from nlq.agent.context import Example, PromptContext, build_context, load_examples
from nlq.agent.errors import ModelRefused, NlqError, UnsafeSql
from nlq.agent.executor import Executor, QueryResult
from nlq.agent.llm import SqlWriter
from nlq.agent.models import (
    AnswerText,
    AskResult,
    Attempt,
    ChartSpec,
    ErrorInfo,
    LlmResult,
    SqlPlan,
    Step,
    Trace,
)
from nlq.agent.sql_guard import guard
from nlq.pricing import DECIMALS, cost_usd

logger = logging.getLogger("nlq")

MAX_REPAIRS = 2
ANSWER_ROW_CAP = 50
CHART_MIN_ROWS = 2
CHART_MAX_ROWS = 25
SUGGESTION_COUNT = 3

BLOCKED_ANSWER = (
    "This request was refused before anything ran: the agent only reads data, "
    "and its database connection is read-only."
)
INTERNAL_MESSAGE = "Something went wrong."


class Agent:
    """`ask(question)` and nothing else. The UI, the evaluation and the tests all call it."""

    def __init__(
        self, sql_writer: Any, executor: Executor, answer_writer: Any, *, today: date
    ) -> None:
        self.sql_writer = sql_writer
        self.executor = executor
        self.answer_writer = answer_writer
        self.today = today

    @classmethod
    def from_env(cls, today: date | None = None) -> Agent:
        """Wire the real components. Never raises: the key and the database are checked on use."""
        return cls(
            SqlWriter(),
            Executor(config.DATABASE_PATH),
            AnswerWriter(),
            today=config.today() if today is None else today,
        )

    def ask(self, question: str) -> AskResult:
        """Answer one question; every failure comes back as a result, never an exception."""
        run = _Run(question, self.sql_writer.model)
        try:
            return self._pipeline(question, run)
        except NlqError as error:
            return run.failed(error.code, error.message)
        except Exception:
            logger.exception("Unexpected failure while answering a question")
            return run.failed("internal", INTERNAL_MESSAGE)

    def _pipeline(self, question: str, run: _Run) -> AskResult:
        with run.step("Reading schema"):
            context = build_context(self.today)
        attempts: list[Attempt] = []
        while True:
            plan = self._write_sql(question, context, attempts, run)
            if not plan.answerable:
                return _declined(run, plan, context)
            run.sql = plan.sql
            try:
                query = self._guard_and_run(plan.sql or "", run)
            except UnsafeSql:
                return run.finish("blocked", answer=BLOCKED_ANSWER, sql=plan.sql)
            except NlqError as error:
                if not error.repairable:
                    raise
                if len(attempts) == MAX_REPAIRS:
                    return run.failed("repairs_exhausted", error.message)
                attempts.append(Attempt(sql=plan.sql or "", error=error.message))
                continue
            return self._answer(question, plan, query, run, context)

    def _write_sql(
        self, question: str, context: PromptContext, attempts: list[Attempt], run: _Run
    ) -> SqlPlan:
        run.repairs = len(attempts)
        with run.step("Writing SQL"):
            result = _priced(
                run,
                self.sql_writer.model,
                lambda: self.sql_writer.write(question, context=context, attempts=attempts),
            )
        return result.plan

    def _guard_and_run(self, sql: str, run: _Run) -> QueryResult:
        with run.step("Checking safety"):
            guarded = guard(sql, max_rows=self.executor.max_rows)
        run.sql = guarded.sql
        with run.step("Running query"):
            return self.executor.run(guarded.sql)

    def _answer(
        self, question: str, plan: SqlPlan, query: QueryResult, run: _Run, context: PromptContext
    ) -> AskResult:
        if query.row_count == 0:
            return run.finish(
                "empty",
                sql=run.sql,
                assumptions=plan.assumptions,
                columns=query.columns,
                suggestions=example_questions(context.examples),
            )
        with run.step("Writing answer"):
            answer = _priced(
                run,
                self.answer_writer.model,
                lambda: self.answer_writer.write(
                    question,
                    plan.assumptions,
                    query.columns,
                    query.rows[:ANSWER_ROW_CAP],
                    query.row_count,
                    query.truncated,
                ),
            )
        return run.finish(
            "answered",
            answer=answer.text,
            sql=run.sql,
            assumptions=plan.assumptions,
            columns=query.columns,
            rows=query.rows,
            row_count=query.row_count,
            truncated=query.truncated,
            chart=chart_for(query),
        )


def _priced[Priced: (LlmResult, AnswerText)](
    run: _Run, model: str, call: Callable[[], Priced]
) -> Priced:
    """Make one model call and bill it, whether the model answered or refused.

    A refusal still cost the tokens it read, so it is charged before it is
    re-raised; an SDK failure never returned a response and charges nothing.
    """
    try:
        result = call()
    except ModelRefused as refused:
        run.charge(model, refused.input_tokens, refused.output_tokens)
        raise
    run.charge(model, result.input_tokens, result.output_tokens)
    return result


def _declined(run: _Run, plan: SqlPlan, context: PromptContext) -> AskResult:
    """A plan the model would not write: refused outright, or beyond what the data holds."""
    if plan.decline_category == "destructive":
        return run.finish("blocked", answer=BLOCKED_ANSWER)
    return run.finish(
        "unanswerable",
        answer=plan.decline_reason or "",
        suggestions=example_questions(context.examples),
    )


def example_questions(examples: tuple[Example, ...]) -> list[str]:
    """The first answerable worked examples: questions a chip can ask and get an answer to.

    Offered when a question returned no rows or cannot be answered, so a suggestion
    is never advice ("try a wider date range") that the agent would itself decline.
    """
    answerable = (example.question for example in examples if example.plan.answerable)
    return list(answerable)[:SUGGESTION_COUNT]


# What an empty result offers with the shipped worked examples; the fake agent shows it too.
EMPTY_SUGGESTIONS = example_questions(load_examples())


def chart_for(query: QueryResult) -> ChartSpec | None:
    """A bar chart fits when there is one label column, one numeric column and a few rows."""
    if len(query.columns) != 2 or not CHART_MIN_ROWS <= query.row_count <= CHART_MAX_ROWS:
        return None
    labels = all(isinstance(row[0], str) for row in query.rows)
    values = all(row[1] is None or isinstance(row[1], (int, float)) for row in query.rows)
    if not (labels and values):
        return None
    return ChartSpec(x=query.columns[0], y=query.columns[1])


class _Run:
    """The ledger for one ask: step timings, tokens, dollars, repairs and the latest SQL."""

    def __init__(self, question: str, model: str) -> None:
        self.question = question
        self.model = model
        self.started = time.monotonic()
        self.steps: dict[str, int] = {}
        self.repairs = 0
        self.input_tokens = 0
        self.output_tokens = 0
        self.cost_usd = 0.0
        self.sql: str | None = None

    @contextmanager
    def step(self, name: str) -> Iterator[None]:
        """Time one stage, adding to the same step when a repair runs it again."""
        started = time.monotonic()
        try:
            yield
        finally:
            self.steps[name] = self.steps.get(name, 0) + _elapsed_ms(started)

    def charge(self, model: str, input_tokens: int, output_tokens: int) -> None:
        self.input_tokens += input_tokens
        self.output_tokens += output_tokens
        self.cost_usd += cost_usd(model, input_tokens, output_tokens)

    def failed(self, code: str, message: str) -> AskResult:
        return self.finish("error", sql=self.sql, error=ErrorInfo(code=code, message=message))

    def finish(self, status: str, **fields: Any) -> AskResult:
        trace = Trace(
            steps=[Step(name=name, ms=ms) for name, ms in self.steps.items()],
            repairs=self.repairs,
            model=self.model,
            total_ms=_elapsed_ms(self.started),
            input_tokens=self.input_tokens,
            output_tokens=self.output_tokens,
            cost_usd=round(self.cost_usd, DECIMALS),
        )
        return AskResult(status=status, question=self.question, trace=trace, **fields)


def _elapsed_ms(started: float) -> int:
    """Whole milliseconds since `started`, rounded up so a stage that ran never reads 0."""
    return math.ceil((time.monotonic() - started) * 1000)
