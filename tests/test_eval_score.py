"""The scorer: row comparison with tolerance, and the judge for every expectation."""

from __future__ import annotations

import pytest

from eval.score import GoldenEntry, Verdict, compare, is_ordered, judge
from nlq.agent.executor import QueryResult
from nlq.agent.models import AskResult, ErrorInfo, Trace

ORDERED_SQL = "SELECT category, COUNT(*) AS n FROM events GROUP BY category ORDER BY n DESC"
UNORDERED_SQL = "SELECT category, COUNT(*) AS n FROM events GROUP BY category"
SUBQUERY_ORDERED_SQL = (
    "SELECT COUNT(*) FROM (SELECT event_id FROM events ORDER BY event_date LIMIT 5)"
)


def rows(*values: list[object], truncated: bool = False) -> QueryResult:
    return QueryResult(
        columns=[f"c{i}" for i in range(len(values[0]) if values else 0)],
        rows=[list(row) for row in values],
        row_count=len(values),
        truncated=truncated,
        elapsed_ms=1,
    )


def entry(expect: str, sql: str | None = None) -> GoldenEntry:
    return GoldenEntry(id="q", question="Q?", tags=["simple"], expect=expect, sql=sql)


def result(status: str, query: QueryResult | None = None, error: str | None = None) -> AskResult:
    trace = Trace(
        steps=[], repairs=0, model="m", total_ms=1, input_tokens=1, output_tokens=1, cost_usd=0.0
    )
    fields = {}
    if query is not None:
        fields = dict(
            columns=query.columns,
            rows=query.rows,
            row_count=query.row_count,
            truncated=query.truncated,
        )
    return AskResult(
        status=status,
        question="Q?",
        trace=trace,
        error=ErrorInfo(code=error, message="failed") if error else None,
        **fields,
    )


def test_unordered_rows_match_in_any_order() -> None:
    assert compare(rows(["a", 1], ["b", 2]), rows(["b", 2], ["a", 1]), ordered=False)


def test_ordered_rows_must_match_in_order() -> None:
    assert not compare(rows(["a", 1], ["b", 2]), rows(["b", 2], ["a", 1]), ordered=True)
    assert compare(rows(["a", 1], ["b", 2]), rows(["a", 1], ["b", 2]), ordered=True)


def test_duplicates_are_counted_as_a_multiset() -> None:
    assert not compare(rows(["a", 1], ["a", 1]), rows(["a", 1], ["b", 1]), ordered=False)


def test_numbers_inside_half_a_percent_match() -> None:
    assert compare(rows([1000.0]), rows([1004.0]), ordered=False)
    assert compare(rows([1_234_567]), rows([1_234_567.4]), ordered=False)


def test_numbers_outside_the_tolerance_do_not_match() -> None:
    assert not compare(rows([1000.0]), rows([1006.0]), ordered=False)
    assert not compare(rows([100]), rows([101]), ordered=False)


def test_small_numbers_match_within_a_cent() -> None:
    assert compare(rows([0.001]), rows([0.009]), ordered=False)
    assert not compare(rows([0.0]), rows([0.02]), ordered=False)


def test_a_different_column_count_fails() -> None:
    assert not compare(rows(["a", 1]), rows(["a"]), ordered=False)


def test_an_extra_constant_label_column_passes() -> None:
    assert compare(rows([333707]), rows([2024, 333707]), ordered=False)
    assert compare(rows(["a", 1], ["b", 2]), rows(["Nets", "a", 1], ["Nets", "b", 2]), ordered=True)


def test_an_extra_varying_column_fails() -> None:
    labeled = rows([2024, "a", 1], [2025, "b", 2])
    assert not compare(rows(["a", 1], ["b", 2]), labeled, ordered=False)


def test_a_wrong_measure_with_a_label_column_fails() -> None:
    assert not compare(rows([333707]), rows([2024, 290000]), ordered=False)


def test_a_different_row_count_fails() -> None:
    assert not compare(rows(["a", 1]), rows(["a", 1], ["b", 2]), ordered=False)


def test_a_truncated_actual_result_fails() -> None:
    assert not compare(rows(["a", 1]), rows(["a", 1], truncated=True), ordered=False)


def test_none_equals_none_and_nothing_else() -> None:
    assert compare(rows([None, "x"]), rows([None, "x"]), ordered=False)
    assert not compare(rows([None]), rows([0]), ordered=False)
    assert not compare(rows([0]), rows([None]), ordered=False)


def test_strings_match_after_stripping() -> None:
    assert compare(rows(["Concert "]), rows([" Concert"]), ordered=False)
    assert not compare(rows(["Concert"]), rows(["concert"]), ordered=False)


def test_is_ordered_reads_only_the_top_level_order_by() -> None:
    assert is_ordered(ORDERED_SQL)
    assert not is_ordered(UNORDERED_SQL)
    assert not is_ordered(SUBQUERY_ORDERED_SQL)


def test_answered_passes_only_when_status_is_answered_and_rows_match() -> None:
    golden = entry("answered", UNORDERED_SQL)
    expected = rows(["a", 1], ["b", 2])
    assert judge(golden, result("answered", rows(["b", 2], ["a", 1])), expected) == Verdict(
        True, "rows match the reference"
    )
    assert judge(golden, result("answered", rows(["a", 1], ["b", 3])), expected) == Verdict(
        False, "rows differ from the reference"
    )
    assert judge(golden, result("empty", rows()), expected) == Verdict(
        False, "expected an answer, got empty"
    )


def test_answered_without_a_reference_result_is_a_harness_error() -> None:
    with pytest.raises(ValueError):
        judge(entry("answered", UNORDERED_SQL), result("answered", rows(["a"])), None)


def test_empty_passes_on_empty_and_fails_on_an_answer() -> None:
    assert judge(entry("empty"), result("empty"), None).passed
    verdict = judge(entry("empty"), result("answered", rows([0])), None)
    assert verdict == Verdict(False, "expected empty, got answered")


def test_unanswerable_passes_only_on_unanswerable() -> None:
    assert judge(entry("unanswerable"), result("unanswerable"), None).passed
    assert not judge(entry("unanswerable"), result("blocked"), None).passed


def test_blocked_accepts_either_refusal_and_records_which() -> None:
    golden = entry("blocked")
    assert judge(golden, result("blocked"), None) == Verdict(True, "refused as blocked")
    assert judge(golden, result("unanswerable"), None) == Verdict(True, "refused as unanswerable")
    assert judge(golden, result("answered", rows([1])), None) == Verdict(
        False, "expected a refusal, got answered"
    )


def test_an_error_result_names_its_code_in_the_reason() -> None:
    verdict = judge(entry("answered", UNORDERED_SQL), result("error", error="rate_limited"), None)
    assert verdict == Verdict(False, "expected an answer, got error (rate_limited)")
