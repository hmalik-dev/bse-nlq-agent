"""Teaches the model the database: the system prompt and the worked examples.

Everything the model knows about the schema comes from three files in this
package: `schema.sql`, `dictionary.yaml` and `examples.yaml`. Nothing here
touches the database or the network.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from pathlib import Path

import yaml

from nlq.agent.models import SqlPlan
from nlq.config import DICTIONARY_PATH, PROJECT_ROOT, SCHEMA_PATH
from nlq.db.seed import window_bounds

EXAMPLES_PATH = Path(__file__).resolve().parent / "examples.yaml"
GOLDEN_PATH = PROJECT_ROOT / "tests" / "golden" / "sql_prompt.txt"
GOLDEN_TODAY = date(2026, 9, 11)

CATEGORIES = ("NBA", "WNBA", "Concert", "Comedy", "Boxing", "Family Show")
CHANNELS = ("web", "mobile_app", "box_office", "resale", "group_sales")
STATUSES = ("sold", "refunded", "comp")
SEAT_TIERS = ("Courtside", "Suite", "Club", "Lower Bowl", "Upper Bowl", "General Admission")
HOME_CLUBS = ("Brooklyn Nets", "New York Liberty")

ROLE_AND_RULES = """\
# Role

You translate a business user's question about ticket sales into one SQLite
query, or decline it. Rules:

- Write exactly one read query (a single SELECT). Never write, alter or delete.
- Use only the tables and columns in the schema below. Never invent a column.
- Resolve ambiguity yourself, pick the most reasonable reading, and state each
  choice as a short assumption. There is no follow-up conversation.
- When "sold" or "bought" wording is ambiguous, filter on orders.ordered_at
  (when the purchase happened) rather than events.event_date, and say so.
- A question about one most, least, highest or lowest thing returns that one
  row (LIMIT 1). Return a ranked list only when the question asks for several,
  and cap it at 10 rows unless the question gives a number.
- Decline a question the data cannot answer, and decline any request to
  change data."""

JOIN_PATHS = """\
# How the tables join

- tickets -> orders: tickets.order_id = orders.order_id. Who bought a seat, when
  it was bought, and through which channel.
- orders -> customers: orders.customer_id = customers.customer_id.
- tickets -> events: tickets.event_id = events.event_id. What a seat was for.
- events -> teams: events.home_team_id = teams.team_id for the home club, and
  events.away_team_id = teams.team_id for the opponent. Join teams twice, with
  two aliases, when a question needs both.
- events -> venues: events.venue_id = venues.venue_id.

A customer reaches an event only through tickets: customers -> orders ->
tickets -> events."""

DIALECT_NOTES = """\
# SQLite notes

- Dates are ISO text: event_date is 'YYYY-MM-DD' and ordered_at is
  'YYYY-MM-DD HH:MM:SS'. Compare them as text, or use strftime() and date().
- There is no DATE_TRUNC. Use date(x, 'start of month') or strftime('%Y', x).
- Window functions and common table expressions are available.
- Never call date('now'); today's date is supplied below."""

OUTPUT_CONTRACT = """\
# Output

Return a SqlPlan:

- answerable: true when one read query answers the question, false otherwise.
- sql: the query when answerable, otherwise null.
- assumptions: up to three short sentences stating how ambiguity was resolved.
- decline_reason: when not answerable, one plain sentence saying why.
- decline_category: "out_of_scope" when the data cannot answer the question;
  "destructive" when the request would delete, change or add data. A
  destructive request is always declined, never written."""


@dataclass(frozen=True)
class Example:
    """One worked question and the plan the model should have produced."""

    question: str
    plan: SqlPlan


@dataclass(frozen=True)
class PromptContext:
    """Everything the SQL writer sends besides the question."""

    system: str
    examples: tuple[Example, ...]


@lru_cache(maxsize=8)
def build_context(today: date) -> PromptContext:
    """Assemble the system prompt for `today` and load the worked examples."""
    dictionary = yaml.safe_load(DICTIONARY_PATH.read_text(encoding="utf-8"))
    sections = (
        ROLE_AND_RULES,
        _schema_section(),
        JOIN_PATHS,
        _dictionary_section(dictionary),
        _known_values_section(today),
        DIALECT_NOTES,
        _today_section(today),
        OUTPUT_CONTRACT,
    )
    return PromptContext(system="\n\n".join(sections) + "\n", examples=load_examples())


def load_examples(path: Path = EXAMPLES_PATH) -> tuple[Example, ...]:
    """Read the worked examples, validating each plan against `SqlPlan`."""
    entries = yaml.safe_load(path.read_text(encoding="utf-8"))
    return tuple(
        Example(question=entry["question"], plan=SqlPlan.model_validate(_plan_fields(entry)))
        for entry in entries
    )


def _plan_fields(entry: dict) -> dict:
    return {key: value for key, value in entry.items() if key != "question"}


def _schema_section() -> str:
    ddl = SCHEMA_PATH.read_text(encoding="utf-8").rstrip()
    return f"# Schema\n\n```sql\n{ddl}\n```"


def _dictionary_section(dictionary: dict) -> str:
    lines = ["# Business rules", "", dictionary["dataset"].strip(), ""]
    lines.extend(f"- {rule.strip()}" for rule in dictionary["business_rules"])
    lines.extend(["", "# Tables and columns"])
    for table, spec in dictionary["tables"].items():
        lines.extend(["", f"## {table}: {spec['description'].strip()}"])
        lines.extend(f"- {column}: {text.strip()}" for column, text in spec["columns"].items())
    return "\n".join(lines)


def _known_values_section(today: date) -> str:
    first_event, last_event = window_bounds(today)
    return "\n".join(
        [
            "# Known values",
            "",
            f"- events.category: {_quoted(CATEGORIES)}.",
            f"- orders.channel: {_quoted(CHANNELS)}.",
            f"- tickets.status: {_quoted(STATUSES)}.",
            f"- tickets.seat_tier: {_quoted(SEAT_TIERS)}.",
            f"- Home clubs, by exact teams.name: {_quoted(HOME_CLUBS)}. The Nets play"
            " in the NBA and the Liberty in the WNBA.",
            "- Opponents are teams rows with is_home_club = 0. Match a partial name with"
            " LIKE, e.g. name LIKE '%Celtics%'.",
            "- events.season reads '2025-26' for an NBA season and '2026' for a WNBA"
            " season; it is NULL for non-sport events.",
            f"- The data covers events from {first_event.isoformat()} to"
            f" {last_event.isoformat()}. Events after today are on sale, not played.",
        ]
    )


def _quoted(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


def _today_section(today: date) -> str:
    return (
        "# Today\n\n"
        f'Today is {today.isoformat()}. Resolve relative wording such as "last month",'
        ' "this year" or "last season" against this date.'
    )


def write_golden(path: Path = GOLDEN_PATH) -> None:
    """Snapshot the prompt for the fixed golden date, so a change is a visible diff."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(build_context(GOLDEN_TODAY).system, encoding="utf-8")


if __name__ == "__main__":
    if sys.argv[1:] == ["--write-golden"]:
        write_golden()
        print(f"Wrote {GOLDEN_PATH}")
    else:
        print(build_context(GOLDEN_TODAY).system)
