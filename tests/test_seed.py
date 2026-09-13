"""The generated database has to satisfy the rules the prompt tells the model about.

Ranges come from `docs/data.md`. They are asserted here rather than described
there, so the data cannot drift back to something a BSE reviewer would not accept.
"""

from __future__ import annotations

import sqlite3
import statistics
from datetime import date, timedelta
from pathlib import Path

import pytest
import yaml

from nlq.config import DICTIONARY_PATH
from nlq.db import seed
from nlq.db.seed import seed_database, window_bounds

TODAY = date(2026, 9, 12)
SCALE = 0.02
WINDOW_START, HORIZON = window_bounds(TODAY)

# Calendar years wholly inside the window, so their per-year counts are complete.
FULL_YEARS = (2024, 2025, 2026)

# (category, tickets sold, sell-through %, average price, gate $)
# Sell-through is tickets sold / seating_capacity, so each band is the
# tickets-sold band over that category's capacity.
REALISM = (
    ("NBA", (15_500, 17_300), (87, 98), (140, 190), (2.2e6, 3.0e6)),
    ("WNBA", (11_500, 14_500), (64, 82), (55, 90), (0.7e6, 1.2e6)),
    ("Concert", (10_500, 13_500), (55, 71), (110, 150), (1.2e6, 1.9e6)),
    ("Boxing", (9_000, 13_000), (47, 69), (100, 180), (1.0e6, 2.0e6)),
    ("Comedy", (5_500, 7_500), (68, 94), (70, 95), (0.4e6, 0.7e6)),
    ("Family Show", (5_000, 7_500), (62, 94), (45, 70), (0.25e6, 0.5e6)),
)


@pytest.fixture(scope="module")
def db(tmp_path_factory: pytest.TempPathFactory) -> sqlite3.Connection:
    path = tmp_path_factory.mktemp("data") / "tickets.db"
    seed_database(path, today=TODAY, scale=SCALE)
    conn = sqlite3.connect(path)
    yield conn
    conn.close()


def _scalar(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> float | int:
    row = conn.execute(sql, params).fetchone()
    assert row is not None
    return row[0]


def _counts_by(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> dict[str, int]:
    return {str(key): value for key, value in conn.execute(sql, params)}


def test_every_table_has_rows(db: sqlite3.Connection) -> None:
    for table in ("venues", "teams", "events", "customers", "orders", "tickets"):
        assert _scalar(db, f"SELECT COUNT(*) FROM {table}") > 0, f"{table} is empty"


def test_barclays_center_is_the_only_venue(db: sqlite3.Connection) -> None:
    assert db.execute("SELECT * FROM venues").fetchall() == [
        (1, "Barclays Center", "Brooklyn", "NY", 19000)
    ]
    assert _scalar(db, "SELECT COUNT(*) FROM events WHERE venue_id <> 1") == 0


def test_seating_capacity_is_set_per_category(db: sqlite3.Connection) -> None:
    """Barclays reconfigures per event, so the manifest is on the event, not the venue."""
    expected = {"NBA": 17732, "WNBA": 17732, "Concert": 19000, "Boxing": 19000}
    expected |= {"Comedy": 8000, "Family Show": 8000}
    actual = {
        category: (low, high)
        for category, low, high in db.execute(
            "SELECT category, MIN(seating_capacity), MAX(seating_capacity) FROM events GROUP BY 1"
        )
    }
    assert actual == {category: (seats, seats) for category, seats in expected.items()}


def test_the_joins_the_agent_writes_are_indexed(db: sqlite3.Connection) -> None:
    """Three-table joins and per-customer aggregates run on 5M rows in production."""
    indexed = {
        row[0]
        for row in db.execute("SELECT sql FROM sqlite_master WHERE type = 'index' AND sql NOT NULL")
    }
    for columns in (
        "orders(customer_id)",
        "events(away_team_id)",
        "events(category, event_date)",
        "tickets(event_id, status)",
        "tickets(event_id)",
        "orders(ordered_at)",
        "events(event_date)",
    ):
        assert any(statement.endswith(f"ON {columns}") for statement in indexed), columns


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
    assert _scalar(db, "SELECT COUNT(*) FROM tickets WHERE status = 'comp' AND fee <> 0") == 0
    assert _scalar(db, "SELECT COUNT(*) FROM tickets WHERE status = 'sold' AND price <= 0") == 0


def test_nothing_is_bought_after_the_event_or_in_the_future(db: sqlite3.Connection) -> None:
    late_orders = _scalar(
        db,
        """
        SELECT COUNT(*) FROM orders o
        JOIN tickets t ON t.order_id = o.order_id
        JOIN events e ON e.event_id = t.event_id
        WHERE DATE(o.ordered_at) > e.event_date OR DATE(o.ordered_at) > ?
    """,
        (TODAY.isoformat(),),
    )
    assert late_orders == 0


def test_no_event_falls_outside_the_window(db: sqlite3.Connection) -> None:
    outside = _scalar(
        db,
        "SELECT COUNT(*) FROM events WHERE event_date < ? OR event_date > ?",
        (WINDOW_START.isoformat(), HORIZON.isoformat()),
    )
    assert outside == 0
    assert _scalar(db, "SELECT COUNT(*) FROM events WHERE event_date < ?", (TODAY.isoformat(),)) > 0
    assert _scalar(db, "SELECT COUNT(*) FROM events WHERE event_date > ?", (TODAY.isoformat(),)) > 0


def test_every_nba_season_in_the_window_is_a_full_41_game_schedule(db: sqlite3.Connection) -> None:
    """Seasons clipped by the window edge are skipped; the rest must be complete."""
    rows = db.execute(
        """
        SELECT season,
               SUM(1 - is_playoff), SUM(is_playoff),
               MIN(CASE WHEN is_playoff = 0 THEN event_date END),
               MAX(CASE WHEN is_playoff = 0 THEN event_date END)
        FROM events WHERE category = 'NBA' GROUP BY season
    """
    ).fetchall()
    complete = [row for row in rows if _season_fits_the_window(row[0])]
    assert len(complete) >= 2, "the window should hold at least two whole NBA seasons"
    for season, regular, playoff, first, last in complete:
        opens, closes = _nba_season_bounds(season)
        assert regular == 41, f"{season} has {regular} regular-season home games"
        assert playoff in (0, 2, 3, 4), f"{season} has {playoff} playoff home games"
        assert opens.isoformat() <= first <= last <= closes.isoformat(), season


def _nba_season_bounds(season: str) -> tuple[date, date]:
    """21 October to 12 April of the season labelled '2025-26'."""
    start_year = int(season[:4])
    return date(start_year, 10, 21), date(start_year + 1, 4, 12)


def _season_fits_the_window(season: str) -> bool:
    opens, closes = _nba_season_bounds(season)
    return WINDOW_START <= opens and closes <= HORIZON


def test_nba_playoff_games_sit_between_18_april_and_20_june(db: sqlite3.Connection) -> None:
    out_of_range = _scalar(
        db,
        """
        SELECT COUNT(*) FROM events
        WHERE category = 'NBA' AND is_playoff = 1
          AND (substr(event_date, 6) < '04-18' OR substr(event_date, 6) > '06-20')
    """,
    )
    assert out_of_range == 0


def test_each_calendar_year_has_a_full_nets_home_slate(db: sqlite3.Connection) -> None:
    """A calendar year straddles two seasons plus a playoff run, so it holds about 41.

    The current year only reaches 36 because the 120-day horizon runs past
    21 October; the fixture passes today as 2026-09-12, which it does.
    """
    per_year = _counts_by(
        db,
        "SELECT substr(event_date, 1, 4), COUNT(*) FROM events WHERE category = 'NBA' GROUP BY 1",
    )
    for year in FULL_YEARS:
        assert per_year.get(str(year), 0) >= 36, f"{year} has too few Nets home games"


def test_each_calendar_year_has_a_full_liberty_home_slate(db: sqlite3.Connection) -> None:
    """Liberty seasons sit inside one calendar year, so every year in range is complete."""
    for year in FULL_YEARS:
        assert date(year, *(10, 25)) <= HORIZON, f"{year} postseason is outside the window"
        counts = db.execute(
            """
            SELECT SUM(1 - is_playoff), SUM(is_playoff) FROM events
            WHERE category = 'WNBA' AND substr(event_date, 1, 4) = ?
        """,
            (str(year),),
        ).fetchone()
        assert counts == (20, 2), f"{year} Liberty slate is {counts}"


# (club, season, is_playoff): first and last allowed date, from docs/data.md.
SEASON_WINDOWS = (
    ("NBA", "2025-26", 0, "2025-10-21", "2026-04-12"),
    ("NBA", "2025-26", 1, "2026-04-18", "2026-06-20"),
    ("WNBA", "2026", 0, "2026-05-12", "2026-09-20"),
    ("WNBA", "2026", 1, "2026-09-24", "2026-10-25"),
)


@pytest.mark.parametrize(("category", "season", "is_playoff", "opens", "closes"), SEASON_WINDOWS)
def test_club_games_fall_inside_the_real_league_calendar(
    db: sqlite3.Connection, category: str, season: str, is_playoff: int, opens: str, closes: str
) -> None:
    first, last = db.execute(
        """
        SELECT MIN(event_date), MAX(event_date) FROM events
        WHERE category = ? AND season = ? AND is_playoff = ?
    """,
        (category, season, is_playoff),
    ).fetchone()
    assert first is not None, f"{category} {season} has no games"
    assert opens <= first <= last <= closes, (first, last)


def test_the_liberty_season_is_still_being_played_on_12_september(db: sqlite3.Connection) -> None:
    still_to_play = _scalar(
        db,
        "SELECT COUNT(*) FROM events WHERE category = 'WNBA' AND season = '2026'"
        " AND is_playoff = 0 AND event_date > ?",
        (TODAY.isoformat(),),
    )
    assert still_to_play >= 1


@pytest.mark.parametrize(
    ("category", "low", "high"),
    [("Concert", 27, 33), ("Comedy", 10, 14), ("Boxing", 3, 5), ("Family Show", 18, 27)],
)
def test_non_sport_events_per_year(
    db: sqlite3.Connection, category: str, low: int, high: int
) -> None:
    for year in FULL_YEARS:
        count = _scalar(
            db,
            "SELECT COUNT(*) FROM events WHERE category = ? AND substr(event_date, 1, 4) = ?",
            (category, str(year)),
        )
        assert low <= count <= high, f"{year} has {count} {category} events"


def test_a_full_year_holds_between_125_and_150_events(db: sqlite3.Connection) -> None:
    per_year = _counts_by(db, "SELECT substr(event_date, 1, 4), COUNT(*) FROM events GROUP BY 1")
    for year in FULL_YEARS:
        assert 125 <= per_year[str(year)] <= 150, f"{year} has {per_year[str(year)]} events"


def test_family_shows_run_as_engagements_of_consecutive_nights(db: sqlite3.Connection) -> None:
    """Family shows book a venue for a run of nights; each performance is its own row."""
    for year in FULL_YEARS:
        runs: dict[str, list[date]] = {}
        for (name,) in db.execute(
            """
            SELECT name FROM events
            WHERE category = 'Family Show' AND substr(event_date, 1, 4) = ?
            ORDER BY event_date
        """,
            (str(year),),
        ):
            show, _, dated = name.partition(" — ")
            runs.setdefault(show, []).append(
                date(*(int(part) for part in _parse_display_date(dated)))
            )
        engagements = [length for dates in runs.values() for length in _consecutive_runs(dates)]
        assert len(engagements) == 3, f"{year} has {len(engagements)} family engagements"
        assert all(6 <= length <= 9 for length in engagements), f"{year}: {engagements}"


def _parse_display_date(dated: str) -> tuple[str, str, str]:
    month, day_year = dated.split(" ", 1)
    day, year = day_year.split(", ")
    months = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()
    return year, str(months.index(month) + 1), day


def _consecutive_runs(dates: list[date]) -> list[int]:
    lengths = []
    run = 1
    for previous, current in zip(dates, dates[1:], strict=False):
        if current - previous == timedelta(days=1):
            run += 1
        else:
            lengths.append(run)
            run = 1
    lengths.append(run)
    return lengths


def test_all_categories_are_represented(db: sqlite3.Connection) -> None:
    categories = {row[0] for row in db.execute("SELECT DISTINCT category FROM events")}
    assert categories == {"NBA", "WNBA", "Concert", "Comedy", "Boxing", "Family Show"}


def test_customer_base_scales_with_the_dataset(db: sqlite3.Connection) -> None:
    assert _scalar(db, "SELECT COUNT(*) FROM customers") == round(400_000 * SCALE)


def test_season_members_are_exactly_the_package_holders(db: sqlite3.Connection) -> None:
    """`is_season_member` has to mean something the data can answer for."""
    members = _scalar(db, "SELECT COUNT(*) FROM customers WHERE is_season_member = 1")
    holders = _scalar(
        db, "SELECT COUNT(DISTINCT customer_id) FROM orders WHERE is_season_package = 1"
    )
    assert members == holders > 0
    strays = _scalar(
        db,
        """
        SELECT COUNT(*) FROM orders o JOIN customers c ON c.customer_id = o.customer_id
        WHERE o.is_season_package = 1 AND c.is_season_member = 0
    """,
    )
    assert strays == 0


@pytest.mark.parametrize("category", ["NBA", "WNBA"])
def test_season_packages_carry_about_a_third_of_the_house(
    db: sqlite3.Connection, category: str
) -> None:
    """Measured on played games: a future game's packages are in while singles still fill."""
    share = _scalar(
        db,
        """
        SELECT SUM(o.is_season_package) * 1.0 / COUNT(*)
        FROM tickets t
        JOIN orders o ON o.order_id = t.order_id
        JOIN events e ON e.event_id = t.event_id
        WHERE e.category = ? AND e.is_playoff = 0 AND t.status = 'sold' AND e.event_date < ?
    """,
        (category, TODAY.isoformat()),
    )
    assert 0.28 <= share <= 0.38, f"{category} package share is {share:.1%}"


def test_package_orders_are_placed_before_their_season_opens(db: sqlite3.Connection) -> None:
    late = _scalar(
        db,
        """
        SELECT COUNT(*) FROM orders o
        JOIN (SELECT t.order_id, MIN(e.event_date) AS opener
              FROM tickets t JOIN events e ON e.event_id = t.event_id
              GROUP BY t.order_id) run ON run.order_id = o.order_id
        WHERE o.is_season_package = 1 AND DATE(o.ordered_at) >= run.opener
    """,
    )
    assert late == 0


def test_each_package_holds_its_seats_at_every_regular_season_game(db: sqlite3.Connection) -> None:
    regular_games = {
        (category, season): games
        for category, season, games in db.execute(
            """
            SELECT category, season, COUNT(*) FROM events
            WHERE is_playoff = 0 AND season IS NOT NULL GROUP BY category, season
        """
        )
    }
    rows = db.execute(
        """
        SELECT o.order_id, e.category, e.season, COUNT(*), COUNT(DISTINCT t.event_id),
               MAX(e.is_playoff)
        FROM orders o
        JOIN tickets t ON t.order_id = o.order_id
        JOIN events e ON e.event_id = t.event_id
        WHERE o.is_season_package = 1
        GROUP BY o.order_id
    """
    ).fetchall()
    assert rows
    for order_id, category, season, tickets, games, playoff in rows:
        assert playoff == 0, f"order {order_id} covers a playoff game"
        assert games == regular_games[(category, season)], f"order {order_id} misses games"
        seats, remainder = divmod(tickets, games)
        assert remainder == 0 and 1 <= seats <= 4, f"order {order_id} holds {tickets} over {games}"


def test_most_buyers_order_once_or_twice(db: sqlite3.Connection) -> None:
    """A ticketing database is a long tail of one-off buyers, not 36 orders each."""
    counts = sorted(
        row[0]
        for row in db.execute(
            "SELECT COUNT(*) FROM orders WHERE is_season_package = 0 GROUP BY customer_id"
        )
    )
    assert statistics.median(counts) <= 3
    assert counts[int(len(counts) * 0.9)] <= 7


@pytest.mark.parametrize(("category", "sold", "sell_through", "price", "gate"), REALISM)
def test_played_events_land_on_their_realism_targets(
    db: sqlite3.Connection,
    category: str,
    sold: tuple[int, int],
    sell_through: tuple[int, int],
    price: tuple[int, int],
    gate: tuple[float, float],
) -> None:
    """Medians over played events, rescaled to full size. Counts scale; prices do not."""
    rows = db.execute(
        """
        SELECT COUNT(*), AVG(t.price), SUM(t.price), e.seating_capacity
        FROM events e JOIN tickets t ON t.event_id = e.event_id
        WHERE e.category = ? AND e.event_date < ? AND t.status = 'sold'
        GROUP BY e.event_id
    """,
        (category, TODAY.isoformat()),
    ).fetchall()
    assert len(rows) >= 10, f"only {len(rows)} played {category} events to measure"
    measured = {
        "tickets sold": (statistics.median(row[0] for row in rows) / SCALE, sold),
        # Read from the stored seating_capacity, not a constant, so this also
        # catches an event whose capacity was written wrong.
        "sell-through": (
            statistics.median(row[0] / row[3] for row in rows) / SCALE * 100,
            sell_through,
        ),
        "average price": (statistics.median(row[1] for row in rows), price),
        "gate": (statistics.median(row[2] for row in rows) / SCALE, gate),
    }
    for label, (value, (low, high)) in measured.items():
        assert low <= value <= high, f"{category} {label} is {value:,.0f}, wanted {low:,}-{high:,}"


def test_dictionary_documents_every_table_and_column(db: sqlite3.Connection) -> None:
    """The dictionary is injected into the prompt, so a column it misses is invisible."""
    dictionary = yaml.safe_load(DICTIONARY_PATH.read_text(encoding="utf-8"))
    tables = {
        row[0]
        for row in db.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        if not row[0].startswith("sqlite_")
    }
    assert set(dictionary["tables"]) == tables
    for table in sorted(tables):
        columns = {row[1] for row in db.execute(f"PRAGMA table_info({table})")}
        assert set(dictionary["tables"][table]["columns"]) == columns, table


def test_an_upcoming_season_on_sale_in_the_close_season_is_generated(tmp_path: Path) -> None:
    """From late June the 120-day horizon already reaches the autumn opener.

    Bounding the last NBA season by "the season in progress" instead of by the
    horizon left June-to-August seeds with no Nets games on sale at all.
    """
    close_season = date(2026, 7, 1)
    path = tmp_path / "close-season.db"
    seed_database(path, today=close_season, scale=SCALE)
    conn = sqlite3.connect(path)
    try:
        upcoming = _scalar(
            conn,
            "SELECT COUNT(*) FROM events WHERE category = 'NBA' AND event_date > ?",
            (close_season.isoformat(),),
        )
        season = _scalar(
            conn,
            "SELECT MAX(season) FROM events WHERE category = 'NBA' AND event_date > ?",
            (close_season.isoformat(),),
        )
    finally:
        conn.close()
    assert upcoming > 0, "no Nets games on sale in the close season"
    assert season == "2026-27"


def test_a_tiny_scale_still_seeds_a_usable_customer_base(tmp_path: Path) -> None:
    """The floor keeps every season-ticket account inside the customer table."""
    path = tmp_path / "tiny.db"
    seed_database(path, today=TODAY, scale=0.001)
    conn = sqlite3.connect(path)
    try:
        customers = _scalar(conn, "SELECT COUNT(*) FROM customers")
        members = _scalar(conn, "SELECT COUNT(*) FROM customers WHERE is_season_member = 1")
        holders = _scalar(
            conn, "SELECT COUNT(DISTINCT customer_id) FROM orders WHERE is_season_package = 1"
        )
        orphans = _scalar(
            conn,
            """
            SELECT COUNT(*) FROM orders o
            LEFT JOIN customers c ON c.customer_id = o.customer_id
            WHERE c.customer_id IS NULL
        """,
        )
    finally:
        conn.close()
    assert customers == 2_000, "the minimum customer base did not apply"
    assert members == holders > 0
    assert orphans == 0


def test_seed_is_deterministic(tmp_path: Path) -> None:
    """Two machines seeding the same date must produce the same database."""
    fingerprints = []
    for name in ("first.db", "second.db"):
        path = tmp_path / name
        seed_database(path, today=TODAY, scale=SCALE)
        conn = sqlite3.connect(path)
        try:
            fingerprints.append(
                (
                    conn.execute(
                        "SELECT COUNT(*), ROUND(SUM(price), 2), SUM(order_id) FROM tickets"
                    ).fetchone(),
                    _scalar(conn, "SELECT COUNT(*) FROM events"),
                    _scalar(conn, "SELECT COUNT(*) FROM customers"),
                )
            )
        finally:
            conn.close()
    assert fingerprints[0] == fingerprints[1]


def _record_seed(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, object]]:
    """Swap the generator for a recorder, so the command line is tested without a seed."""
    calls: list[dict[str, object]] = []

    def fake_seed(**kwargs: object) -> dict[str, int]:
        calls.append(kwargs)
        return {"venues": 1, "tickets": 1234}

    monkeypatch.setattr(seed, "seed_database", fake_seed)
    return calls


def test_the_command_line_passes_scale_through_and_prints_the_scale(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    calls = _record_seed(monkeypatch)

    seed.main(["--scale", "0.2"])

    assert calls == [{"scale": 0.2}]
    out = capsys.readouterr().out
    assert "at scale 0.2" in out
    assert "tickets" in out and "1,234" in out


def test_the_command_line_defaults_to_full_scale_for_the_real_today(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _record_seed(monkeypatch)
    seed.main([])
    assert calls == [{"scale": 1.0}]


@pytest.mark.parametrize("argv", [["--scale", "0"], ["--scale", "-1"], ["--today", "2026-09-12"]])
def test_the_command_line_rejects_a_bad_scale_or_a_today_override(
    monkeypatch: pytest.MonkeyPatch, argv: list[str]
) -> None:
    calls = _record_seed(monkeypatch)
    with pytest.raises(SystemExit):
        seed.main(argv)
    assert calls == []
