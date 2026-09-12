"""The HTTP contract: 200 with a status for every agent outcome, 422 only for a bad body."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from nlq.agent.agent import INTERNAL_MESSAGE, Agent
from nlq.agent.fake import FakeAgent
from nlq.agent.models import AskResult, ErrorInfo, Trace
from nlq.api import UI_NOT_BUILT, app, create_app

TRACE = Trace(
    steps=[], repairs=0, model="fake", total_ms=1, input_tokens=0, output_tokens=0, cost_usd=0.0
)
RESULT_KEYS = {
    "status",
    "question",
    "answer",
    "assumptions",
    "sql",
    "columns",
    "rows",
    "row_count",
    "truncated",
    "chart",
    "trace",
    "error",
    "suggestions",
}
TABLE_NAMES = ["venues", "teams", "events", "customers", "orders", "tickets"]
QUESTION = "How many tickets did we sell last month?"


class StubAgent:
    def __init__(self, result: AskResult | None = None) -> None:
        self.result = result
        self.questions: list[str] = []

    def ask(self, question: str) -> AskResult:
        self.questions.append(question)
        return self.result or AskResult(status="empty", question=question, trace=TRACE)


class RaisingAgent:
    def ask(self, question: str) -> AskResult:
        raise RuntimeError("secret detail")


def result(status: str, **fields: object) -> AskResult:
    return AskResult(status=status, question=QUESTION, trace=TRACE, **fields)


@pytest.fixture(autouse=True)
def no_real_agent(monkeypatch: pytest.MonkeyPatch) -> None:
    """No test may build a real agent; the fake or a stub stands in."""

    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError("Agent.from_env must not be called in a test")

    monkeypatch.setattr(Agent, "from_env", refuse)
    monkeypatch.delenv("NLQ_FAKE_AGENT", raising=False)
    monkeypatch.delenv("NLQ_MAX_QUESTION_CHARS", raising=False)


@pytest.fixture
def unbuilt(tmp_path: Path) -> Path:
    """A static directory with no index.html in it."""
    return tmp_path / "static"


@pytest.fixture
def built(tmp_path: Path) -> Path:
    """A static directory shaped like a Vite build: index.html, assets/, and a public file."""
    static = tmp_path / "static"
    (static / "assets").mkdir(parents=True)
    (static / "brand").mkdir()
    (static / "index.html").write_text("<!doctype html><title>BSE Insights</title>")
    (static / "assets" / "app.js").write_text("console.log('hi')")
    (static / "brand" / "nets.svg").write_text("<svg/>")
    return static


def client(agent: object | None, static_dir: Path) -> TestClient:
    return TestClient(create_app(agent, static_dir=static_dir))


@pytest.mark.parametrize(
    "canned",
    [
        result("answered", answer="Five.", columns=["n"], rows=[[5]], row_count=1),
        result("empty", sql="SELECT 1", suggestions=["Try a wider date range."]),
        result("unanswerable", answer="No weather here.", suggestions=["q1", "q2", "q3"]),
        result("blocked", answer="Refused.", sql="DELETE FROM tickets"),
        result("error", error=ErrorInfo(code="rate_limited", message="Slow down.")),
    ],
    ids=lambda canned: canned.status,
)
def test_ask_returns_200_with_the_result_for_every_status(canned: AskResult, unbuilt: Path) -> None:
    agent = StubAgent(canned)

    response = client(agent, unbuilt).post("/api/ask", json={"question": QUESTION})

    assert response.status_code == 200
    assert response.json() == canned.model_dump()
    assert set(response.json()) == RESULT_KEYS
    assert agent.questions == [QUESTION]


def test_ask_trims_the_question_before_handing_it_to_the_agent(unbuilt: Path) -> None:
    agent = StubAgent()
    response = client(agent, unbuilt).post("/api/ask", json={"question": "  hello  "})
    assert response.status_code == 200
    assert agent.questions == ["hello"]


@pytest.mark.parametrize(
    "body",
    [{}, {"question": ""}, {"question": "   \n"}, {"question": "x" * 501}, {"question": 7}],
    ids=["missing", "empty", "whitespace", "over-long", "not-a-string"],
)
def test_ask_rejects_a_malformed_body_with_422_before_the_agent_runs(
    body: dict, unbuilt: Path
) -> None:
    agent = StubAgent()

    response = client(agent, unbuilt).post("/api/ask", json=body)

    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", "question"]
    assert agent.questions == []


def test_the_length_cap_is_read_from_the_environment(
    monkeypatch: pytest.MonkeyPatch, unbuilt: Path
) -> None:
    monkeypatch.setenv("NLQ_MAX_QUESTION_CHARS", "10")
    api = client(StubAgent(), unbuilt)
    assert api.post("/api/ask", json={"question": "x" * 10}).status_code == 200
    assert api.post("/api/ask", json={"question": "x" * 11}).status_code == 422


def test_an_agent_that_raises_becomes_an_internal_error_without_the_detail(
    unbuilt: Path, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.ERROR, logger="nlq"):
        response = client(RaisingAgent(), unbuilt).post("/api/ask", json={"question": QUESTION})

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "error"
    assert body["error"] == {"code": "internal", "message": INTERNAL_MESSAGE}
    assert body["question"] == QUESTION
    assert "secret detail" not in response.text and "Traceback" not in response.text
    logged = [record for record in caplog.records if record.name == "nlq"]
    assert len(logged) == 1 and "secret detail" in logged[0].exc_text


def test_schema_lists_six_tables_in_order_with_typed_columns_and_definitions(
    unbuilt: Path,
) -> None:
    body = client(StubAgent(), unbuilt).get("/api/schema").json()

    assert [table["name"] for table in body["tables"]] == TABLE_NAMES
    assert set(body) == {"tables", "definitions"}
    assert len(body["definitions"]) >= 3
    assert any("Revenue" in rule for rule in body["definitions"])
    tickets = body["tables"][5]
    assert tickets["description"].startswith("One row per seat")
    by_name = {column["name"]: column for column in tickets["columns"]}
    assert by_name["price"] == {
        "name": "price",
        "type": "REAL",
        "description": "Face value paid, excluding fee. 0 for comps.",
    }
    assert by_name["ticket_id"]["type"] == "INTEGER"
    assert by_name["status"]["type"] == "TEXT"
    assert len(by_name) == 8


def test_examples_are_the_six_chips_with_the_nets_and_liberty_badges(unbuilt: Path) -> None:
    body = client(StubAgent(), unbuilt).get("/api/examples").json()

    assert len(body) == 6
    assert body[0] == {
        "question": "How many tickets did we sell for Nets home games last month?",
        "badge": "nets",
    }
    assert body[3] == {
        "question": "Which Liberty home games sold the most tickets this season?",
        "badge": "liberty",
    }
    assert [entry["badge"] for entry in body] == ["nets", None, None, "liberty", None, None]


def test_health_reports_whether_the_database_file_exists(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, unbuilt: Path
) -> None:
    database = tmp_path / "tickets.db"
    monkeypatch.setenv("NLQ_DATABASE_PATH", str(database))
    api = client(StubAgent(), unbuilt)

    assert api.get("/api/health").json() == {"ok": True, "database": False, "fake": False}

    database.write_bytes(b"")
    response = api.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"ok": True, "database": True, "fake": False}


def test_health_reports_fake_mode(monkeypatch: pytest.MonkeyPatch, unbuilt: Path) -> None:
    monkeypatch.setenv("NLQ_FAKE_AGENT", "1")
    assert client(StubAgent(), unbuilt).get("/api/health").json()["fake"] is True


def test_the_root_says_the_ui_is_not_built_when_there_is_no_index(unbuilt: Path) -> None:
    api = client(StubAgent(), unbuilt)
    response = api.get("/")
    assert response.status_code == 200
    assert response.json() == UI_NOT_BUILT
    assert api.get("/anything").status_code == 404


def test_a_built_ui_is_served_with_its_assets_and_an_index_fallback(built: Path) -> None:
    api = client(StubAgent(), built)
    index = built.joinpath("index.html").read_text()

    assert api.get("/").text == index
    assert api.get("/some/client/route").text == index
    assert api.get("/assets/app.js").text == "console.log('hi')"
    assert api.get("/brand/nets.svg").text == "<svg/>"
    assert api.get("/assets/missing.js").status_code == 404
    assert api.get("/api/missing").status_code == 404
    assert len(api.get("/api/examples").json()) == 6  # the API still wins over the fallback


def test_a_path_outside_the_static_directory_gets_the_index_not_the_file(
    built: Path, tmp_path: Path
) -> None:
    (tmp_path / "secret.txt").write_text("keep out")
    api = client(StubAgent(), built)
    response = api.get("/%2e%2e/secret.txt")
    assert "keep out" not in response.text


def test_a_path_the_filesystem_cannot_resolve_gets_the_index_not_a_500(built: Path) -> None:
    response = client(StubAgent(), built).get("/%00")
    assert response.status_code == 200
    assert response.text == built.joinpath("index.html").read_text()


def test_the_fake_agent_is_used_when_the_flag_is_set(
    monkeypatch: pytest.MonkeyPatch, unbuilt: Path
) -> None:
    monkeypatch.setenv("NLQ_FAKE_AGENT", "1")
    api = client(None, unbuilt)

    body = api.post("/api/ask", json={"question": "Delete all ticket records"}).json()

    assert body["status"] == "blocked"
    assert body["sql"] == "DELETE FROM tickets"
    assert isinstance(api.app.state.agent, FakeAgent)


def test_the_real_agent_is_built_on_the_first_request_not_at_import(
    monkeypatch: pytest.MonkeyPatch, unbuilt: Path
) -> None:
    built_agents: list[StubAgent] = []

    def from_env(*args: object, **kwargs: object) -> StubAgent:
        built_agents.append(StubAgent())
        return built_agents[-1]

    monkeypatch.setattr(Agent, "from_env", from_env)
    api = client(None, unbuilt)
    assert built_agents == []

    api.post("/api/ask", json={"question": QUESTION})
    api.post("/api/ask", json={"question": QUESTION})

    assert len(built_agents) == 1
    assert built_agents[0].questions == [QUESTION, QUESTION]


def test_the_module_level_app_has_no_agent_until_asked() -> None:
    assert app.state.agent is None
    assert TestClient(app).get("/api/health").status_code == 200
