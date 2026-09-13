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


def test_the_summary_quotes_each_models_score_and_leaves_the_table_to_the_report() -> None:
    rows = summary_rows()
    assert list(rows) == ["claude-sonnet-5", "claude-haiku-4-5"]
    assert f"Claude Sonnet 5 passed {rows['claude-sonnet-5'][1]} golden questions" in README
    assert f"Haiku scored {rows['claude-haiku-4-5'][1]}" in README
    assert SUMMARY_ROW.search(README) is None


def test_the_headline_quotes_the_chosen_models_mean_cost_and_latency() -> None:
    _, _, _, latency, mean_cost, _ = summary_rows()["claude-sonnet-5"]
    assert (
        f"- **Cost:** {mean_cost} per question on average, with a median latency of {latency}."
        in README
    )


def test_every_dollar_figure_comes_from_the_latest_evaluation_run() -> None:
    rows = summary_rows().values()
    rerun_cost = sum(float(cells[5].lstrip("$")) for cells in rows)
    allowed = set(DOLLAR_FIGURE.findall(EVAL_RESULTS)) | {f"${rerun_cost:.2f}"}
    assert set(DOLLAR_FIGURE.findall(README)) <= allowed
    assert f"about ${rerun_cost:.2f}" in README


def test_every_path_the_readme_names_exists() -> None:
    paths = REPO_PATH.findall(README)
    assert "src/nlq/agent/agent.py" in paths
    missing = [path for path in paths if not (PROJECT_ROOT / path).exists()]
    assert missing == []
