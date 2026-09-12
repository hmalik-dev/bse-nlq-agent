"""What a model call costs, so every result can carry its price in dollars.

One table serves the app and the evaluation. There is no spend guard: the
evaluation sums these numbers to compare models, and nothing else reads them.
"""

from __future__ import annotations

# Dollars per million tokens, (input, output).
PRICES: dict[str, tuple[float, float]] = {
    "claude-opus-5": (5.00, 25.00),
    "claude-sonnet-5": (2.00, 10.00),
    "claude-haiku-4-5": (1.00, 5.00),
}

# An unknown model is priced at the dearest rate, so a misconfigured name
# overstates the cost rather than hiding it.
FALLBACK_MODEL = "claude-opus-5"
FREE_MODEL_MARKER = "fake"
TOKENS_PER_PRICE_UNIT = 1_000_000
DECIMALS = 6


def cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    """Price one call. A fake model costs nothing; an unknown one costs Opus rates."""
    if FREE_MODEL_MARKER in model:
        return 0.0
    input_price, output_price = PRICES.get(model, PRICES[FALLBACK_MODEL])
    dollars = (input_tokens * input_price + output_tokens * output_price) / TOKENS_PER_PRICE_UNIT
    return round(dollars, DECIMALS)
