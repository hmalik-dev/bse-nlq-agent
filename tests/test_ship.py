"""The shipping files: the scripts parse, and the key can never reach the image."""

from __future__ import annotations

import contextlib
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import threading
from collections.abc import Callable
from pathlib import Path

import pytest

from nlq.api import UI_NOT_BUILT_PAGE
from nlq.config import PROJECT_ROOT

DOCKERIGNORE = PROJECT_ROOT / ".dockerignore"
DOCKERFILE = PROJECT_ROOT / "Dockerfile"
ENTRYPOINT = PROJECT_ROOT / "docker" / "entrypoint.sh"
SMOKE = PROJECT_ROOT / "scripts" / "smoke.sh"
DEV = PROJECT_ROOT / "scripts" / "dev.mjs"
NODE = shutil.which("node") or "node"
DEV_API_PORT = 8000
KEY_VAR = "ANTHROPIC_API_KEY"

POSIX_ONLY = pytest.mark.skipif(
    sys.platform == "win32",
    reason="runs POSIX shell scripts or signals a process group; Windows shutdown is"
    " covered by test_stop_tree_kills_the_whole_tree_with_taskkill_on_windows",
)


@POSIX_ONLY
@pytest.mark.parametrize("script", (ENTRYPOINT, SMOKE), ids=lambda path: path.name)
def test_the_shell_scripts_parse_and_are_executable(script: Path) -> None:
    assert script.stat().st_mode & 0o111, f"{script.name} is not executable"
    subprocess.run(["bash", "-n", str(script)], check=True)


def test_npm_run_dev_and_npm_start_both_run_the_node_launcher() -> None:
    package = json.loads((PROJECT_ROOT / "package.json").read_text(encoding="utf-8"))
    assert package["scripts"] == {"dev": "node scripts/dev.mjs", "start": "node scripts/dev.mjs"}


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
    claude_md = (PROJECT_ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    runs = [line for line in claude_md.splitlines() if "docker run" in line and " -p " in line]
    assert runs, "no documented docker run command to check"
    assert all(" -p 127.0.0.1:" in line for line in runs), runs
    assert "-p 127.0.0.1:8000:8000" in UI_NOT_BUILT_PAGE


@POSIX_ONLY
def test_the_entrypoint_explains_an_unwritable_data_directory_instead_of_seeding(
    tmp_path: Path,
) -> None:
    data = tmp_path / "data"
    data.mkdir()
    data.chmod(0o555)
    env = {"PATH": "/usr/bin:/bin", "NLQ_DATABASE_PATH": str(data / "tickets.db")}
    try:
        run = subprocess.run(
            ["bash", str(ENTRYPOINT)], env=env, capture_output=True, text=True, timeout=10
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
    """PATH and variables for running a shipped script against fake uv, npm and python."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _stub(bin_dir, "uv", UV_STUB)
    _stub(bin_dir, "npm", 'case "$*" in *"web dev"*) echo up > "$STUB_READY"; exec sleep 60;; esac')
    _stub(bin_dir, "python", "")
    _stub(bin_dir, "uvicorn", "")
    tool_dirs = [str(Path(shutil.which(tool) or "/bin/sh").parent) for tool in (NODE, "bash")]
    env = {
        "PATH": os.pathsep.join([str(bin_dir), *tool_dirs, "/usr/bin", "/bin"]),
        "HOME": str(tmp_path),
        "STUB_LOG": str(tmp_path / "calls.log"),
        "STUB_DB": str(tmp_path / "tickets.db"),
        "STUB_PID": str(tmp_path / "api.pid"),
        "STUB_READY": str(tmp_path / "ui-ready"),
        "NLQ_DATABASE_PATH": str(tmp_path / "tickets.db"),
        KEY_VAR: "a-key-for-the-script-checks",
    }
    if "SYSTEMROOT" in os.environ:  # Node on Windows cannot start without it
        env["SYSTEMROOT"] = os.environ["SYSTEMROOT"]
    return env


UV_STUB = """case "$*" in
  "run python -c"*) echo "$STUB_DB";;
  "run uvicorn"*) echo $$ > "$STUB_PID"; exec "$STUB_API";;
esac"""


def _calls(stubs: dict[str, str]) -> str:
    log = Path(stubs["STUB_LOG"])
    return log.read_text(encoding="utf-8") if log.exists() else ""


def _run_dev_with_the_api_port_taken(
    stubs: dict[str, str], launcher: Path = DEV
) -> subprocess.CompletedProcess[str]:
    with socket.socket() as holder:
        with contextlib.suppress(OSError):  # already taken by something else: the same case
            holder.bind(("127.0.0.1", DEV_API_PORT))
            holder.listen()
        return subprocess.run(
            [NODE, str(launcher)], env=stubs, capture_output=True, text=True, timeout=30
        )


@POSIX_ONLY
def test_npm_run_dev_seeds_a_fifth_of_the_data_when_there_is_no_database(
    stubs: dict[str, str],
) -> None:
    _run_dev_with_the_api_port_taken(stubs)
    assert "uv run python -m nlq.db.seed --scale 0.2" in _calls(stubs)


@POSIX_ONLY
def test_npm_run_dev_reuses_an_existing_database(stubs: dict[str, str]) -> None:
    Path(stubs["STUB_DB"]).write_bytes(b"")
    run = _run_dev_with_the_api_port_taken(stubs)
    assert "nlq.db.seed" not in _calls(stubs)
    assert f"using the existing database at {stubs['STUB_DB']}" in run.stdout


def _bin_dir(stubs: dict[str, str]) -> Path:
    return Path(stubs["PATH"].split(os.pathsep)[0])


@POSIX_ONLY
@pytest.mark.parametrize(
    ("tool", "hint"),
    [
        ("uv", "uv is not installed: curl -LsSf https://astral.sh/uv/install.sh | sh"),
        ("npm", "npm is not installed: it ships with Node: https://nodejs.org/en/download"),
    ],
)
def test_npm_run_dev_names_a_missing_tool_and_starts_nothing(
    stubs: dict[str, str], tool: str, hint: str
) -> None:
    (_bin_dir(stubs) / tool).unlink()
    run = subprocess.run(
        [NODE, str(DEV)],
        env={**stubs, "PATH": str(_bin_dir(stubs))},  # no real uv or npm can answer
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert run.returncode == 1
    assert run.stderr.strip() == hint
    assert run.stdout == ""
    assert "uv " not in _calls(stubs)
    assert "npm " not in _calls(stubs)


def _dev_module(expression: str) -> object:
    """The JSON value of `expression`, evaluated with the launcher's exports imported."""
    code = f"import * as dev from {json.dumps(DEV.as_uri())};"
    code += f"process.stdout.write(JSON.stringify({expression}));"
    run = subprocess.run(
        [NODE, "--input-type=module", "-e", code],
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )
    return json.loads(run.stdout)


def test_npm_run_dev_refuses_a_node_older_than_24() -> None:
    assert _dev_module("dev.nodeVersionProblem('v20.11.1')") == (
        "Node 24 or newer is required; found v20.11.1: https://nodejs.org/en/download"
    )
    assert _dev_module("dev.nodeVersionProblem('v24.0.0')") is None


def test_a_missing_uv_is_named_with_the_installer_for_that_platform() -> None:
    assert _dev_module("dev.uvInstallHint('win32')") == (
        'powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"'
    )
    assert _dev_module("dev.uvInstallHint('darwin')") == (
        "curl -LsSf https://astral.sh/uv/install.sh | sh"
    )


def test_stop_tree_kills_the_whole_tree_with_taskkill_on_windows() -> None:
    calls = _dev_module(
        """(() => {
          const calls = [];
          const options = { platform: 'win32', runSync: (...call) => calls.push(call.slice(0, 2)) };
          dev.stopTree({ pid: 4321, exitCode: null, signalCode: null }, options);
          dev.stopTree({ pid: 4322, exitCode: 0, signalCode: null }, options);
          return calls;
        })()"""
    )
    assert calls == [["taskkill", ["/PID", "4321", "/T", "/F"]]]


NO_KEY_LINE = (
    f"{KEY_VAR} is not set. Create .env with the {KEY_VAR}= line you were sent,"
    " then run npm run dev again."
)


def _clone_with(tmp_path: Path, launcher: Path, env_file: str | None) -> Path:
    """A copy of `launcher` and the key check it runs, in a clone with the given .env."""
    repo = tmp_path / "clone"
    (repo / "scripts").mkdir(parents=True)
    for source in {launcher, DEV}:
        shutil.copy(source, repo / "scripts" / source.name)
    if env_file is not None:
        (repo / ".env").write_text(env_file, encoding="utf-8")
    return repo / "scripts" / launcher.name


@pytest.mark.parametrize(
    "launcher",
    [DEV, pytest.param(SMOKE, marks=POSIX_ONLY)],
    ids=lambda path: path.name,
)
@pytest.mark.parametrize(
    ("shell_key", "env_file"),
    [
        (None, None),
        (None, "NLQ_SQL_MODEL=claude-sonnet-5\n"),
        ("  ", f"{KEY_VAR}=\n"),
        (None, f'{KEY_VAR}=""\n'),
        ("", f"{KEY_VAR}=from-the-file\n"),  # the app never lets .env override the shell
        (" ", f"{KEY_VAR}=from-the-file\n"),
    ],
    ids=[
        "no-env-file",
        "env-file-without-a-key",
        "blank-key",
        "quoted-blank",
        "empty-shell-wins",
        "blank-shell-wins",
    ],
)
def test_a_launcher_without_a_key_names_it_and_installs_nothing(
    stubs: dict[str, str],
    tmp_path: Path,
    launcher: Path,
    shell_key: str | None,
    env_file: str | None,
) -> None:
    env = {name: value for name, value in stubs.items() if name != KEY_VAR}
    if shell_key is not None:
        env[KEY_VAR] = shell_key
    clone = _clone_with(tmp_path, launcher, env_file)
    command = [NODE if launcher.suffix == ".mjs" else "bash", str(clone)]
    run = subprocess.run(command, env=env, capture_output=True, text=True, timeout=30)
    assert run.returncode == 1
    assert run.stderr.strip() == NO_KEY_LINE
    assert "uv " not in _calls(stubs)
    assert "npm " not in _calls(stubs)


@POSIX_ONLY
@pytest.mark.parametrize(
    "line", ["{}=from-the-file", "export {}='from-the-file'", "  {}=from-the-file"]
)
def test_npm_run_dev_finds_a_key_that_is_only_in_env(
    stubs: dict[str, str], tmp_path: Path, line: str
) -> None:
    env = {name: value for name, value in stubs.items() if name != KEY_VAR}
    clone = _clone_with(tmp_path, DEV, line.format(KEY_VAR) + "\n")
    run = _run_dev_with_the_api_port_taken(env, clone)
    assert NO_KEY_LINE not in run.stderr
    assert "uv sync" in _calls(stubs)


@POSIX_ONLY
def test_npm_run_dev_exits_non_zero_naming_a_taken_api_port(stubs: dict[str, str]) -> None:
    run = _run_dev_with_the_api_port_taken(stubs)
    assert run.returncode == 1
    assert run.stderr.strip() == f"FAIL: port {DEV_API_PORT} is already in use (lsof -i :8000)."
    assert "uvicorn" not in _calls(stubs)


HEALTHY_API = """import http.server

class Health(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        body = b'{"ok":true,"database":true}'
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass

http.server.HTTPServer(("127.0.0.1", 8000), Health).serve_forever()
"""


def _healthy_api(tmp_path: Path) -> Path:
    """A command standing in for uvicorn: answers /api/health on :8000 until interrupted."""
    server = tmp_path / "health.py"
    server.write_text(HEALTHY_API, encoding="utf-8")
    command = tmp_path / "api"
    command.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{server}"\n', encoding="utf-8")
    command.chmod(0o755)
    return command


def _ctrl_c(pid: int) -> None:
    os.killpg(pid, signal.SIGINT)  # what Ctrl+C sends to the terminal's process group


def _kill(pid: int) -> None:
    os.kill(pid, signal.SIGTERM)  # a plain `kill` or an editor's stop button, launcher only


def _close_terminal(pid: int) -> None:
    os.kill(pid, signal.SIGHUP)


@POSIX_ONLY
@pytest.mark.parametrize("stop", [_ctrl_c, _kill, _close_terminal], ids=lambda stop: stop.__name__)
def test_stopping_npm_run_dev_stops_the_api_too(
    stubs: dict[str, str], tmp_path: Path, stop: Callable[[int], None]
) -> None:
    # Needs port 8000 free, as `npm run dev` itself does: say so at once rather than time out.
    with socket.socket() as probe:
        assert probe.connect_ex(("127.0.0.1", DEV_API_PORT)) != 0, (
            f"port {DEV_API_PORT} is in use; stop `npm run dev` or the container first"
        )
    Path(stubs["STUB_DB"]).write_bytes(b"")
    os.mkfifo(stubs["STUB_READY"])
    dev = subprocess.Popen(
        [NODE, str(DEV)],
        env={**stubs, "STUB_API": str(_healthy_api(tmp_path))},
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
        stop(dev.pid)
        dev.wait(timeout=30)
        with pytest.raises(ProcessLookupError):
            os.kill(api_pid, 0)
        with socket.socket() as probe:
            assert probe.connect_ex(("127.0.0.1", DEV_API_PORT)) != 0
    finally:
        with contextlib.suppress(ProcessLookupError):
            os.killpg(dev.pid, signal.SIGKILL)
        with contextlib.suppress(OSError):  # unblock the reader if the UI never started
            fd = os.open(stubs["STUB_READY"], os.O_WRONLY | os.O_NONBLOCK)
            os.close(fd)


@POSIX_ONLY
def test_the_container_seeds_the_full_dataset_on_first_start(stubs: dict[str, str]) -> None:
    run = subprocess.run(
        ["bash", str(ENTRYPOINT)], env=stubs, capture_output=True, text=True, timeout=10
    )
    assert run.returncode == 0
    assert "Seeding the database" in run.stdout
    assert "python -m nlq.db.seed\nuvicorn nlq.api:app --host 0.0.0.0 --port 8000" in _calls(stubs)


@POSIX_ONLY
def test_the_container_reuses_its_database_on_a_later_start(stubs: dict[str, str]) -> None:
    Path(stubs["STUB_DB"]).write_bytes(b"")
    run = subprocess.run(
        ["bash", str(ENTRYPOINT)], env=stubs, capture_output=True, text=True, timeout=10
    )
    assert "Using the existing database" in run.stdout
    assert _calls(stubs) == "uvicorn nlq.api:app --host 0.0.0.0 --port 8000\n"


def test_the_dockerfile_never_names_the_key() -> None:
    dockerfile = DOCKERFILE.read_text(encoding="utf-8")
    assert "ANTHROPIC_API_KEY" not in dockerfile
    assert "ENTRYPOINT" in dockerfile and "docker/entrypoint.sh" in dockerfile
