"""The API key is sent to Anthropic and nowhere else: not a response, not the trace, not a log."""

from __future__ import annotations

import json
import logging
from datetime import date
from pathlib import Path

import anthropic
import httpx2
import pytest
from fastapi.testclient import TestClient

from nlq.agent.agent import Agent
from nlq.agent.answer import AnswerWriter
from nlq.agent.executor import Executor
from nlq.agent.llm import SqlWriter
from nlq.api import create_app

# Deliberately not shaped like a real key, so no secret scanner mistakes it for one.
FAKE_KEY = "fake-key-for-the-leak-test-0123456789"
TODAY = date(2026, 9, 11)


def _anthropic_answering(status: int, seen_keys: list[str], monkeypatch: pytest.MonkeyPatch):
    """Build the real SDK client, but over a transport that answers `status` with no network."""
    real_client = anthropic.Anthropic

    def respond(request: httpx2.Request) -> httpx2.Response:
        seen_keys.append(request.headers.get("x-api-key", ""))
        body = {"type": "error", "error": {"type": "api_error", "message": "upstream said no"}}
        return httpx2.Response(status, json=body)

    def build(**kwargs: object) -> anthropic.Anthropic:
        transport = httpx2.MockTransport(respond)
        return real_client(**kwargs, http_client=httpx2.Client(transport=transport))

    monkeypatch.setattr(anthropic, "Anthropic", build)


@pytest.mark.parametrize("status", [400, 401, 403, 404], ids=lambda status: f"http-{status}")
def test_the_key_never_reaches_a_response_the_trace_or_a_log(
    status: int,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", FAKE_KEY)
    monkeypatch.setenv("ANTHROPIC_LOG", "debug")
    seen_keys: list[str] = []
    _anthropic_answering(status, seen_keys, monkeypatch)
    agent = Agent(SqlWriter(), Executor(tmp_path / "absent.db"), AnswerWriter(), today=TODAY)
    api = TestClient(create_app(agent, static_dir=tmp_path / "static"), base_url="http://127.0.0.1")

    with caplog.at_level(logging.DEBUG):
        response = api.post("/api/ask", json={"question": "How many tickets did we sell?"})

    assert seen_keys == [FAKE_KEY]  # the key was really sent, so its absence below means something
    body = response.json()
    assert body["status"] == "error"
    assert FAKE_KEY not in response.text
    assert FAKE_KEY not in json.dumps(body["trace"])
    assert caplog.records, "nothing was logged, so the log half of this test proves nothing"
    for record in caplog.records:
        assert FAKE_KEY not in record.getMessage(), record.name
        assert FAKE_KEY not in (record.exc_text or ""), record.name
