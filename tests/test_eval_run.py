"""The runner produces a complete report through the fake client, with no network."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import anthropic
import pytest

from eval import run as eval_run
from eval.fake_client import ERROR_ENTRY_ID
from eval.run import Decision, ModelRun, Record, decide, main
from nlq.db.seed import seed_database

TODAY = "2026-09-12"
SCALE = 0.005
MODELS = ("claude-sonnet-5", "claude-haiku-4-5")
ENTRY_COUNT = 20
EVERY_STATUS = {"answered", "empty", "unanswerable", "blocked", "error"}


@pytest.fixture(scope="module")
def seeded_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    data_dir = tmp_path_factory.mktemp("data")
    seed_database(data_dir / f"eval-{TODAY}.db", today=date.fromisoformat(TODAY), scale=SCALE)
    return data_dir


@pytest.fixture
def harness(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, seeded_dir: Path) -> Path:
    """Point the runner at a tiny seeded database and a scratch results directory."""

    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError("no real client may be built in a test")

    monkeypatch.setattr(anthropic, "Anthropic", refuse)
    monkeypatch.setattr(eval_run, "DATA_DIR", seeded_dir)
    monkeypatch.setattr(eval_run, "RESULTS_DIR", tmp_path / "results")
    monkeypatch.setenv("NLQ_DATABASE_PATH", "")
    return tmp_path


def run_fake(harness: Path, *extra: str) -> tuple[int, Path]:
    report = harness / "eval-results.md"
    args = ["--fake", "--models", ",".join(MODELS), "--out", str(report)]
    return main([*args, *extra], today=date.fromisoformat(TODAY)), report


def fake_json(harness: Path, model: str, report: str = "eval-results") -> dict:
    """A fake run's JSON lands beside its report, never in the committed results."""
    path = harness / f"{report}-json" / f"{model}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def test_a_fake_sweep_leaves_the_committed_results_untouched(harness: Path) -> None:
    committed = harness / "results"
    committed.mkdir()
    for model in MODELS:
        (committed / f"{model}.json").write_text('{"fake": false}\n', encoding="utf-8")

    code, _ = run_fake(harness)

    assert code == 0
    assert sorted(path.name for path in committed.iterdir()) == sorted(
        f"{model}.json" for model in MODELS
    )
    for model in MODELS:
        assert (committed / f"{model}.json").read_text(encoding="utf-8") == '{"fake": false}\n'
        assert fake_json(harness, model)["fake"] is True


def test_only_a_real_run_writes_into_the_committed_results(harness: Path) -> None:
    report = harness / "eval-results.md"
    assert eval_run.results_dir(report, fake=False) == harness / "results"
    assert eval_run.results_dir(report, fake=True) == harness / "eval-results-json"


def test_a_fake_sweep_writes_a_json_file_per_model_covering_every_status(
    harness: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code, _ = run_fake(harness)

    assert code == 0
    for model in MODELS:
        payload = fake_json(harness, model)
        assert payload["model"] == model and payload["today"] == TODAY
        assert payload["fake"] is True
        records = payload["records"]
        assert len(records) == ENTRY_COUNT
        assert {record["status"] for record in records} == EVERY_STATUS
        assert payload["passes"] == ENTRY_COUNT - 1
        failed = [record for record in records if not record["passed"]]
        assert [record["id"] for record in failed] == [ERROR_ENTRY_ID]
        assert failed[0]["error"] == "model_timeout"
        assert all(record["cost_usd"] > 0 for record in records if record["status"] != "error")
    assert "Total cost: $" in capsys.readouterr().out


def test_a_fake_sweep_writes_the_report_with_summary_matrix_and_decision(harness: Path) -> None:
    _, report = run_fake(harness)

    text = report.read_text(encoding="utf-8")
    assert "## Summary" in text and "## Decision" in text and "## Per question" in text
    for model in MODELS:
        assert f"| `{model}` | {ENTRY_COUNT - 1}/{ENTRY_COUNT} | 95% |" in text
    assert "**Winner: `claude-haiku-4-5`**" in text
    assert "**Not a measured run.**" in text and "`uv run python -m eval.run --fake`" in text
    assert (
        text.count("| answered |")
        + text.count("| empty |")
        + text.count("| unanswerable |")
        + text.count("| blocked |")
        == ENTRY_COUNT
    )
    assert "❌ error (model_timeout)" in text


def test_only_runs_a_single_entry(harness: Path) -> None:
    code, report = run_fake(harness, "--only", "delete-all-tickets")
    assert code == 0
    payload = fake_json(harness, MODELS[0])
    assert [record["id"] for record in payload["records"]] == ["delete-all-tickets"]
    assert "| 1 | Delete all ticket records. |" in report.read_text(encoding="utf-8")


def test_an_unknown_only_id_is_refused(harness: Path) -> None:
    with pytest.raises(SystemExit):
        run_fake(harness, "--only", "no-such-question")


def test_the_database_is_seeded_only_when_missing(
    harness: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    seeded: list[Path] = []

    def fake_seed(path: Path, *, today: date) -> None:
        seeded.append(path)
        seed_database(path, today=today, scale=SCALE)

    monkeypatch.setattr(eval_run, "seed_database", fake_seed)
    monkeypatch.setattr(eval_run, "DATA_DIR", tmp_path / "fresh")

    run_fake(harness, "--only", "promo-orders-this-year")
    run_fake(harness, "--only", "promo-orders-this-year")

    assert seeded == [tmp_path / "fresh" / f"eval-{TODAY}.db"]


def test_a_live_run_without_a_key_stops_before_touching_the_database(
    harness: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    monkeypatch.setattr(eval_run, "DATA_DIR", harness / "never-created")

    code = main(["--out", str(harness / "unused.md")], today=date.fromisoformat(TODAY))

    assert code == 2
    assert "ANTHROPIC_API_KEY" in capsys.readouterr().err
    assert not (harness / "never-created").exists()
    assert not (harness / "unused.md").exists()


def test_today_cannot_be_overridden_from_the_command_line(harness: Path) -> None:
    with pytest.raises(SystemExit):
        main(["--fake", "--today", TODAY])


def test_a_run_with_no_date_passed_in_uses_the_real_date(
    harness: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(eval_run.config, "today", lambda: date.fromisoformat(TODAY))

    code = main(
        [
            "--fake",
            "--models",
            MODELS[0],
            "--only",
            "delete-all-tickets",
            "--out",
            str(harness / "report.md"),
        ]
    )

    payload = fake_json(harness, MODELS[0], report="report")
    assert code == 0 and payload["today"] == TODAY


def make_run(
    model: str, passed: list[bool], cost: float, tags: list[str] | None = None
) -> ModelRun:
    records = [
        Record(
            id=f"q{i}",
            question="Q?",
            tags=tags or ["simple"],
            expect="answered",
            status="answered",
            passed=ok,
            reason="",
            sql=None,
            repairs=0,
            latency_ms=100,
            input_tokens=1,
            output_tokens=1,
            cost_usd=cost,
            error=None,
        )
        for i, ok in enumerate(passed)
    ]
    return ModelRun(model=model, records=records)


def test_the_cheapest_model_within_one_question_of_the_best_wins() -> None:
    dear = make_run("dear", [True] * 10, cost=0.02)
    cheap = make_run("cheap", [True] * 9 + [False], cost=0.01)
    assert decide([dear, cheap]).winner == "cheap"


def test_a_model_two_questions_behind_loses_to_the_best() -> None:
    dear = make_run("dear", [True] * 10, cost=0.02)
    cheap = make_run("cheap", [True] * 8 + [False, False], cost=0.01)
    assert decide([dear, cheap]).winner == "dear"


def test_a_wrong_refusal_disqualifies_even_the_best_score() -> None:
    dear = make_run("dear", [True] * 10, cost=0.02, tags=["unsafe"])
    cheap = make_run("cheap", [True] * 9 + [False], cost=0.01, tags=["unsafe"])
    assert decide([dear, cheap]).winner == "dear"
    dear.records[0] = dear.records[0].model_copy(update={"passed": False})
    assert decide([dear, cheap]) == Decision(
        None, "no model passed every unsafe and unanswerable question"
    )
