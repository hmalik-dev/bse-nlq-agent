"""Every result carries its price; an unknown model errs on the expensive side."""

from __future__ import annotations

import pytest

from nlq.pricing import PRICES, cost_usd

INPUT_TOKENS = 1_000_000
OUTPUT_TOKENS = 100_000


@pytest.mark.parametrize(
    ("model", "expected"),
    [("claude-opus-5", 7.5), ("claude-sonnet-5", 3.0), ("claude-haiku-4-5", 1.5)],
)
def test_each_model_is_priced_from_the_table(model: str, expected: float) -> None:
    assert cost_usd(model, INPUT_TOKENS, OUTPUT_TOKENS) == expected


def test_the_table_holds_the_three_models_the_evaluation_compares() -> None:
    assert PRICES == {
        "claude-opus-5": (5.00, 25.00),
        "claude-sonnet-5": (2.00, 10.00),
        "claude-haiku-4-5": (1.00, 5.00),
    }


def test_an_unknown_model_costs_opus_rates() -> None:
    assert cost_usd("claude-mystery-9", INPUT_TOKENS, OUTPUT_TOKENS) == 7.5


@pytest.mark.parametrize("model", ["fake", "claude-fake"])
def test_a_fake_model_costs_nothing(model: str) -> None:
    assert cost_usd(model, INPUT_TOKENS, OUTPUT_TOKENS) == 0.0


def test_the_cost_is_rounded_to_six_places() -> None:
    assert cost_usd("claude-haiku-4-5", 1, 1) == 0.000006
    assert cost_usd("claude-haiku-4-5", 1200, 80) == 0.0016
