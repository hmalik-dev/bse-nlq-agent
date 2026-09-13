"""Settings resolve from the environment, with the defaults the docs promise."""

from __future__ import annotations

import importlib
import os
from pathlib import Path

import dotenv
import pytest

from nlq import config


def test_database_path_defaults_to_data_tickets_db(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("NLQ_DATABASE_PATH", raising=False)
    assert config.database_path() == config.PROJECT_ROOT / "data" / "tickets.db"


def test_database_path_resolves_a_relative_setting_against_the_project_root(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("NLQ_DATABASE_PATH", "build/eval.db")
    assert config.database_path() == config.PROJECT_ROOT / "build" / "eval.db"


def test_database_path_takes_an_absolute_setting_as_given(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    absolute = tmp_path / "container" / "tickets.db"
    monkeypatch.setenv("NLQ_DATABASE_PATH", str(absolute))
    assert config.database_path() == absolute


def test_allowed_hosts_default_to_local_and_honor_the_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("NLQ_ALLOWED_HOSTS", raising=False)
    assert config.allowed_hosts() == ["localhost", "127.0.0.1"]

    monkeypatch.setenv("NLQ_ALLOWED_HOSTS", " insights.example.com, ,localhost ")
    assert config.allowed_hosts() == ["insights.example.com", "localhost"]


def test_query_bounds_default_and_honor_the_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("NLQ_QUERY_TIMEOUT_MS", raising=False)
    monkeypatch.delenv("NLQ_MAX_ROWS", raising=False)
    assert config.query_timeout_ms() == 5000
    assert config.max_rows() == 500

    monkeypatch.setenv("NLQ_QUERY_TIMEOUT_MS", "250")
    monkeypatch.setenv("NLQ_MAX_ROWS", "10")
    assert config.query_timeout_ms() == 250
    assert config.max_rows() == 10


def test_model_settings_default_and_honor_the_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for name in ("NLQ_SQL_MODEL", "NLQ_ANSWER_MODEL", "NLQ_LLM_TIMEOUT_S"):
        monkeypatch.delenv(name, raising=False)
    assert config.sql_model() == "claude-sonnet-5"
    assert config.answer_model() == "claude-sonnet-5"
    assert config.llm_timeout_s() == 60

    monkeypatch.setenv("NLQ_SQL_MODEL", "claude-haiku-4-5")
    monkeypatch.setenv("NLQ_ANSWER_MODEL", "claude-opus-5")
    monkeypatch.setenv("NLQ_LLM_TIMEOUT_S", "15")
    assert config.sql_model() == "claude-haiku-4-5"
    assert config.answer_model() == "claude-opus-5"
    assert config.llm_timeout_s() == 15


def test_the_api_key_is_read_from_the_environment_only(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert config.anthropic_api_key() == ""
    monkeypatch.setenv("ANTHROPIC_API_KEY", " sk-test ")
    assert config.anthropic_api_key() == "sk-test"


def test_the_project_env_file_fills_gaps_without_overriding_the_environment(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    (tmp_path / ".env").write_text(
        "NLQ_SQL_MODEL=from-file\nNLQ_LLM_TIMEOUT_S=7\n", encoding="utf-8"
    )
    monkeypatch.setenv("NLQ_SQL_MODEL", "already-set")
    monkeypatch.delenv("NLQ_LLM_TIMEOUT_S", raising=False)
    monkeypatch.setattr(config, "PROJECT_ROOT", tmp_path)

    # The file writes straight into os.environ, which monkeypatch cannot undo
    # for a variable that was absent, so the value is removed by hand.
    try:
        config.load_project_env()
        assert config.sql_model() == "already-set"
        assert config.llm_timeout_s() == 7
    finally:
        os.environ.pop("NLQ_LLM_TIMEOUT_S", None)


def test_the_env_file_is_loaded_at_import(monkeypatch: pytest.MonkeyPatch) -> None:
    loaded: list[tuple[Path, bool]] = []
    monkeypatch.setattr(
        dotenv, "load_dotenv", lambda path, override: loaded.append((path, override)) or True
    )

    importlib.reload(config)

    assert loaded == [(config.PROJECT_ROOT / ".env", False)]
