"""The shipping files: the scripts parse, and the key can never reach the image."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from nlq.api import UI_NOT_BUILT_PAGE
from nlq.config import PROJECT_ROOT

DOCKERIGNORE = PROJECT_ROOT / ".dockerignore"
DOCKERFILE = PROJECT_ROOT / "Dockerfile"
SCRIPTS = (
    PROJECT_ROOT / "docker" / "entrypoint.sh",
    PROJECT_ROOT / "scripts" / "smoke.sh",
    PROJECT_ROOT / "scripts" / "dev.sh",
)


@pytest.mark.parametrize("script", SCRIPTS, ids=lambda path: path.name)
def test_the_shell_scripts_parse_and_are_executable(script: Path) -> None:
    assert script.stat().st_mode & 0o111, f"{script.name} is not executable"
    subprocess.run(["bash", "-n", str(script)], check=True)


def test_npm_run_dev_and_npm_start_both_run_the_dev_script() -> None:
    package = json.loads((PROJECT_ROOT / "package.json").read_text(encoding="utf-8"))
    assert package["scripts"] == {"dev": "scripts/dev.sh", "start": "scripts/dev.sh"}


def test_env_files_and_secrets_are_kept_out_of_the_build_context() -> None:
    ignored = DOCKERIGNORE.read_text(encoding="utf-8").splitlines()
    assert ".env*" in ignored
    assert ".venv" in ignored
    assert "data" in ignored
    assert ".git" in ignored


def test_the_container_runs_as_a_user_that_is_not_root() -> None:
    directives = [line.split() for line in DOCKERFILE.read_text(encoding="utf-8").splitlines()]
    users = [words[1] for words in directives if words and words[0] == "USER"]
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


def test_the_entrypoint_explains_an_unwritable_data_directory_instead_of_seeding(
    tmp_path: Path,
) -> None:
    data = tmp_path / "data"
    data.mkdir()
    data.chmod(0o555)
    env = {"PATH": "/usr/bin:/bin", "NLQ_DATABASE_PATH": str(data / "tickets.db")}
    try:
        run = subprocess.run(
            ["bash", str(SCRIPTS[0])], env=env, capture_output=True, text=True, timeout=10
        )
    finally:
        data.chmod(0o755)
    assert run.returncode == 1
    assert f"Cannot write {data}" in run.stderr
    assert "docker volume rm bse-data" in run.stderr
    assert "Seeding" not in run.stdout


def test_the_dockerfile_never_names_the_key() -> None:
    dockerfile = DOCKERFILE.read_text(encoding="utf-8")
    assert "ANTHROPIC_API_KEY" not in dockerfile
    assert "ENTRYPOINT" in dockerfile and "docker/entrypoint.sh" in dockerfile
