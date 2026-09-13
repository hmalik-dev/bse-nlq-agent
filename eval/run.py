"""Run the golden set against each candidate model and write the results.

    uv run python -m eval.run --models claude-sonnet-5,claude-haiku-4-5

Each question is asked once per model, sequentially, through `Agent.ask`, with
today as the real date and a database seeded for it. The
outcome is one JSON file per model, `docs/eval-results.md`, and the model the
decision rule in `docs/decisions.md` picks. `--fake` drives the same pipeline
through a scripted client, which is how the harness is debugged for nothing.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from pydantic import BaseModel

from eval.fake_client import GoldenFakeClient
from eval.report import write_report
from eval.score import GoldenEntry, judge, load_golden
from nlq import config
from nlq.agent.agent import Agent
from nlq.agent.answer import AnswerWriter
from nlq.agent.executor import Executor, QueryResult
from nlq.agent.llm import SqlWriter
from nlq.agent.sql_guard import guard
from nlq.db.seed import seed_database

DEFAULT_MODELS = "claude-sonnet-5,claude-haiku-4-5"
DEFAULT_REPORT = config.PROJECT_ROOT / "docs" / "eval-results.md"
DATA_DIR = config.PROJECT_ROOT / "data"
RESULTS_DIR = Path(__file__).resolve().parent / "results"

# A model may trail the best score by this many questions and still be chosen.
ALLOWED_SHORTFALL = 1
# The tags every eligible model must pass in full: no refusal may be wrong.
REFUSAL_TAGS = ("unsafe", "unanswerable")

EXIT_OK = 0
EXIT_MISSING_KEY = 2


class Record(BaseModel):
    """One question asked of one model, and how it went."""

    id: str
    question: str
    tags: list[str]
    expect: str
    status: str
    passed: bool
    reason: str
    sql: str | None
    repairs: int
    latency_ms: int
    input_tokens: int
    output_tokens: int
    cost_usd: float
    error: str | None


@dataclass
class ModelRun:
    """Every record for one model, with the numbers the decision reads."""

    model: str
    records: list[Record]

    @property
    def passes(self) -> int:
        return sum(record.passed for record in self.records)

    @property
    def accuracy(self) -> float:
        return self.passes / len(self.records) if self.records else 0.0

    @property
    def median_latency_ms(self) -> float:
        return statistics.median(record.latency_ms for record in self.records)

    @property
    def total_cost_usd(self) -> float:
        return sum(record.cost_usd for record in self.records)

    @property
    def mean_cost_usd(self) -> float:
        return self.total_cost_usd / len(self.records) if self.records else 0.0

    @property
    def refusals_right(self) -> bool:
        """Every unsafe and unanswerable question was refused."""
        return all(
            record.passed
            for record in self.records
            if any(tag in REFUSAL_TAGS for tag in record.tags)
        )


@dataclass(frozen=True)
class Decision:
    """The model the rule picked, or None with the reason nothing qualified."""

    winner: str | None
    reason: str


def main(argv: list[str] | None = None, *, today: date | None = None) -> int:
    """`today` is the real date; tests pass one in so a run is reproducible."""
    args = parse_args(argv)
    if not args.fake and not config.anthropic_api_key():
        print("ANTHROPIC_API_KEY is not set. Add it to .env, or run with --fake.", file=sys.stderr)
        return EXIT_MISSING_KEY
    today = today or config.today()
    entries = select_entries(load_golden(today), args.only)
    database = prepare_database(today)
    expected = reference_results(entries, database)
    runs = [
        sweep(model, entries, expected, database, today, fake=args.fake)
        for model in args.models.split(",")
    ]
    for run in runs:
        write_json(run, today, database, fake=args.fake)
    decision = decide(runs)
    write_report(Path(args.out), runs, decision, today, database, fake=args.fake)
    print(f"Total cost: ${sum(run.total_cost_usd for run in runs):.4f}")
    print(f"Decision: {decision.winner or 'no model qualifies'} - {decision.reason}")
    return EXIT_OK


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="python -m eval.run", description=__doc__)
    parser.add_argument("--models", default=DEFAULT_MODELS, help="comma-separated model names")
    parser.add_argument("--only", help="run a single golden entry by id")
    parser.add_argument("--fake", action="store_true", help="use the scripted client, no API")
    parser.add_argument("--out", default=str(DEFAULT_REPORT), help="where the markdown report goes")
    return parser.parse_args(argv)


def select_entries(entries: list[GoldenEntry], only: str | None) -> list[GoldenEntry]:
    if only is None:
        return entries
    selected = [entry for entry in entries if entry.id == only]
    if not selected:
        raise SystemExit(f"No golden entry with id {only!r}")
    return selected


def prepare_database(today: date) -> Path:
    """Point the agent at a database seeded for `today`, seeding it if this date has none yet."""
    path = DATA_DIR / f"eval-{today.isoformat()}.db"
    os.environ["NLQ_DATABASE_PATH"] = str(path)
    if not path.is_file():
        print(f"Seeding {path} at full scale for {today.isoformat()} ...")
        seed_database(path, today=today)
    return path


def reference_results(entries: list[GoldenEntry], database: Path) -> dict[str, QueryResult]:
    """Run every reference query once, through the same guard and executor as the agent."""
    executor = Executor(database)
    return {
        entry.id: executor.run(guard(entry.sql, max_rows=executor.max_rows).sql)
        for entry in entries
        if entry.sql
    }


def build_agent(
    model: str, entries: list[GoldenEntry], database: Path, today: date, *, fake: bool
) -> Agent:
    """The same wiring as `Agent.from_env`, with the model and database chosen per run.

    `from_env` reads the database path once at import, so the per-date file set
    by `prepare_database` would not reach it. Both writers get the candidate model
    so cost per question reflects one model end to end.
    """
    client = GoldenFakeClient(entries) if fake else None
    return Agent(
        SqlWriter(client, model=model),
        Executor(database),
        AnswerWriter(client, model=model),
        today=today,
    )


def sweep(
    model: str,
    entries: list[GoldenEntry],
    expected: dict[str, QueryResult],
    database: Path,
    today: date,
    *,
    fake: bool,
) -> ModelRun:
    """Ask every question of one model, in order, recording each outcome."""
    agent = build_agent(model, entries, database, today, fake=fake)
    records = []
    for entry in entries:
        record = ask_one(agent, entry, expected.get(entry.id))
        records.append(record)
        print(_progress_line(model, record))
    return ModelRun(model=model, records=records)


def ask_one(agent: Agent, entry: GoldenEntry, expected: QueryResult | None) -> Record:
    """One question, judged. `ask` never raises, but a harness fault still becomes a record."""
    try:
        result = agent.ask(entry.question)
    except Exception as error:  # the sweep must finish whatever one call does
        return _failed_record(entry, type(error).__name__)
    verdict = judge(entry, result, expected)
    return Record(
        **_entry_fields(entry),
        status=result.status,
        passed=verdict.passed,
        reason=verdict.reason,
        sql=result.sql,
        repairs=result.trace.repairs,
        latency_ms=result.trace.total_ms,
        input_tokens=result.trace.input_tokens,
        output_tokens=result.trace.output_tokens,
        cost_usd=result.trace.cost_usd,
        error=result.error.code if result.error else None,
    )


def _entry_fields(entry: GoldenEntry) -> dict[str, object]:
    return {
        "id": entry.id,
        "question": entry.question,
        "tags": list(entry.tags),
        "expect": entry.expect,
    }


def _failed_record(entry: GoldenEntry, error: str) -> Record:
    return Record(
        **_entry_fields(entry),
        status="error",
        passed=False,
        reason=f"the call raised {error}",
        sql=None,
        repairs=0,
        latency_ms=0,
        input_tokens=0,
        output_tokens=0,
        cost_usd=0.0,
        error=error,
    )


def _progress_line(model: str, record: Record) -> str:
    mark = "PASS" if record.passed else "FAIL"
    return (
        f"[{model}] {record.id}: {mark} {record.status} "
        f"{record.latency_ms} ms ${record.cost_usd:.4f} - {record.reason}"
    )


def decide(runs: list[ModelRun]) -> Decision:
    """The rule from docs/decisions.md: cheapest within one question of the best,
    among models that got every unsafe and unanswerable question right."""
    best = max(run.passes for run in runs)
    eligible = [
        run for run in runs if run.passes >= best - ALLOWED_SHORTFALL and run.refusals_right
    ]
    if not eligible:
        return Decision(None, "no model passed every unsafe and unanswerable question")
    winner = min(eligible, key=lambda run: run.mean_cost_usd)
    return Decision(
        winner.model,
        f"{winner.passes}/{len(winner.records)} against a best of {best}, "
        f"cheapest of {len(eligible)} eligible at ${winner.mean_cost_usd:.4f} per question",
    )


def write_json(run: ModelRun, today: date, database: Path, *, fake: bool = False) -> Path:
    """One file per model, so a failure's generated SQL can be read after the run.

    `fake` is recorded so a scripted sweep can never be mistaken for a measured one.
    """
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    path = RESULTS_DIR / f"{run.model}.json"
    payload = {
        "model": run.model,
        "today": today.isoformat(),
        "database": database.name,
        "fake": fake,
        "passes": run.passes,
        "accuracy": round(run.accuracy, 4),
        "median_latency_ms": run.median_latency_ms,
        "mean_cost_usd": round(run.mean_cost_usd, 6),
        "total_cost_usd": round(run.total_cost_usd, 6),
        "records": [record.model_dump() for record in run.records],
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


if __name__ == "__main__":
    sys.exit(main())
