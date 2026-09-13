"""The README quotes the repository truthfully: the latest evaluation, real paths."""

from __future__ import annotations

import re

from nlq.config import PROJECT_ROOT

README = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
EVAL_RESULTS = (PROJECT_ROOT / "docs" / "eval-results.md").read_text(encoding="utf-8")

SUMMARY_ROW = re.compile(r"^\| `(claude-[\w-]+)` \|.*\|$", re.MULTILINE)
DOLLAR_FIGURE = re.compile(r"\$\d+\.\d+")
REPO_PATH = re.compile(r"`((?:src|tests|eval|docs|scripts|web|design-plan)/[^`\s]*)`")


def summary_rows() -> dict[str, list[str]]:
    """Model name to its summary cells, from the report's table above the decision."""
    summary = EVAL_RESULTS.split("## Decision")[0]
    rows = {m.group(1): m.group(0) for m in SUMMARY_ROW.finditer(summary)}
    return {
        model: [cell.strip() for cell in row.strip("|").split("|")] for model, row in rows.items()
    }


README_SECTIONS = [
    "Run it locally",
    "Other ways to run",
    "Tests",
    "How it works",
    "Results",
    "Tradeoffs",
    "With more time",
    "How it was built",
    "Docs",
]
CONTRIBUTOR_DETAIL = (
    "median latency",
    "never raises",
    "AskResult",
    "NLQ_FAKE_AGENT",
    "--fake",
    "HTTP 200",
    "Seed small",
    "thinner and later",
)


def test_the_readme_is_short_and_follows_the_interviewer_outline() -> None:
    assert len(README.splitlines()) <= 75
    headings = [line[3:] for line in README.splitlines() if line.startswith("## ")]
    assert headings == README_SECTIONS


def test_the_readme_leaves_contributor_detail_to_the_docs() -> None:
    assert [detail for detail in CONTRIBUTOR_DETAIL if detail in README] == []


def test_the_summary_quotes_each_models_score_and_leaves_the_table_to_the_report() -> None:
    rows = summary_rows()
    assert list(rows) == ["claude-sonnet-5", "claude-haiku-4-5"]
    assert f"Claude Sonnet 5 passed {rows['claude-sonnet-5'][1]} test questions" in README
    assert f"Haiku 4.5 scored {rows['claude-haiku-4-5'][1]}" in README
    assert SUMMARY_ROW.search(README) is None


def test_the_headline_quotes_the_chosen_models_mean_cost() -> None:
    mean_cost = summary_rows()["claude-sonnet-5"][4]
    assert f"A question costs {mean_cost} on average." in README


def test_every_dollar_figure_comes_from_the_latest_evaluation_run() -> None:
    assert set(DOLLAR_FIGURE.findall(README)) <= set(DOLLAR_FIGURE.findall(EVAL_RESULTS))


def test_every_path_the_readme_names_exists() -> None:
    paths = REPO_PATH.findall(README)
    assert "src/nlq/agent/agent.py" in paths
    missing = [path for path in paths if not (PROJECT_ROOT / path).exists()]
    assert missing == []


CLAUDE_MD = (PROJECT_ROOT / "CLAUDE.md").read_text(encoding="utf-8")
SCRIPT_TEXT = "\n".join(
    path.read_text(encoding="utf-8") for path in sorted((PROJECT_ROOT / "scripts").glob("*.sh"))
)
DECISIONS = (PROJECT_ROOT / "docs" / "decisions.md").read_text(encoding="utf-8")
INLINE_CODE = re.compile(r"`([^`\n]+)`")
COMMAND_PREFIXES = ("npm ", "uv ", "docker ")


def section(title: str) -> list[str]:
    """The lines under a `## title` heading up to the next one, without surrounding blanks."""
    body = README.split(f"\n## {title}\n", 1)[1].split("\n## ", 1)[0]
    return body.strip("\n").splitlines()


def commands(lines: list[str]) -> list[str]:
    """Inline code and code-block lines that run npm, uv or docker."""
    candidates = [code for line in lines for code in INLINE_CODE.findall(line)] + lines
    return [text.strip() for text in candidates if text.strip().startswith(COMMAND_PREFIXES)]


def test_run_it_locally_is_one_prerequisites_line_and_three_steps_ending_in_npm_run_dev() -> None:
    lines = section("Run it locally")
    assert len(lines) <= 12
    assert "[uv]" in lines[0] and "[Node 24]" in lines[0]
    steps = [line for line in lines if re.match(r"^\d\. ", line)]
    assert [step[:2] for step in steps] == ["1.", "2.", "3."]
    assert "`npm run dev`" in steps[-1]
    text = "\n".join(lines).lower()
    for absent in ("uv run uvicorn", "scripts/smoke.sh", "fake", "canned"):
        assert absent not in text


def test_other_ways_to_run_is_docker_and_the_cli_in_at_most_eight_lines() -> None:
    lines = section("Other ways to run")
    assert len(lines) <= 8
    found = commands(lines)
    assert "docker build -t bse-insights ." in found
    assert any(command.startswith("uv run python -m nlq.ask ") for command in found)


def test_every_setup_command_is_one_claude_md_or_the_scripts_also_use() -> None:
    found = commands(section("Run it locally") + section("Other ways to run") + section("Tests"))
    assert "npm run dev" in found
    assert [command for command in found if command not in CLAUDE_MD + SCRIPT_TEXT] == []


def test_the_readme_drops_the_manual_run_block_and_the_smoke_script() -> None:
    assert "Without `npm run dev`" not in README
    assert "scripts/smoke.sh" not in README


def test_the_decisions_record_the_fakes_exactly_once() -> None:
    entries = [line for line in DECISIONS.splitlines() if line.startswith("- **")]
    assert len([entry for entry in entries if "fake" in entry.lower()]) == 1
