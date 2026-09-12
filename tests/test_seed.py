"""The generated database has to satisfy the rules the prompt tells the model about."""

from __future__ import annotations

import sqlite3
from datetime import date
from pathlib import Path

import pytest

from nlq.db.seed import seed_database

TODAY = date(2026, 9, 11)
SCALE = 0.01


@pytest.fixture(scope="module")
def db(tmp_path_factory: pytest.TempPathFactory) -> sqlite3.Connection:
    path = tmp_path_factory.mktemp("data") / "tickets.db"
    seed_database(path, today=TODAY, scale=SCALE)
    conn = sqlite3.connect(path)
    yield conn
    conn.close()


def _scalar(conn: sqlite3.Connection, sql: str) -> float | int:
    row = conn.execute(sql).fetchone()
    assert row is not None
    return row[0]


def test_every_table_has_rows(db: sqlite3.Connection) -> None:
    for table in ("venues", "teams", "events", "customers", "orders", "tickets"):
        assert _scalar(db, f"SELECT COUNT(*) FROM {table}") > 0, f"{table} is empty"


def test_no_orphan_rows(db: sqlite3.Connection) -> None:
    orphan_tickets = _scalar(
        db,
        """
        SELECT COUNT(*) FROM tickets t
        LEFT JOIN orders o ON o.order_id = t.order_id
        LEFT JOIN events e ON e.event_id = t.event_id
        WHERE o.order_id IS NULL OR e.event_id IS NULL
    """,
    )
    orphan_orders = _scalar(
        db,
        """
        SELECT COUNT(*) FROM orders o
        LEFT JOIN customers c ON c.customer_id = o.customer_id
        WHERE c.customer_id IS NULL
    """,
    )
    assert orphan_tickets == 0
    assert orphan_orders == 0


def test_sport_events_have_both_teams_and_others_have_none(db: sqlite3.Connection) -> None:
    bad_sport = _scalar(
        db,
        """
        SELECT COUNT(*) FROM events
        WHERE category IN ('NBA', 'WNBA')
          AND (home_team_id IS NULL OR away_team_id IS NULL)
    """,
    )
    bad_other = _scalar(
        db,
        """
        SELECT COUNT(*) FROM events
        WHERE category NOT IN ('NBA', 'WNBA')
          AND (home_team_id IS NOT NULL OR away_team_id IS NOT NULL)
    """,
    )
    assert bad_sport == 0
    assert bad_other == 0


def test_home_games_belong_to_the_operator_clubs(db: sqlite3.Connection) -> None:
    foreign_home = _scalar(
        db,
        """
        SELECT COUNT(*) FROM events e
        JOIN teams t ON t.team_id = e.home_team_id
        WHERE t.is_home_club = 0
    """,
    )
    assert foreign_home == 0


def test_comps_are_free_and_sold_tickets_are_not(db: sqlite3.Connection) -> None:
    assert _scalar(db, "SELECT COUNT(*) FROM tickets WHERE status = 'comp' AND price <> 0") == 0
    assert _scalar(db, "SELECT COUNT(*) FROM tickets WHERE status = 'sold' AND price <= 0") == 0


def test_nothing_is_bought_after_the_event_or_in_the_future(db: sqlite3.Connection) -> None:
    late_orders = _scalar(
        db,
        f"""
        SELECT COUNT(*) FROM orders o
        JOIN tickets t ON t.order_id = o.order_id
        JOIN events e ON e.event_id = t.event_id
        WHERE DATE(o.ordered_at) > e.event_date OR DATE(o.ordered_at) > '{TODAY.isoformat()}'
    """,
    )
    assert late_orders == 0


def test_window_covers_past_and_upcoming_events(db: sqlite3.Connection) -> None:
    past = _scalar(db, f"SELECT COUNT(*) FROM events WHERE event_date < '{TODAY.isoformat()}'")
    upcoming = _scalar(db, f"SELECT COUNT(*) FROM events WHERE event_date > '{TODAY.isoformat()}'")
    assert past > 0
    assert upcoming > 0


def test_each_recent_calendar_year_has_club_games_and_shows(db: sqlite3.Connection) -> None:
    """A question about a whole year, such as 2024, needs a whole year of events."""
    for year in (TODAY.year - 2, TODAY.year - 1, TODAY.year):
        categories = {
            row[0]
            for row in db.execute(
                "SELECT DISTINCT category FROM events WHERE substr(event_date, 1, 4) = ?",
                (str(year),),
            )
        }
        assert {"NBA", "WNBA"} <= categories, f"{year} is missing club home games"
        assert categories - {"NBA", "WNBA"}, f"{year} is missing concerts and shows"


def test_all_categories_are_represented(db: sqlite3.Connection) -> None:
    categories = {row[0] for row in db.execute("SELECT DISTINCT category FROM events")}
    assert categories == {"NBA", "WNBA", "Concert", "Comedy", "Boxing", "Family Show"}


def test_seed_honours_nlq_today(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The seed and the agent must agree on "today", so NLQ_TODAY pins both."""
    monkeypatch.setenv("NLQ_TODAY", "2025-03-01")
    path = tmp_path / "pinned.db"
    seed_database(path, scale=SCALE)
    conn = sqlite3.connect(path)
    try:
        latest_order = _scalar(conn, "SELECT MAX(DATE(ordered_at)) FROM orders")
        latest_event = _scalar(conn, "SELECT MAX(event_date) FROM events")
    finally:
        conn.close()
    assert latest_order <= "2025-03-01"
    assert latest_event <= "2025-06-29"  # today plus the 120-day on-sale horizon


def test_seed_is_deterministic(tmp_path: Path) -> None:
    fingerprints = []
    for name in ("first.db", "second.db"):
        path = tmp_path / name
        seed_database(path, today=TODAY, scale=SCALE)
        conn = sqlite3.connect(path)
        try:
            fingerprints.append(
                conn.execute("SELECT COUNT(*), ROUND(SUM(price), 2) FROM tickets").fetchone()
            )
        finally:
            conn.close()
    assert fingerprints[0] == fingerprints[1]
