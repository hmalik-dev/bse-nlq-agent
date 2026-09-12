"""The shapes that cross the model boundary: what it returns, and what it cost."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints, model_validator

MAX_ASSUMPTIONS = 3
MAX_ASSUMPTION_CHARS = 120

Assumption = Annotated[str, StringConstraints(max_length=MAX_ASSUMPTION_CHARS)]
DeclineCategory = Literal["out_of_scope", "destructive"]


class SqlPlan(BaseModel):
    """The model's structured answer: one read query, or a reason not to write one."""

    answerable: bool
    sql: str | None = None
    assumptions: list[Assumption] = Field(default_factory=list, max_length=MAX_ASSUMPTIONS)
    decline_reason: str | None = None
    decline_category: DeclineCategory | None = None

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
