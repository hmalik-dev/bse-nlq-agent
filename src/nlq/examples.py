"""The six starter questions the ask screen offers as chips.

The list is the one in `docs/design.md` under "Example questions", in
that order; the badge names the club mark drawn on the chip.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

Badge = Literal["nets", "liberty"]


class ExampleQuestion(BaseModel):
    """One chip: the question it asks, and which club mark it carries, if any."""

    question: str
    badge: Badge | None = None


EXAMPLE_QUESTIONS: tuple[ExampleQuestion, ...] = (
    ExampleQuestion(
        question="How many tickets did we sell for Nets home games last month?", badge="nets"
    ),
    ExampleQuestion(question="Top 5 event categories by total revenue"),
    ExampleQuestion(question="Which 2024 events had the highest average ticket price?"),
    ExampleQuestion(
        question="Which Liberty home games sold the most tickets this season?", badge="liberty"
    ),
    ExampleQuestion(question="How much revenue did refunds cost us last season?"),
    ExampleQuestion(question="Compare web and box office sales for concerts"),
)
