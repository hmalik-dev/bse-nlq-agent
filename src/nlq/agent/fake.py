"""A stand-in agent that answers from canned results, one per screen the UI has.

Switched on with `NLQ_FAKE_AGENT=1`, so the interface can be built and driven
in a browser without a key or a database. The shapes follow the design frames;
the values come from the real schema: event names as the seed writes them,
the real categories, real column names in the SQL. A keyword in the question
picks the outcome; anything else gets the revenue-by-category answer.
"""

from __future__ import annotations

import time
from collections.abc import Callable

from nlq.agent.agent import BLOCKED_ANSWER, EMPTY_SUGGESTIONS
from nlq.agent.models import AskResult, ChartSpec, ErrorInfo, Step, Trace
from nlq.examples import EXAMPLE_QUESTIONS
from nlq.pricing import cost_usd

FAKE_MODEL = "fake"
SLOW_SECONDS = 2
SUGGESTION_COUNT = 3
INPUT_TOKENS = 9800
OUTPUT_TOKENS = 310

# The five steps of one answered question, in order; they add up to TOTAL_MS.
STEP_MS = (
    ("Reading schema", 2),
    ("Writing SQL", 1240),
    ("Checking safety", 8),
    ("Running query", 18),
    ("Writing answer", 892),
)
TOTAL_MS = sum(ms for _, ms in STEP_MS)

CATEGORY_COLUMNS = ["category", "revenue"]
CATEGORY_ROWS: list[list[object]] = [
    ["NBA", 118400215.50],
    ["Concert", 61204880.00],
    ["WNBA", 12910332.25],
    ["Family Show", 9842110.00],
    ["Comedy", 4317905.50],
]
CATEGORY_ANSWER = (
    "NBA games brought in the most revenue at $118.4M, followed by concerts at $61.2M; "
    "together they account for about four fifths of all ticket revenue."
)
CATEGORY_ASSUMPTIONS = [
    "Revenue is the face value of sold tickets; fees, refunds and comps are excluded.",
    "Only events that have already taken place are counted.",
]
CATEGORY_SQL = """\
-- Revenue is SUM(price) over sold tickets; fees, refunds and comps are excluded.
SELECT
    e.category,
    ROUND(SUM(t.price), 2) AS revenue
FROM tickets AS t
JOIN events AS e ON e.event_id = t.event_id
WHERE t.status = 'sold'
  -- events dated after today are on sale, not played
  AND e.event_date <= '2026-09-12'
GROUP BY e.category
ORDER BY revenue DESC
LIMIT 5"""

NETS_COLUMNS = ["event", "event_date", "tickets_sold", "avg_price", "gate_revenue"]
# (opponent, event date, tickets sold, average price): 2026-27 Nets home fixtures.
NETS_FIXTURES = (
    ("New York Knicks", "2026-10-24", 17732, 214.60),
    ("Boston Celtics", "2026-10-31", 17732, 198.25),
    ("Los Angeles Lakers", "2026-11-07", 17732, 226.80),
    ("Golden State Warriors", "2026-11-19", 17612, 205.15),
    ("Philadelphia 76ers", "2026-11-28", 17104, 168.40),
    ("Milwaukee Bucks", "2026-12-05", 16880, 162.90),
    ("Miami Heat", "2026-12-18", 16455, 159.35),
    ("Cleveland Cavaliers", "2027-01-09", 15990, 148.70),
)
NETS_ASSUMPTIONS = [
    '"Last month" means August 2026, by purchase date.',
    "Counts sold tickets only; refunds and comps excluded.",
]
NETS_SQL = """\
SELECT
    e.name AS event,
    e.event_date,
    COUNT(*) AS tickets_sold,
    ROUND(AVG(t.price), 2) AS avg_price,
    ROUND(SUM(t.price), 2) AS gate_revenue
FROM tickets AS t
JOIN orders AS o ON o.order_id = t.order_id
JOIN events AS e ON e.event_id = t.event_id
JOIN teams AS h ON h.team_id = e.home_team_id
WHERE h.name = 'Brooklyn Nets'
  AND t.status = 'sold'
  AND o.ordered_at >= '2026-08-01'
  AND o.ordered_at < '2026-09-01'
GROUP BY e.event_id
ORDER BY e.event_date"""

EMPTY_SQL = """\
SELECT e.name, e.event_date
FROM events AS e
WHERE e.category = 'Boxing'
  AND e.event_date >= '2026-08-01'
  AND e.event_date < '2026-09-01'"""

UNANSWERABLE_ANSWER = (
    "The data holds no weather information. It covers events, tickets, orders, customers "
    "and revenue at Barclays Center, so try a question about one of those."
)
ERROR_MESSAGES = {
    "rate_limited": "The model is rate limited right now. Try again shortly.",
    "missing_api_key": "ANTHROPIC_API_KEY is not set. Add it to .env.",
    "database_missing": "No database found. Create it with: uv run python -m nlq.db.seed",
}


class FakeAgent:
    """`ask(question)` with the real agent's signature and none of its dependencies."""

    def ask(self, question: str) -> AskResult:
        """Pick a canned result from a keyword in the question; default to the chart answer."""
        lowered = question.lower()
        for keywords, build in _CANNED:
            if any(keyword in lowered for keyword in keywords):
                return build(question)
        return _category_chart(question)


def _blocked(question: str) -> AskResult:
    return _result(question, "blocked", answer=BLOCKED_ANSWER, sql="DELETE FROM tickets")


def _unanswerable(question: str) -> AskResult:
    suggestions = [example.question for example in EXAMPLE_QUESTIONS[:SUGGESTION_COUNT]]
    return _result(question, "unanswerable", answer=UNANSWERABLE_ANSWER, suggestions=suggestions)


def _empty(question: str) -> AskResult:
    return _result(
        question,
        "empty",
        sql=EMPTY_SQL,
        assumptions=["Boxing events dated in August 2026."],
        columns=["name", "event_date"],
        suggestions=EMPTY_SUGGESTIONS,
    )


def _error(code: str) -> Callable[[str], AskResult]:
    def build(question: str) -> AskResult:
        error = ErrorInfo(code=code, message=ERROR_MESSAGES[code])
        return _result(question, "error", error=error)

    return build


def _slow(question: str) -> AskResult:
    time.sleep(SLOW_SECONDS)
    return _category_chart(question)


def _nets_table(question: str) -> AskResult:
    rows = [_nets_row(*fixture) for fixture in NETS_FIXTURES]
    total = sum(sold for _, _, sold, _ in NETS_FIXTURES)
    answer = (
        f"Nets home games sold {total:,} tickets in August 2026, all of them for upcoming "
        "2026-27 fixtures, since the Nets play no home games in August."
    )
    return _result(
        question,
        "answered",
        answer=answer,
        sql=NETS_SQL,
        assumptions=NETS_ASSUMPTIONS,
        columns=NETS_COLUMNS,
        rows=rows,
        row_count=len(rows),
        repairs=1,
    )


def _nets_row(opponent: str, event_date: str, sold: int, avg_price: float) -> list[object]:
    return [
        f"Brooklyn Nets vs. {opponent}",
        event_date,
        sold,
        avg_price,
        round(sold * avg_price, 2),
    ]


def _category_chart(question: str) -> AskResult:
    return _result(
        question,
        "answered",
        answer=CATEGORY_ANSWER,
        sql=CATEGORY_SQL,
        assumptions=CATEGORY_ASSUMPTIONS,
        columns=CATEGORY_COLUMNS,
        rows=CATEGORY_ROWS,
        row_count=len(CATEGORY_ROWS),
        chart=ChartSpec(x="category", y="revenue"),
    )


_CANNED: tuple[tuple[tuple[str, ...], Callable[[str], AskResult]], ...] = (
    (("delete", "drop", "update"), _blocked),
    (("weather",), _unanswerable),
    (("nothing",), _empty),
    (("rate limit",), _error("rate_limited")),
    (("no key",), _error("missing_api_key")),
    (("no database",), _error("database_missing")),
    (("slow",), _slow),
    (("nets",), _nets_table),
)


def _result(question: str, status: str, *, repairs: int = 0, **fields: object) -> AskResult:
    """An `AskResult` carrying the fixed trace, so every fake answer looks the same on screen."""
    trace = Trace(
        steps=[Step(name=name, ms=ms) for name, ms in STEP_MS],
        repairs=repairs,
        model=FAKE_MODEL,
        total_ms=TOTAL_MS,
        input_tokens=INPUT_TOKENS,
        output_tokens=OUTPUT_TOKENS,
        cost_usd=cost_usd(FAKE_MODEL, INPUT_TOKENS, OUTPUT_TOKENS),
    )
    return AskResult(status=status, question=question, trace=trace, **fields)
