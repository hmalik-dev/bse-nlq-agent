"""A plan is either runnable SQL or a stated reason; nothing in between gets through."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from nlq.agent.models import SqlPlan

SQL = "SELECT COUNT(*) FROM tickets"


def test_an_answerable_plan_needs_sql() -> None:
    with pytest.raises(ValidationError):
        SqlPlan(answerable=True, sql=None)
    with pytest.raises(ValidationError):
        SqlPlan(answerable=True, sql="   ")


def test_a_declined_plan_needs_a_reason() -> None:
    with pytest.raises(ValidationError):
        SqlPlan(answerable=False, decline_category="out_of_scope")


def test_extra_assumptions_are_dropped_rather_than_failing_the_plan() -> None:
    plan = SqlPlan(answerable=True, sql=SQL, assumptions=["a", "b", "c", "d"])
    assert plan.assumptions == ["a", "b", "c"]


def test_a_long_assumption_is_kept_whole_rather_than_failing_the_plan() -> None:
    long = (
        "This season is the Nets' 2026-27 season: the latest season label with home games "
        "still to come."
    )
    plan = SqlPlan(answerable=True, sql=SQL, assumptions=[long + " " + long])
    assert plan.assumptions == [long + " " + long]


def test_the_schema_still_asks_the_model_for_three_short_assumptions() -> None:
    schema = SqlPlan.model_json_schema()["properties"]["assumptions"]
    assert schema["maxItems"] == 3
    assert schema["items"]["maxLength"] == 120


def test_the_decline_category_is_one_of_two_values() -> None:
    with pytest.raises(ValidationError):
        SqlPlan(answerable=False, decline_reason="no", decline_category="rude")
