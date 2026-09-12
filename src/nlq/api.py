"""The agent on a URL: four routes and the built interface, served from one address.

`POST /api/ask` always answers 200 with an `AskResult`; only a malformed body
gets an HTTP error. `GET /api/schema` and `GET /api/examples` describe the
data for the drawer and the chips, `GET /api/health` says whether the server,
the database and fake mode are there, and everything else is the web app.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path
from typing import Any, Protocol

import sqlglot
import yaml
from fastapi import APIRouter, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, field_validator
from sqlglot import exp

from nlq import config
from nlq.agent.agent import INTERNAL_MESSAGE, Agent
from nlq.agent.fake import FakeAgent
from nlq.agent.models import AskResult, ErrorInfo, Trace
from nlq.examples import EXAMPLE_QUESTIONS

logger = logging.getLogger("nlq")

API_PREFIX = "/api"
# What `GET /` serves when the interface has not been built: the API is up, and
# these are the three ways forward. Plain HTML with no assets, so it needs nothing.
UI_NOT_BUILT_PAGE = """<!doctype html>
<html lang="en">
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>BSE Insights</title>
<style>pre { white-space: pre-wrap; overflow-wrap: anywhere; }</style>
<main style="max-width: 40rem; margin: 3rem auto; padding: 0 1rem;
             font-family: system-ui, sans-serif; line-height: 1.5">
<h1>BSE Insights is running</h1>
<p>The API is up, but the web interface has not been built, so there is nothing
to show at this address yet. Three ways forward:</p>
<ol>
<li><strong>Build the interface</strong> (needs Node 24), then restart the server:
<pre><code>npm ci &amp;&amp; npm run -w web build</code></pre></li>
<li><strong>Ask from the terminal</strong>, no Node needed:
<pre><code>uv run python -m nlq.ask "How many tickets did we sell last month?"</code></pre></li>
<li><strong>Run the container</strong>, which builds the interface itself:
<pre><code>docker build -t bse-insights .
docker run --env-file .env -p 127.0.0.1:8000:8000 bse-insights</code></pre></li>
</ol>
<p>The API works either way: <a href="/api/health">/api/health</a>,
<a href="/api/examples">/api/examples</a>, <a href="/api/schema">/api/schema</a>
and <code>POST /api/ask</code>.</p>
</main>
"""
SQL_DIALECT = "sqlite"


class AgentLike(Protocol):
    """What the API needs from an agent: `ask`, and nothing else."""

    def ask(self, question: str) -> AskResult: ...


class AskRequest(BaseModel):
    """The one request body: a question, trimmed, non-empty and within the length cap."""

    question: str

    @field_validator("question")
    @classmethod
    def _trimmed_and_bounded(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("question must not be empty")
        limit = config.max_question_chars()
        if len(trimmed) > limit:
            raise ValueError(f"question must be at most {limit} characters")
        return trimmed


router = APIRouter(prefix=API_PREFIX)


@router.post("/ask")
def ask(body: AskRequest, request: Request) -> dict[str, Any]:
    """Answer one question. Every agent outcome is a 200 carrying a status."""
    try:
        result = _agent(request.app).ask(body.question)
    except Exception:
        logger.exception("The agent raised instead of returning a result")
        result = _internal_error(body.question)
    return result.model_dump()


@router.get("/schema")
def schema() -> dict[str, Any]:
    """The tables, their columns and the business definitions, for the drawer."""
    return describe_schema()


@router.get("/examples")
def examples() -> list[dict[str, Any]]:
    """The six starter questions, for the chips."""
    return [example.model_dump() for example in EXAMPLE_QUESTIONS]


@router.get("/health")
def health() -> dict[str, bool]:
    """Is the server up, is the database there, is fake mode on."""
    return {
        "ok": True,
        "database": config.database_path().is_file(),
        "fake": config.fake_agent(),
    }


def create_app(agent: AgentLike | None = None, *, static_dir: Path = config.STATIC_DIR) -> FastAPI:
    """Build the app. With no agent given, one is resolved on the first request."""
    app = FastAPI(title="BSE Insights")
    app.state.agent = agent
    app.include_router(router)
    if (static_dir / "index.html").is_file():
        _serve_ui(app, static_dir)
    else:
        _serve_not_built_page(app)
    return app


def _agent(app: FastAPI) -> AgentLike:
    """The injected agent, else the fake or the real one, built once on first use."""
    if app.state.agent is None:
        app.state.agent = FakeAgent() if config.fake_agent() else Agent.from_env()
    return app.state.agent


def _internal_error(question: str) -> AskResult:
    """What the caller sees when the agent itself raised: the fixed message, no detail."""
    trace = Trace(
        steps=[],
        repairs=0,
        model=config.sql_model(),
        total_ms=0,
        input_tokens=0,
        output_tokens=0,
        cost_usd=0.0,
    )
    error = ErrorInfo(code="internal", message=INTERNAL_MESSAGE)
    return AskResult(status="error", question=question, trace=trace, error=error)


def _serve_not_built_page(app: FastAPI) -> None:
    """With no build present, the root is a plain page saying how to get one."""

    @app.get("/", include_in_schema=False, response_class=HTMLResponse)
    def not_built() -> str:
        return UI_NOT_BUILT_PAGE


def _serve_ui(app: FastAPI, static_dir: Path) -> None:
    """Serve the built interface: its assets, its other files, and index.html for any route."""
    app.mount("/assets", StaticFiles(directory=static_dir / "assets"), name="assets")
    index = static_dir / "index.html"

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str) -> FileResponse:
        if path == "api" or path.startswith("api/"):
            raise HTTPException(status_code=404)
        return FileResponse(_static_file(static_dir, path) or index)


def _static_file(static_dir: Path, path: str) -> Path | None:
    """The file `path` names inside `static_dir`, or None for anything else (or unresolvable)."""
    try:
        candidate = (static_dir / path).resolve()
    except (OSError, ValueError):  # a null byte, or a path the OS refuses to resolve
        return None
    inside = candidate.is_relative_to(static_dir.resolve())
    return candidate if inside and candidate.is_file() else None


@lru_cache(maxsize=1)
def describe_schema() -> dict[str, Any]:
    """Six tables in schema order, each column typed and described, plus the business rules."""
    dictionary = yaml.safe_load(config.DICTIONARY_PATH.read_text(encoding="utf-8"))
    statements = sqlglot.parse(config.SCHEMA_PATH.read_text(encoding="utf-8"), read=SQL_DIALECT)
    tables = [
        _describe_table(statement.this, dictionary["tables"])
        for statement in statements
        if isinstance(statement, exp.Create) and statement.kind == "TABLE"
    ]
    return {
        "tables": tables,
        "definitions": [rule.strip() for rule in dictionary["business_rules"]],
    }


def _describe_table(schema: exp.Schema, described: dict[str, Any]) -> dict[str, Any]:
    name = schema.this.name
    entry = described[name]
    columns = [
        {
            "name": column.name,
            "type": column.args["kind"].sql(dialect=SQL_DIALECT),
            "description": entry["columns"][column.name].strip(),
        }
        for column in schema.expressions
        if isinstance(column, exp.ColumnDef)
    ]
    return {"name": name, "description": entry["description"].strip(), "columns": columns}


app = create_app()
