"""The shipping files: the scripts parse, and the key can never reach the image."""

from __future__ import annotations

import contextlib
import json
import os
import shutil
import signal
import socket
import subprocess
import threading
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
DEV_API_PORT = 8000


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
    assert "**/.env*" in ignored  # web/.env.local would otherwise be built into the bundle
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


def _stub(bin_dir: Path, name: str, body: str) -> None:
    """A fake command on PATH that logs its arguments, then runs `body`."""
    path = bin_dir / name
    path.write_text(f'#!/bin/sh\necho "{name} $*" >> "$STUB_LOG"\n{body}\n', encoding="utf-8")
    path.chmod(0o755)


@pytest.fixture
def stubs(tmp_path: Path) -> dict[str, str]:
    """PATH and variables for running a shipped script against fake uv, npm, curl and python."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    ready = tmp_path / "ui-ready"
    os.mkfifo(ready)
    _stub(bin_dir, "uv", UV_STUB)
    _stub(bin_dir, "npm", f'case "$*" in *"web dev"*) echo up > "{ready}"; exec sleep 60;; esac')
    _stub(bin_dir, "node", "echo v24.0.0")
    _stub(bin_dir, "curl", """echo '{"ok":true,"database":true}'""")
    _stub(bin_dir, "python", "")
    _stub(bin_dir, "uvicorn", "")
    bash_dir = str(Path(shutil.which("bash") or "/bin/bash").parent)
    return {
        "PATH": f"{bin_dir}:{bash_dir}:/usr/bin:/bin",
        "HOME": str(tmp_path),
        "STUB_LOG": str(tmp_path / "calls.log"),
        "STUB_DB": str(tmp_path / "tickets.db"),
        "STUB_PID": str(tmp_path / "api.pid"),
        "STUB_READY": str(ready),
        "NLQ_DATABASE_PATH": str(tmp_path / "tickets.db"),
    }


UV_STUB = """case "$*" in
  "run python -c"*) echo "$STUB_DB";;
  "run uvicorn"*) echo $$ > "$STUB_PID"; exec sleep 60;;
esac"""


def _calls(stubs: dict[str, str]) -> str:
    log = Path(stubs["STUB_LOG"])
    return log.read_text(encoding="utf-8") if log.exists() else ""


def _run_dev_with_the_api_port_taken(
    stubs: dict[str, str], script: Path = SCRIPTS[2]
) -> subprocess.CompletedProcess[str]:
    with socket.socket() as holder:
        with contextlib.suppress(OSError):  # already taken by something else: the same case
            holder.bind(("127.0.0.1", DEV_API_PORT))
            holder.listen()
        return subprocess.run(
            ["bash", str(script)], env=stubs, capture_output=True, text=True, timeout=30
        )


def test_npm_run_dev_seeds_a_fifth_of_the_data_when_there_is_no_database(
    stubs: dict[str, str],
) -> None:
    _run_dev_with_the_api_port_taken(stubs)
    assert "uv run python -m nlq.db.seed --scale 0.2" in _calls(stubs)


def test_npm_run_dev_reuses_an_existing_database(stubs: dict[str, str]) -> None:
    Path(stubs["STUB_DB"]).write_bytes(b"")
    run = _run_dev_with_the_api_port_taken(stubs)
    assert "nlq.db.seed" not in _calls(stubs)
    assert f"using the existing database at {stubs['STUB_DB']}" in run.stdout


def _bin_dir(stubs: dict[str, str]) -> Path:
    return Path(stubs["PATH"].split(":")[0])


def _run_dev_with_only_the_stubs_on_path(stubs: dict[str, str]) -> subprocess.CompletedProcess[str]:
    """PATH holds the stub directory and `dirname`, so no real uv or Node can answer."""
    bin_dir = _bin_dir(stubs)
    (bin_dir / "dirname").symlink_to(shutil.which("dirname") or "/usr/bin/dirname")
    return subprocess.run(
        [shutil.which("bash") or "/bin/bash", str(SCRIPTS[2])],
        env={**stubs, "PATH": str(bin_dir)},
        capture_output=True,
        text=True,
        timeout=30,
    )


@pytest.mark.parametrize(
    ("tool", "hint"),
    [
        ("uv", "uv is not installed: curl -LsSf https://astral.sh/uv/install.sh | sh"),
        ("node", "node is not installed: install Node 24 from https://nodejs.org/en/download"),
        ("npm", "npm is not installed: it ships with Node: https://nodejs.org/en/download"),
    ],
)
def test_npm_run_dev_names_a_missing_tool_and_starts_nothing(
    stubs: dict[str, str], tool: str, hint: str
) -> None:
    (_bin_dir(stubs) / tool).unlink()
    run = _run_dev_with_only_the_stubs_on_path(stubs)
    assert run.returncode == 1
    assert run.stderr.strip() == hint
    assert run.stdout == ""
    assert "uv " not in _calls(stubs)
    assert "npm " not in _calls(stubs)


def test_npm_run_dev_refuses_a_node_older_than_24(stubs: dict[str, str]) -> None:
    _stub(_bin_dir(stubs), "node", "echo v20.11.1")
    run = _run_dev_with_only_the_stubs_on_path(stubs)
    assert run.returncode == 1
    assert run.stderr.strip() == (
        "Node 24 or newer is required; found v20.11.1: https://nodejs.org/en/download"
    )
    assert "uv " not in _calls(stubs)


NO_KEY_LINE = "ANTHROPIC_API_KEY is not set: using the fake agent (canned answers)."
ENV_HINT = " Create .env with the ANTHROPIC_API_KEY= line you were sent."


@pytest.mark.parametrize(
    ("env_file", "expected"),
    [(None, NO_KEY_LINE + ENV_HINT), ("NLQ_SQL_MODEL=claude-sonnet-5\n", NO_KEY_LINE)],
    ids=["no-env-file", "env-file-without-a-key"],
)
def test_npm_run_dev_without_a_key_says_where_the_key_goes_only_when_env_is_missing(
    stubs: dict[str, str], tmp_path: Path, env_file: str | None, expected: str
) -> None:
    repo = tmp_path / "clone"
    (repo / "scripts").mkdir(parents=True)
    script = repo / "scripts" / "dev.sh"
    shutil.copy(SCRIPTS[2], script)
    if env_file is not None:
        (repo / ".env").write_text(env_file, encoding="utf-8")
    run = _run_dev_with_the_api_port_taken(stubs, script)
    assert expected in run.stdout.splitlines()


def test_npm_run_dev_exits_non_zero_naming_a_taken_api_port(stubs: dict[str, str]) -> None:
    run = _run_dev_with_the_api_port_taken(stubs)
    assert run.returncode == 1
    assert f"port {DEV_API_PORT} is already in use" in run.stderr
    assert "uvicorn" not in _calls(stubs)


def test_ctrl_c_on_npm_run_dev_stops_the_api_too(stubs: dict[str, str]) -> None:
    # Needs port 8000 free, as `npm run dev` itself does: say so at once rather than time out.
    with socket.socket() as probe:
        assert probe.connect_ex(("127.0.0.1", DEV_API_PORT)) != 0, (
            f"port {DEV_API_PORT} is in use; stop `npm run dev` or the container first"
        )
    Path(stubs["STUB_DB"]).write_bytes(b"")
    dev = subprocess.Popen(
        ["bash", str(SCRIPTS[2])],
        env=stubs,
        start_new_session=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        reader = threading.Thread(target=lambda: Path(stubs["STUB_READY"]).read_text())
        reader.start()
        reader.join(timeout=30)
        assert not reader.is_alive(), "the UI never started"
        api_pid = int(Path(stubs["STUB_PID"]).read_text(encoding="utf-8"))
        os.killpg(dev.pid, signal.SIGINT)  # what Ctrl+C sends to the terminal's process group
        dev.wait(timeout=30)
        with pytest.raises(ProcessLookupError):
            os.kill(api_pid, 0)
    finally:
        with contextlib.suppress(ProcessLookupError):
            os.killpg(dev.pid, signal.SIGKILL)
        with contextlib.suppress(OSError):  # unblock the reader if the UI never started
            fd = os.open(stubs["STUB_READY"], os.O_WRONLY | os.O_NONBLOCK)
            os.close(fd)


def test_the_container_seeds_the_full_dataset_on_first_start(stubs: dict[str, str]) -> None:
    run = subprocess.run(
        ["bash", str(SCRIPTS[0])], env=stubs, capture_output=True, text=True, timeout=10
    )
    assert run.returncode == 0
    assert "Seeding the database" in run.stdout
    assert "python -m nlq.db.seed\nuvicorn nlq.api:app --host 0.0.0.0 --port 8000" in _calls(stubs)


def test_the_container_reuses_its_database_on_a_later_start(stubs: dict[str, str]) -> None:
    Path(stubs["STUB_DB"]).write_bytes(b"")
    run = subprocess.run(
        ["bash", str(SCRIPTS[0])], env=stubs, capture_output=True, text=True, timeout=10
    )
    assert "Using the existing database" in run.stdout
    assert _calls(stubs) == "uvicorn nlq.api:app --host 0.0.0.0 --port 8000\n"


def test_the_dockerfile_never_names_the_key() -> None:
    dockerfile = DOCKERFILE.read_text(encoding="utf-8")
    assert "ANTHROPIC_API_KEY" not in dockerfile
    assert "ENTRYPOINT" in dockerfile and "docker/entrypoint.sh" in dockerfile
