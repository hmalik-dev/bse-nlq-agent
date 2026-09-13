"""The shapes that cross the model boundary: what it returns, and what it cost."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

MAX_ASSUMPTIONS = 3
MAX_ASSUMPTION_CHARS = 120

# The limits are asked for in the schema, but structured output cannot enforce
# them, so a plan that runs over is trimmed to three rather than thrown away.
Assumption = Annotated[str, Field(json_schema_extra={"maxLength": MAX_ASSUMPTION_CHARS})]
DeclineCategory = Literal["out_of_scope", "destructive"]


class SqlPlan(BaseModel):
    """The model's structured answer: one read query, or a reason not to write one."""

    answerable: bool
    sql: str | None = None
    assumptions: list[Assumption] = Field(
        default_factory=list, json_schema_extra={"maxItems": MAX_ASSUMPTIONS}
    )
    decline_reason: str | None = None
    decline_category: DeclineCategory | None = None

    @field_validator("assumptions")
    @classmethod
    def _at_most_three(cls, assumptions: list[str]) -> list[str]:
        return assumptions[:MAX_ASSUMPTIONS]

    @model_validator(mode="after")
    def _answerable_means_sql_and_declined_means_reason(self) -> SqlPlan:
        if self.answerable and not (self.sql or "").strip():
            raise ValueError("an answerable plan must carry SQL")
        if not self.answerable and not (self.decline_reason or "").strip():
            raise ValueError("a declined plan must say why")
        return self


class Attempt(BaseModel):
    """A query that was tried and the error it produced, fed back for repair."""

    sql: str
    error: str


class LlmResult(BaseModel):
    """A validated plan plus what the call cost, for the trace."""

    plan: SqlPlan
    model: str
    input_tokens: int
    output_tokens: int
    elapsed_ms: int


class AnswerText(BaseModel):
    """The written answer plus what the call cost, for the trace."""

    text: str
    model: str
    input_tokens: int
    output_tokens: int
    elapsed_ms: int


Status = Literal["answered", "empty", "unanswerable", "blocked", "error"]


class ChartSpec(BaseModel):
    """A hint that the result fits one bar chart: a label column and a value column."""

    type: Literal["bar"] = "bar"
    x: str
    y: str


class Step(BaseModel):
    """One stage of the pipeline and how long it took."""

    name: str
    ms: int


class Trace(BaseModel):
    """What the ask cost in time, tokens and dollars, and how many repairs it took."""

    steps: list[Step]
    repairs: int
    model: str
    total_ms: int
    input_tokens: int
    output_tokens: int
    cost_usd: float


class ErrorInfo(BaseModel):
    """A failure the interface can show: a stable code and a plain sentence."""

    code: str
    message: str


class AskResult(BaseModel):
    """Everything `Agent.ask` returns; the API serialises it unchanged."""

    status: Status
    question: str
    answer: str = ""
    assumptions: list[str] = Field(default_factory=list)
    sql: str | None = None
    columns: list[str] = Field(default_factory=list)
    rows: list[list] = Field(default_factory=list)
    row_count: int = 0
    truncated: bool = False
    chart: ChartSpec | None = None
    trace: Trace
    error: ErrorInfo | None = None
    suggestions: list[str] = Field(default_factory=list)
