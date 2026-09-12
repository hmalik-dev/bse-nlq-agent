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


def test_assumptions_are_capped_in_count_and_length() -> None:
    with pytest.raises(ValidationError):
        SqlPlan(answerable=True, sql=SQL, assumptions=["a", "b", "c", "d"])
    with pytest.raises(ValidationError):
        SqlPlan(answerable=True, sql=SQL, assumptions=["x" * 121])
    assert SqlPlan(answerable=True, sql=SQL, assumptions=["x" * 120] * 3).assumptions


def test_the_decline_category_is_one_of_two_values() -> None:
    with pytest.raises(ValidationError):
        SqlPlan(answerable=False, decline_reason="no", decline_category="rude")
