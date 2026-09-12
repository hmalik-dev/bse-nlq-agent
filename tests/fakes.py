"""A scripted stand-in for the Anthropic client, so no test needs a key or a network.

Every ticket that talks to the model tests against this: script the responses,
run the code, then read `.calls` to see exactly what would have been sent.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import anthropic
import httpx2

from nlq.agent.models import SqlPlan

FAKE_MODEL = "claude-fake"
FAKE_INPUT_TOKENS = 1200
FAKE_OUTPUT_TOKENS = 80


@dataclass
class FakeUsage:
    input_tokens: int
    output_tokens: int


@dataclass
class FakeTextBlock:
    text: str
    type: str = "text"


@dataclass
class FakeResponse:
    """The fields the writers read from a real `Message`."""

    content: list[FakeTextBlock]
    usage: FakeUsage
    stop_reason: str = "end_turn"
    model: str = FAKE_MODEL


Scripted = SqlPlan | str | Exception | FakeResponse


@dataclass
class FakeMessages:
    """Stands in for `client.messages`; pops one scripted response per call."""

    responses: list[Scripted]
    calls: list[dict] = field(default_factory=list)

    def create(self, **kwargs) -> FakeResponse:
        return self._respond(kwargs)

    def _respond(self, kwargs: dict) -> FakeResponse:
        self.calls.append(kwargs)
        if not self.responses:
            raise AssertionError("FakeAnthropic ran out of scripted responses")
        scripted = self.responses.pop(0)
        if isinstance(scripted, Exception):
            raise scripted
        if isinstance(scripted, FakeResponse):
            return scripted
        usage = FakeUsage(FAKE_INPUT_TOKENS, FAKE_OUTPUT_TOKENS)
        text = scripted.model_dump_json() if isinstance(scripted, SqlPlan) else scripted
        return FakeResponse([FakeTextBlock(text)], usage)


class FakeAnthropic:
    """`FakeAnthropic([plan, "text", error])` answers three calls in that order.

    A `SqlPlan` comes back as its JSON in a text content block, a `str` as the
    text itself, an `Exception` is raised, and a `FakeResponse` is returned as
    scripted (for a refusal, say).
    """

    def __init__(self, responses: list[Scripted]) -> None:
        self.messages = FakeMessages(list(responses))

    @property
    def calls(self) -> list[dict]:
        return self.messages.calls


def refusal() -> FakeResponse:
    """A response the API stopped with `stop_reason == "refusal"` and no plan."""
    return FakeResponse([], FakeUsage(FAKE_INPUT_TOKENS, 0), stop_reason="refusal")


def _response(status: int) -> httpx2.Response:
    request = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    return httpx2.Response(status, request=request)


def authentication_error() -> anthropic.AuthenticationError:
    return anthropic.AuthenticationError("invalid x-api-key", response=_response(401), body=None)


def rate_limit_error() -> anthropic.RateLimitError:
    return anthropic.RateLimitError("rate limited", response=_response(429), body=None)


def api_timeout_error() -> anthropic.APITimeoutError:
    return anthropic.APITimeoutError(request=_response(408).request)


def api_connection_error() -> anthropic.APIConnectionError:
    return anthropic.APIConnectionError(request=_response(503).request)


def api_status_error(status: int = 500) -> anthropic.APIStatusError:
    return anthropic.APIStatusError("upstream failure", response=_response(status), body=None)
