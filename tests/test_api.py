"""The HTTP contract: 200 with a status for every agent outcome, 422 only for a bad body."""

from __future__ import annotations

import logging
import os
from datetime import date
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

from nlq import config
from nlq.agent.agent import INTERNAL_MESSAGE, Agent
from nlq.agent.answer import AnswerWriter
from nlq.agent.context import build_context
from nlq.agent.executor import Executor
from nlq.agent.fake import FakeAgent
from nlq.agent.llm import SqlWriter
from nlq.agent.models import AskResult, ErrorInfo, SqlPlan, Trace
from nlq.api import app, create_app
from tests.fakes import FakeAnthropic

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
# The drawer's definitions are read at a glance: one line in a 480px panel.
MAX_DEFINITION_CHARS = 90
MAX_DEFINITIONS = 8
QUESTION = "How many tickets did we sell last month?"
LOCAL_URL = "http://127.0.0.1:8000"


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
    monkeypatch.delenv("NLQ_ALLOWED_HOSTS", raising=False)


@pytest.fixture
def unbuilt(tmp_path: Path) -> Path:
    """A static directory that does not exist: what a clone without the web build has."""
    static = tmp_path / "static"
    assert not static.exists()
    return static


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
    return TestClient(create_app(agent, static_dir=static_dir), base_url=LOCAL_URL)


@pytest.mark.parametrize("host", ["localhost:8000", "127.0.0.1:8000", "localhost"])
def test_the_local_host_names_are_served(host: str, unbuilt: Path) -> None:
    response = client(StubAgent(), unbuilt).get("/api/health", headers={"host": host})
    assert response.status_code == 200


def test_a_foreign_host_header_is_refused_before_the_agent_runs(unbuilt: Path) -> None:
    # A DNS-rebinding page reaches 127.0.0.1 under its own name; the Host header gives it away.
    agent = StubAgent()
    response = client(agent, unbuilt).post(
        "/api/ask",
        json={"question": QUESTION},
        headers={"host": "attacker.example", "origin": "http://attacker.example"},
    )
    assert response.status_code == 400
    assert response.text == "Invalid host header"
    assert agent.questions == []


def test_the_allowed_hosts_are_read_from_the_environment(
    monkeypatch: pytest.MonkeyPatch, unbuilt: Path
) -> None:
    monkeypatch.setenv("NLQ_ALLOWED_HOSTS", "insights.example.com")
    api = client(StubAgent(), unbuilt)
    assert api.get("/api/health", headers={"host": "insights.example.com"}).status_code == 200
    assert api.get("/api/health", headers={"host": "localhost"}).status_code == 400


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


def test_a_missing_database_reaches_the_client_without_the_server_path(
    monkeypatch: pytest.MonkeyPatch, unbuilt: Path
) -> None:
    monkeypatch.setenv("NLQ_DATABASE_PATH", "data/absent-for-this-test.db")
    missing = config.database_path()
    assert not missing.exists()
    sql_writer = SqlWriter(FakeAnthropic([SqlPlan(answerable=True, sql="SELECT 1")]))
    agent = Agent(
        sql_writer, Executor(missing), AnswerWriter(FakeAnthropic([])), today=date(2026, 9, 11)
    )

    response = client(agent, unbuilt).post("/api/ask", json={"question": "How many tickets?"})

    assert response.json()["error"] == {
        "code": "database_missing",
        "message": "No database found. Create it with: uv run python -m nlq.db.seed",
    }
    assert str(missing) not in response.text
    assert os.sep + "Users" not in response.text


def test_schema_lists_six_tables_in_order_with_typed_columns_and_definitions(
    unbuilt: Path,
) -> None:
    body = client(StubAgent(), unbuilt).get("/api/schema").json()

    assert [table["name"] for table in body["tables"]] == TABLE_NAMES
    assert set(body) == {"tables", "definitions"}
    assert len(body["definitions"]) >= 3
    assert any(definition["term"] == "Revenue" for definition in body["definitions"])
    tickets = body["tables"][5]
    assert tickets["description"].startswith("One row per seat")
    by_name = {column["name"]: column for column in tickets["columns"]}
    assert by_name["price"] == {
        "name": "price",
        "type": "REAL",
        "references": None,
        "description": "Face value paid, excluding fee. 0 for comps.",
    }
    assert by_name["ticket_id"]["type"] == "INTEGER"
    assert by_name["status"]["type"] == "TEXT"
    assert len(by_name) == 8


def test_schema_names_the_table_a_foreign_key_points_at(unbuilt: Path) -> None:
    tables = client(StubAgent(), unbuilt).get("/api/schema").json()["tables"]
    columns = {
        f"{table['name']}.{column['name']}": column
        for table in tables
        for column in table["columns"]
    }

    assert columns["tickets.event_id"]["type"] == "INTEGER"
    assert columns["tickets.event_id"]["references"] == "events"
    assert columns["events.home_team_id"]["references"] == "teams"
    assert columns["tickets.price"]["references"] is None
    assert columns["tickets.ticket_id"]["references"] is None


def test_schema_definitions_are_one_short_sentence_each_naming_their_term(unbuilt: Path) -> None:
    definitions = client(StubAgent(), unbuilt).get("/api/schema").json()["definitions"]

    assert 3 <= len(definitions) <= MAX_DEFINITIONS
    for definition in definitions:
        assert set(definition) == {"term", "text"}
        sentence = f"{definition['term']} {definition['text']}"
        assert len(sentence) <= MAX_DEFINITION_CHARS, sentence
        assert sentence.endswith(".")
        assert ". " not in sentence, sentence
        assert definition["term"][0].isupper()


def test_schema_definitions_are_separate_from_the_rules_the_sql_writer_reads(
    unbuilt: Path,
) -> None:
    definitions = client(StubAgent(), unbuilt).get("/api/schema").json()["definitions"]
    dictionary = yaml.safe_load(config.DICTIONARY_PATH.read_text(encoding="utf-8"))
    prompt = build_context(date(2026, 9, 12)).system

    assert all(rule.strip() in prompt for rule in dictionary["business_rules"])
    assert len(dictionary["business_rules"]) > len(definitions)
    for definition in definitions:
        assert definition["text"] not in prompt


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


def test_the_root_is_a_page_naming_the_three_ways_forward_when_there_is_no_build(
    unbuilt: Path,
) -> None:
    api = client(StubAgent(), unbuilt)
    response = api.get("/")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "npm ci &amp;&amp; npm run -w web build" in response.text
    assert 'uv run python -m nlq.ask "How many tickets did we sell last month?"' in response.text
    assert "docker run --env-file .env -p 127.0.0.1:8000:8000 bse-insights" in response.text
    assert "pre { white-space: pre-wrap" in response.text  # commands wrap at phone width
    assert api.get("/anything").status_code == 404


def test_the_api_routes_answer_the_same_with_and_without_a_build(
    tmp_path: Path, built: Path
) -> None:
    canned = result("answered", answer="Five.", columns=["n"], rows=[[5]], row_count=1)
    without = client(StubAgent(canned), tmp_path / "missing")
    with_build = client(StubAgent(canned), built)
    for path in ("/api/examples", "/api/schema", "/api/health"):
        assert without.get(path).json() == with_build.get(path).json(), path
    body = {"question": QUESTION}
    asked = [api.post("/api/ask", json=body).json() for api in (without, with_build)]
    assert asked[0] == asked[1] == canned.model_dump()
    assert without.get("/").text != with_build.get("/").text


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


@pytest.fixture
def secret(tmp_path: Path) -> Path:
    """A file beside the static directory, one `..` away from being served."""
    path = tmp_path / "secret.txt"
    path.write_text("keep out")
    return path


@pytest.mark.parametrize(
    "url",
    [
        "/%2e%2e/secret.txt",
        "/%2e%2e%2fsecret.txt",
        "/..%2fsecret.txt",
        "/brand/%2e%2e/%2e%2e/secret.txt",
        "/assets/%2e%2e/%2e%2e/secret.txt",
    ],
)
def test_a_path_that_climbs_out_of_the_static_directory_is_a_404(
    built: Path, secret: Path, url: str
) -> None:
    response = client(StubAgent(), built).get(url)
    assert response.status_code == 404
    assert "keep out" not in response.text


def test_an_absolute_path_is_a_404_not_the_file_it_names(built: Path, secret: Path) -> None:
    # `//tmp/...` would be read as a host by the client, so the leading slash goes in encoded.
    response = client(StubAgent(), built).get("/%2F" + str(secret).lstrip("/"))
    assert response.status_code == 404
    assert "keep out" not in response.text


def test_a_symlink_pointing_out_of_the_static_directory_is_a_404(built: Path, secret: Path) -> None:
    (built / "brand" / "leak.txt").symlink_to(secret)
    response = client(StubAgent(), built).get("/brand/leak.txt")
    assert response.status_code == 404
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
    assert TestClient(app, base_url=LOCAL_URL).get("/api/health").status_code == 200
