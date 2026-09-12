"""Filesystem paths and environment-driven settings.

Secrets are only ever read from the environment, never hardcoded. The project
root `.env` is read into the environment at import so `uv run uvicorn` and the
CLI pick the key up from it; a variable already set in the environment wins.
"""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path

import dotenv

PACKAGE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_DIR.parents[1]

SCHEMA_PATH = PACKAGE_DIR / "db" / "schema.sql"
DICTIONARY_PATH = PACKAGE_DIR / "db" / "dictionary.yaml"

DEFAULT_DATABASE_PATH = "data/tickets.db"
DEFAULT_QUERY_TIMEOUT_MS = 5000
DEFAULT_MAX_ROWS = 500
DEFAULT_MODEL = "claude-sonnet-5"
DEFAULT_LLM_TIMEOUT_S = 60


def load_project_env() -> None:
    """Read `.env` from the project root without overriding what is already set."""
    dotenv.load_dotenv(PROJECT_ROOT / ".env", override=False)


load_project_env()


def database_path() -> Path:
    """Where the generated database lives.

    NLQ_DATABASE_PATH may be absolute or relative to the project root, so the
    evaluation and the container can each point at their own file.
    """
    configured = os.environ.get("NLQ_DATABASE_PATH", "").strip()
    return PROJECT_ROOT / (configured or DEFAULT_DATABASE_PATH)


def _int_env(name: str, default: int) -> int:
    """An integer setting from the environment, falling back when unset or blank."""
    raw = os.environ.get(name, "").strip()
    return int(raw) if raw else default


def _str_env(name: str, default: str) -> str:
    """A text setting from the environment, falling back when unset or blank."""
    return os.environ.get(name, "").strip() or default


def query_timeout_ms() -> int:
    """How long a single query may run before it is interrupted."""
    return _int_env("NLQ_QUERY_TIMEOUT_MS", DEFAULT_QUERY_TIMEOUT_MS)


def max_rows() -> int:
    """The most rows one query may return to the answer writer and the UI."""
    return _int_env("NLQ_MAX_ROWS", DEFAULT_MAX_ROWS)


def sql_model() -> str:
    """The model that turns a question into SQL."""
    return _str_env("NLQ_SQL_MODEL", DEFAULT_MODEL)


def answer_model() -> str:
    """The model that turns query results into a written answer."""
    return _str_env("NLQ_ANSWER_MODEL", DEFAULT_MODEL)


def llm_timeout_s() -> int:
    """How long one model call may take before it is abandoned."""
    return _int_env("NLQ_LLM_TIMEOUT_S", DEFAULT_LLM_TIMEOUT_S)


def anthropic_api_key() -> str:
    """The API key, or an empty string when none is set. Never logged or stored."""
    return os.environ.get("ANTHROPIC_API_KEY", "").strip()


DATABASE_PATH = database_path()


def today() -> date:
    """The date the agent treats as "now" when resolving relative wording.

    NLQ_TODAY pins it so evaluation runs are reproducible; unset means the real
    current date.
    """
    pinned = os.environ.get("NLQ_TODAY", "").strip()
    if not pinned:
        return date.today()
    return date.fromisoformat(pinned)
