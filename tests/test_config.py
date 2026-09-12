"""Settings resolve from the environment, with the defaults the docs promise."""

from __future__ import annotations

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


def test_query_bounds_default_and_honour_the_environment(
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
