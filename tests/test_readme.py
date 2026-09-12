"""The README quotes the repository truthfully: current figures, real paths."""

from __future__ import annotations

import re

from nlq.config import PROJECT_ROOT

README = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
EVAL_RESULTS = (PROJECT_ROOT / "docs" / "eval-results.md").read_text(encoding="utf-8")

SUMMARY_ROW = re.compile(r"^\| `claude-[\w-]+` \|.*\|$", re.MULTILINE)
DOLLAR_FIGURE = re.compile(r"\$\d+\.\d{4}")
REPO_PATH = re.compile(r"`((?:src|tests|eval|docs|scripts|web|design-plan)/[^`\s]*)`")


def test_the_model_table_matches_the_latest_evaluation_run() -> None:
    summary_rows = SUMMARY_ROW.findall(EVAL_RESULTS.split("## Decision")[0])
    assert len(summary_rows) == 2
    for row in summary_rows:
        assert row in README


def test_every_cost_figure_comes_from_the_latest_evaluation_run() -> None:
    quoted = set(DOLLAR_FIGURE.findall(README))
    assert "$0.0185" in quoted
    assert quoted <= set(DOLLAR_FIGURE.findall(EVAL_RESULTS))


def test_every_path_the_readme_names_exists() -> None:
    paths = REPO_PATH.findall(README)
    assert "src/nlq/agent/agent.py" in paths
    missing = [path for path in paths if not (PROJECT_ROOT / path).exists()]
    assert missing == []
