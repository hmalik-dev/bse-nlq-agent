"""The shipping files: the scripts parse, and the key can never reach the image."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from nlq.api import UI_NOT_BUILT_PAGE
from nlq.config import PROJECT_ROOT

DOCKERIGNORE = PROJECT_ROOT / ".dockerignore"
DOCKERFILE = PROJECT_ROOT / "Dockerfile"
SCRIPTS = (PROJECT_ROOT / "docker" / "entrypoint.sh", PROJECT_ROOT / "scripts" / "smoke.sh")


@pytest.mark.parametrize("script", SCRIPTS, ids=lambda path: path.name)
def test_the_shell_scripts_parse_and_are_executable(script: Path) -> None:
    assert script.stat().st_mode & 0o111, f"{script.name} is not executable"
    subprocess.run(["bash", "-n", str(script)], check=True)


def test_env_files_and_secrets_are_kept_out_of_the_build_context() -> None:
    ignored = DOCKERIGNORE.read_text(encoding="utf-8").splitlines()
    assert ".env*" in ignored
    assert ".venv" in ignored
    assert "data" in ignored
    assert ".git" in ignored


def test_the_container_runs_as_a_user_that_is_not_root() -> None:
    directives = [line.split() for line in DOCKERFILE.read_text(encoding="utf-8").splitlines()]
    users = [words[1] for words in directives if words[:1] == ["USER"]]
    assert users, "the Dockerfile never switches away from root"
    assert users[-1] not in {"root", "0", "0:0"}


def test_every_documented_docker_run_publishes_the_port_on_loopback_only() -> None:
    documents = [PROJECT_ROOT / "README.md", PROJECT_ROOT / "CLAUDE.md"]
    runs = [
        line
        for document in documents
        for line in document.read_text(encoding="utf-8").splitlines()
        if "docker run" in line and " -p " in line
    ]
    assert runs, "no documented docker run command to check"
    assert all(" -p 127.0.0.1:" in line for line in runs), runs
    assert "-p 127.0.0.1:8000:8000" in UI_NOT_BUILT_PAGE


def test_the_dockerfile_never_names_the_key() -> None:
    dockerfile = DOCKERFILE.read_text(encoding="utf-8")
    assert "ANTHROPIC_API_KEY" not in dockerfile
    assert "ENTRYPOINT" in dockerfile and "docker/entrypoint.sh" in dockerfile
