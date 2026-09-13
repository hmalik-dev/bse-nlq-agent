"""The hosted demo's configuration: fly.toml says what the ticket says, the
entrypoint honours the seed scale, and deploy.sh takes every value from the
environment and stops early when one is missing."""

from __future__ import annotations

import os
import subprocess
import tomllib
from pathlib import Path

import pytest

from nlq.config import PROJECT_ROOT

FLY_TOML = PROJECT_ROOT / "fly.toml"
DEPLOY = PROJECT_ROOT / "scripts" / "deploy.sh"
ENTRYPOINT = PROJECT_ROOT / "docker" / "entrypoint.sh"
SYSTEM_PATH = "/usr/bin:/bin"
KEY_VARIABLE = "ANTHROPIC_API_KEY"
PLACEHOLDER_KEY = "placeholder-from-the-environment"

FAKE_FLY = """#!/usr/bin/env bash
printf '%s\\n' "$*" >> "$FLY_LOG"
case "$1 $2" in
  "auth whoami") exit 0 ;;
  "status --app") exit "$FLY_APP_MISSING" ;;
  "volumes list") echo "$FLY_VOLUMES" ;;
  "secrets import") cat >> "$FLY_LOG" ;;
esac
"""


def fly_config() -> dict:
    return tomllib.loads(FLY_TOML.read_text(encoding="utf-8"))


def test_fly_toml_describes_one_warm_machine_in_ewr_with_a_volume() -> None:
    fly = fly_config()
    assert fly["primary_region"] == "ewr"
    assert fly["mounts"] == {"source": "data", "destination": "/data", "initial_size": "1gb"}
    assert fly["vm"] == [{"size": "shared-cpu-1x", "memory": "1gb"}]
    service = fly["http_service"]
    assert service["internal_port"] == 8000
    assert service["force_https"] is True
    assert service["auto_stop_machines"] == "off"
    assert service["min_machines_running"] == 1


def test_fly_toml_checks_health_every_thirty_seconds_with_time_to_seed() -> None:
    fly = fly_config()
    (check,) = fly["http_service"]["checks"]
    assert check["path"] == "/api/health"
    assert check["method"] == "GET"
    assert check["interval"] == "30s"
    assert check["grace_period"].endswith("m") and int(check["grace_period"][:-1]) >= 3
    assert check["headers"]["Host"] == f"{fly['app']}.fly.dev"


def test_fly_toml_points_the_app_at_the_volume_a_small_seed_and_its_own_host() -> None:
    fly = fly_config()
    assert fly["env"] == {
        "NLQ_DATABASE_PATH": "/data/tickets.db",
        "NLQ_SEED_SCALE": "0.2",
        "NLQ_ALLOWED_HOSTS": f"{fly['app']}.fly.dev",
    }
    assert "ANTHROPIC" not in FLY_TOML.read_text(encoding="utf-8")


def fake_tools(tmp_path: Path) -> Path:
    """A bin directory whose python records its arguments and whose uvicorn exits at once."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    python = bin_dir / "python"
    python.write_text('#!/usr/bin/env bash\nprintf \'%s\\n\' "$*" > "$SEED_LOG"\n')
    uvicorn = bin_dir / "uvicorn"
    uvicorn.write_text("#!/usr/bin/env bash\nexit 0\n")
    for tool in (python, uvicorn):
        tool.chmod(0o755)
    return bin_dir


@pytest.mark.parametrize(
    ("scale_env", "expected"), [({}, "1.0"), ({"NLQ_SEED_SCALE": "0.2"}, "0.2")]
)
def test_the_entrypoint_seeds_at_the_configured_scale_and_says_so(
    tmp_path: Path, scale_env: dict[str, str], expected: str
) -> None:
    seed_log = tmp_path / "seed.log"
    env = {
        "PATH": f"{fake_tools(tmp_path)}:{SYSTEM_PATH}",
        "NLQ_DATABASE_PATH": str(tmp_path / "tickets.db"),
        "SEED_LOG": str(seed_log),
        **scale_env,
    }
    run = subprocess.run(
        ["bash", str(ENTRYPOINT)], env=env, capture_output=True, text=True, timeout=10, check=True
    )
    assert seed_log.read_text() == f"-m nlq.db.seed --scale {expected}\n"
    assert f"at scale {expected}" in run.stdout


def run_deploy(tmp_path: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(DEPLOY)], env=env, capture_output=True, text=True, timeout=10, cwd=tmp_path
    )


def test_deploy_stops_before_touching_fly_when_the_key_is_missing(tmp_path: Path) -> None:
    run = run_deploy(tmp_path, {"PATH": SYSTEM_PATH})
    assert run.returncode == 1
    assert f"{KEY_VARIABLE} is not set" in run.stderr


def test_deploy_stops_with_an_install_link_when_flyctl_is_missing(tmp_path: Path) -> None:
    run = run_deploy(tmp_path, {"PATH": SYSTEM_PATH, KEY_VARIABLE: PLACEHOLDER_KEY})
    assert run.returncode == 1
    assert "flyctl is not installed" in run.stderr


def deploy_with_fake_fly(tmp_path: Path, *, app_missing: bool, volumes: str) -> list[str]:
    """Run deploy.sh against a recording fly, and return the fly commands it issued."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "flyctl").write_text(FAKE_FLY)
    (bin_dir / "flyctl").chmod(0o755)
    log = tmp_path / "fly.log"
    env = {
        "PATH": f"{bin_dir}:{SYSTEM_PATH}",
        KEY_VARIABLE: PLACEHOLDER_KEY,
        "FLY_LOG": str(log),
        "FLY_APP_MISSING": "1" if app_missing else "0",
        "FLY_VOLUMES": volumes,
    }
    run = run_deploy(tmp_path, env)
    assert run.returncode == 0, run.stderr
    return log.read_text().splitlines()


def test_deploy_creates_the_app_and_volume_once_and_sets_the_key_from_the_environment(
    tmp_path: Path,
) -> None:
    app = fly_config()["app"]
    calls = deploy_with_fake_fly(tmp_path, app_missing=True, volumes="[]")
    assert calls == [
        "auth whoami",
        f"status --app {app}",
        f"apps create {app} --org personal",
        f"volumes list --app {app} --json",
        f"volumes create data --app {app} --region ewr --size 1 --yes",
        f"secrets import --app {app} --stage",
        f"{KEY_VARIABLE}={PLACEHOLDER_KEY}",
        f"deploy --app {app} --ha=false",
    ]


def test_deploy_is_idempotent_when_the_app_and_volume_already_exist(tmp_path: Path) -> None:
    calls = deploy_with_fake_fly(tmp_path, app_missing=False, volumes='[{"name": "data"}]')
    assert not any(call.startswith(("apps create", "volumes create")) for call in calls)
    assert calls[-1] == f"deploy --app {fly_config()['app']} --ha=false"


def test_deploy_pipes_the_key_from_the_environment_and_never_puts_it_in_an_argument() -> None:
    script = DEPLOY.read_text(encoding="utf-8")
    assert f'"${KEY_VARIABLE}" | "$fly" secrets import' in script
    assert "secrets set" not in script
    assert os.access(DEPLOY, os.X_OK)
