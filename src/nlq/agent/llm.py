"""One call to Claude that turns a question into a validated `SqlPlan`.

The examples ride along as prior conversation turns, the plan comes back as a
structured output, and every way the API can fail becomes a named `NlqError`.
"""

from __future__ import annotations

import time
from collections.abc import Sequence
from typing import Any

import anthropic
import pydantic

from nlq import config
from nlq.agent.context import PromptContext
from nlq.agent.errors import (
    ApiKeyError,
    ModelError,
    ModelRateLimited,
    ModelRefused,
    ModelTimeout,
    NlqError,
)
from nlq.agent.models import Attempt, LlmResult, SqlPlan

MAX_TOKENS = 2048
REPAIR_INSTRUCTION = (
    "Earlier queries for this question failed. Write a corrected query that avoids these errors:"
)


class SqlWriter:
    """Asks the model for a `SqlPlan`, with a repair turn when earlier attempts failed."""

    def __init__(
        self,
        client: Any = None,
        *,
        model: str | None = None,
        timeout_s: float | None = None,
    ) -> None:
        self._client = client
        self.model = model or config.sql_model()
        self.timeout_s = config.llm_timeout_s() if timeout_s is None else timeout_s

    def write(
        self, question: str, *, context: PromptContext, attempts: Sequence[Attempt] = ()
    ) -> LlmResult:
        """Return the model's plan for `question`, or raise a typed error."""
        client = self._get_client()
        started = time.monotonic()
        try:
            response = client.messages.parse(
                model=self.model,
                max_tokens=MAX_TOKENS,
                system=context.system,
                messages=build_messages(question, context, attempts),
                output_format=SqlPlan,
            )
        except anthropic.AnthropicError as error:
            raise map_api_error(error) from error
        except pydantic.ValidationError as error:
            raise ModelRefused(f"The model's plan did not fit the schema: {error}") from error
        return _result(response, started)

    def _get_client(self) -> Any:
        """Build the real client on first use; refuse before that without a key."""
        if self._client is None:
            if not config.anthropic_api_key():
                raise ApiKeyError("ANTHROPIC_API_KEY is not set. Add it to .env.")
            self._client = anthropic.Anthropic(timeout=self.timeout_s, max_retries=1)
        return self._client


def build_messages(
    question: str, context: PromptContext, attempts: Sequence[Attempt] = ()
) -> list[dict[str, str]]:
    """The examples as alternating turns, then the question as the final user turn."""
    messages: list[dict[str, str]] = []
    for example in context.examples:
        messages.append({"role": "user", "content": example.question})
        messages.append({"role": "assistant", "content": example.plan.model_dump_json()})
    messages.append({"role": "user", "content": _final_turn(question, attempts)})
    return messages


def _final_turn(question: str, attempts: Sequence[Attempt]) -> str:
    if not attempts:
        return question
    lines = [question, "", REPAIR_INSTRUCTION]
    for number, attempt in enumerate(attempts, start=1):
        lines.extend(["", f"Attempt {number}:", attempt.sql, f"Error: {attempt.error}"])
    return "\n".join(lines)


def _result(response: Any, started: float) -> LlmResult:
    plan = response.parsed_output
    if response.stop_reason == "refusal" or plan is None:
        raise ModelRefused("The model declined to produce a plan for this question.")
    return LlmResult(
        plan=plan,
        model=response.model,
        input_tokens=response.usage.input_tokens,
        output_tokens=response.usage.output_tokens,
        elapsed_ms=int((time.monotonic() - started) * 1000),
    )


def map_api_error(error: anthropic.AnthropicError) -> NlqError:
    """Name an SDK failure. Shared with the answer writer so both speak the same codes."""
    if isinstance(error, anthropic.AuthenticationError):
        return ApiKeyError("The Anthropic API rejected the API key. Check ANTHROPIC_API_KEY.")
    if isinstance(error, anthropic.RateLimitError):
        return ModelRateLimited("The model is rate limited right now. Try again shortly.")
    if isinstance(error, anthropic.APIConnectionError):  # APITimeoutError is a subclass
        return ModelTimeout("The model did not respond in time.")
    return ModelError(f"The model call failed: {error}")
