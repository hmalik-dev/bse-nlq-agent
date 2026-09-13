"""Generate the synthetic ticketing dataset.

Everything here is fabricated. Team, venue and opponent names are real so the
exercise's example questions are answerable; artists, customers, orders and
tickets are invented. The generator is seeded, so the same inputs always give
the same database.

Rows are written per event rather than accumulated, so a full-scale seed holds
one event's orders and tickets in memory at a time instead of five million.

Run with: python -m nlq.db.seed [--scale 0.2]
"""

from __future__ import annotations

import argparse
import itertools
import random
import sqlite3
from collections.abc import Iterator
from dataclasses import dataclass, replace
from datetime import date, timedelta
from pathlib import Path

from nlq import config
from nlq.config import DATABASE_PATH, SCHEMA_PATH

RNG_SEED = 20260911

SEASONS_BACK = 2  # whole calendar years behind the year in progress
FUTURE_WINDOW_DAYS = 120

NBA_HOME_GAMES = 41
NBA_SEASON_START = (10, 21)
NBA_SEASON_END = (4, 12)
NBA_PLAYOFF_START = (4, 18)
NBA_PLAYOFF_END = (6, 20)
NBA_PLAYOFF_HOME_GAMES = (0, 2, 3, 4)  # rounds reached at home, drawn per season

WNBA_HOME_GAMES = 20
WNBA_SEASON_START = (5, 12)
WNBA_SEASON_END = (9, 20)
WNBA_PLAYOFF_START = (9, 24)
WNBA_PLAYOFF_END = (10, 25)
WNBA_PLAYOFF_HOME_GAMES = 2

# Per calendar year. Drawn at the top of each published range so the yearly
# total stays inside the 125-150 band the data spec asserts.
CONCERTS_PER_YEAR = (29, 33)
COMEDY_PER_YEAR = (11, 14)
BOXING_PER_YEAR = (4, 5)
FAMILY_ENGAGEMENTS_PER_YEAR = 3
FAMILY_PERFORMANCES = (7, 9)  # consecutive nights per engagement

CUSTOMER_COUNT = 400_000
MIN_CUSTOMERS = 2_000
CUSTOMER_BATCH = 25_000
FREQUENT_BUYER_RATE = 0.03
FREQUENT_BUYER_SHARE = 0.25  # of single-game orders

REFUND_RATE = 0.03
COMP_RATE = 0.02
SOLD_RATE = 1.0 - REFUND_RATE - COMP_RATE
FEE_RATE = 0.18
SEASON_INFLATION = 0.05
WEEKEND_UPLIFT = 1.08
PRICE_DRAW_SENSITIVITY = 0.5
SELL_THROUGH_DRAW_SENSITIVITY = 0.10
PLAYOFF_DRAW = 1.35

ON_SALE_LEAD_DAYS = 150
PACKAGE_LEAD_DAYS = (30, 120)  # before the season opener
GROUP_SIZES = (1, 2, 3, 4, 6)
GROUP_WEIGHTS = (0.22, 0.46, 0.10, 0.18, 0.04)
PACKAGE_SEAT_SIZES = (1, 2, 3, 4)
PACKAGE_SEAT_WEIGHTS = (0.15, 0.55, 0.10, 0.20)
CHANNELS = ("web", "mobile_app", "box_office", "resale", "group_sales")
CHANNEL_WEIGHTS = (0.44, 0.31, 0.09, 0.11, 0.05)
PACKAGE_CHANNELS = ("web", "box_office")
PACKAGE_CHANNEL_WEIGHTS = (0.7, 0.3)
PROMO_CODES = (None, None, None, None, "SPRING20", "FLASH15", "MEMBER10", "GROUP25")

BARCLAYS_CENTER = (1, "Barclays Center", "Brooklyn", "NY", 19000)
VENUE_ID = BARCLAYS_CENTER[0]

NETS_TEAM_ID = 1
LIBERTY_TEAM_ID = 2
HOME_TEAMS = (
    (NETS_TEAM_ID, "Brooklyn Nets", "NBA", 1),
    (LIBERTY_TEAM_ID, "New York Liberty", "WNBA", 1),
)

# (name, draw multiplier) — bigger names sell more seats at higher prices.
NBA_OPPONENTS = (
    ("Los Angeles Lakers", 1.60),
    ("New York Knicks", 1.55),
    ("Golden State Warriors", 1.50),
    ("Boston Celtics", 1.45),
    ("Philadelphia 76ers", 1.25),
    ("Milwaukee Bucks", 1.20),
    ("Miami Heat", 1.20),
    ("Denver Nuggets", 1.20),
    ("Dallas Mavericks", 1.20),
    ("Oklahoma City Thunder", 1.20),
    ("Phoenix Suns", 1.15),
    ("Cleveland Cavaliers", 1.10),
    ("Chicago Bulls", 1.10),
    ("San Antonio Spurs", 1.10),
    ("LA Clippers", 1.10),
    ("Minnesota Timberwolves", 1.05),
    ("Atlanta Hawks", 1.00),
    ("Toronto Raptors", 1.00),
    ("Indiana Pacers", 1.00),
    ("Houston Rockets", 1.00),
    ("Orlando Magic", 0.95),
    ("Memphis Grizzlies", 0.95),
    ("New Orleans Pelicans", 0.95),
    ("Sacramento Kings", 0.95),
    ("Detroit Pistons", 0.90),
    ("Portland Trail Blazers", 0.90),
    ("Charlotte Hornets", 0.85),
    ("Washington Wizards", 0.85),
    ("Utah Jazz", 0.85),
)

WNBA_OPPONENTS = (
    ("Indiana Fever", 1.50),
    ("Las Vegas Aces", 1.35),
    ("Seattle Storm", 1.15),
    ("Phoenix Mercury", 1.10),
    ("Minnesota Lynx", 1.05),
    ("Chicago Sky", 1.05),
    ("Los Angeles Sparks", 1.05),
    ("Connecticut Sun", 1.00),
    ("Dallas Wings", 1.00),
    ("Golden State Valkyries", 1.00),
    ("Washington Mystics", 0.95),
    ("Atlanta Dream", 0.95),
)

# Fictional acts, so no real performer is implied to have played these dates.
CONCERT_ACTS = (
    ("Neon Harbor", 1.30),
    ("Kaia Monroe", 1.45),
    ("Static Parade", 1.15),
    ("The Velvet Line", 1.00),
    ("Rumble & Vine", 0.95),
    ("Sofia Reign", 1.35),
    ("Bridge & Tunnel Collective", 0.80),
    ("Harbor Lights Session", 0.85),
    ("Marlowe Gray", 1.20),
    ("The Ferry Yard", 0.90),
)
COMEDY_ACTS = (
    ("Danny Ortiz: Third Act", 0.95),
    ("Late Shift Comedy Tour", 1.05),
    ("Priya Raman Live", 1.00),
)
BOXING_ACTS = (
    ("Brooklyn Fight Night", 1.10),
    ("Atlantic Title Bout", 1.00),
)
FAMILY_SHOWS = (
    ("Wonderworld on Ice", 1.00),
    ("Dino Adventure Live", 0.95),
    ("Circus Aurora", 1.05),
)

FIRST_NAMES = (
    "Alex",
    "Maria",
    "Jordan",
    "Priya",
    "Marcus",
    "Nina",
    "Devon",
    "Sofia",
    "Elijah",
    "Grace",
    "Tomas",
    "Aisha",
    "Ryan",
    "Leila",
    "Andre",
    "Chloe",
    "Hassan",
    "Erin",
    "Victor",
    "Dana",
    "Malik",
    "Rosa",
    "Kevin",
    "Yuki",
    "Omar",
    "Beth",
    "Carlos",
    "Ivy",
    "Nathan",
    "Simone",
)
LAST_NAMES = (
    "Alvarez",
    "Bennett",
    "Chen",
    "Diallo",
    "Espinoza",
    "Foster",
    "Greco",
    "Hughes",
    "Ibrahim",
    "Jensen",
    "Kowalski",
    "Lombardi",
    "Mercado",
    "Novak",
    "Okafor",
    "Patel",
    "Quinn",
    "Ramirez",
    "Silva",
    "Thompson",
    "Ueda",
    "Vasquez",
    "Walsh",
    "Xu",
    "Yates",
    "Zimmer",
)
BUYER_CITIES = (
    ("Brooklyn", "NY"),
    ("New York", "NY"),
    ("Queens", "NY"),
    ("Jersey City", "NJ"),
    ("Hoboken", "NJ"),
    ("Uniondale", "NY"),
    ("Garden City", "NY"),
    ("Stamford", "CT"),
    ("Newark", "NJ"),
    ("Yonkers", "NY"),
    ("Philadelphia", "PA"),
    ("Boston", "MA"),
)


@dataclass(frozen=True)
class Tier:
    """A seating tier: what share of the house it is and what it costs.

    `multiplier` is relative to the category's base price, and the shares are
    weighted so a whole house averages out to that base price.
    """

    name: str
    share: float
    multiplier: float
    sections: tuple[str, ...]


LOWER_BOWL_SECTIONS = tuple(str(n) for n in range(101, 129))
UPPER_BOWL_SECTIONS = tuple(str(n) for n in range(201, 232))
CLUB_SECTIONS = tuple(f"C{n}" for n in range(1, 13))
SUITE_SECTIONS = tuple(f"S{n}" for n in range(1, 21))
COURTSIDE_SECTIONS = tuple(f"A{n}" for n in range(1, 9))

# Barclays reconfigures per event, so each configuration has its own manifest.
BASKETBALL_TIERS = (
    Tier("Courtside", 0.01, 7.00, COURTSIDE_SECTIONS),
    Tier("Suite", 0.02, 3.80, SUITE_SECTIONS),
    Tier("Club", 0.08, 1.90, CLUB_SECTIONS),
    Tier("Lower Bowl", 0.34, 1.25, LOWER_BOWL_SECTIONS),
    Tier("Upper Bowl", 0.55, 0.52, UPPER_BOWL_SECTIONS),
)
END_STAGE_TIERS = (
    Tier("General Admission", 0.10, 1.45, ("FLOOR",)),
    Tier("Suite", 0.02, 3.50, SUITE_SECTIONS),
    Tier("Club", 0.08, 1.90, CLUB_SECTIONS),
    Tier("Lower Bowl", 0.35, 1.20, LOWER_BOWL_SECTIONS),
    Tier("Upper Bowl", 0.45, 0.50, UPPER_BOWL_SECTIONS),
)
CURTAINED_TIERS = (
    Tier("Club", 0.10, 2.00, CLUB_SECTIONS),
    Tier("Lower Bowl", 0.50, 1.10, LOWER_BOWL_SECTIONS),
    Tier("Upper Bowl", 0.40, 0.60, UPPER_BOWL_SECTIONS),
)

BASKETBALL_CAPACITY = 17_732
END_STAGE_CAPACITY = 19_000
CURTAINED_CAPACITY = 8_000


@dataclass(frozen=True)
class CategoryProfile:
    """How one kind of event is configured, priced and how well it sells."""

    capacity: int
    tiers: tuple[Tier, ...]
    base_price: float
    sell_through: float


CATEGORIES = {
    "NBA": CategoryProfile(BASKETBALL_CAPACITY, BASKETBALL_TIERS, 163.0, 0.93),
    "WNBA": CategoryProfile(BASKETBALL_CAPACITY, BASKETBALL_TIERS, 76.0, 0.73),
    "Concert": CategoryProfile(END_STAGE_CAPACITY, END_STAGE_TIERS, 124.0, 0.63),
    "Boxing": CategoryProfile(END_STAGE_CAPACITY, END_STAGE_TIERS, 138.0, 0.58),
    "Comedy": CategoryProfile(CURTAINED_CAPACITY, CURTAINED_TIERS, 84.0, 0.81),
    "Family Show": CategoryProfile(CURTAINED_CAPACITY, CURTAINED_TIERS, 58.0, 0.78),
}

# A third of the basketball house sells as season packages. The Liberty share is
# lower because their sell-through is, and what the data spec asserts is the
# package share of *sold* seats.
PACKAGE_HOUSE_SHARE = {"NBA": 0.33, "WNBA": 0.25}


@dataclass(frozen=True)
class Event:
    event_id: int
    name: str
    category: str
    home_team_id: int | None
    away_team_id: int | None
    event_date: date
    season: str | None
    is_playoff: int
    announced_date: date
    draw: float  # demand multiplier, drives both sell-through and price

    @property
    def seating_capacity(self) -> int:
        return CATEGORIES[self.category].capacity

    def row(self) -> tuple[object, ...]:
        return (
            self.event_id,
            VENUE_ID,
            self.name,
            self.category,
            self.home_team_id,
            self.away_team_id,
            self.event_date.isoformat(),
            self.season,
            self.is_playoff,
            self.seating_capacity,
            self.announced_date.isoformat(),
        )


@dataclass(frozen=True)
class PackageHolder:
    """One season-ticket account: the same seats at every regular-season game."""

    order_id: int
    seats: int
    tier: Tier
    section: str


def _team_rows() -> list[tuple[object, ...]]:
    rows: list[tuple[object, ...]] = list(HOME_TEAMS)
    for team_id, (name, _) in enumerate(NBA_OPPONENTS, start=10):
        rows.append((team_id, name, "NBA", 0))
    wnba_start = 10 + len(NBA_OPPONENTS)
    for team_id, (name, _) in enumerate(WNBA_OPPONENTS, start=wnba_start):
        rows.append((team_id, name, "WNBA", 0))
    return rows


NBA_OPPONENT_IDS = {name: 10 + index for index, (name, _) in enumerate(NBA_OPPONENTS)}
WNBA_OPPONENT_IDS = {
    name: 10 + len(NBA_OPPONENTS) + index for index, (name, _) in enumerate(WNBA_OPPONENTS)
}


def _spread_dates(rng: random.Random, start: date, end: date, number: int) -> list[date]:
    """One date per evenly sized bucket, so a season reads as scheduled, not random."""
    span = (end - start).days
    step = span / number
    days: list[int] = []
    previous = -1
    for index in range(number):
        low = max(previous + 1, int(index * step))
        high = max(low, int((index + 1) * step) - 1)
        previous = rng.randint(low, min(high, span))
        days.append(previous)
    return [start + timedelta(days=offset) for offset in days]


def _sport_event(
    category: str,
    home_team_id: int,
    opponent: str,
    draw: float,
    event_date: date,
    season: str,
    is_playoff: int,
) -> Event:
    opponent_ids = NBA_OPPONENT_IDS if category == "NBA" else WNBA_OPPONENT_IDS
    home_name = "Brooklyn Nets" if home_team_id == NETS_TEAM_ID else "New York Liberty"
    label = "Playoffs: " if is_playoff else ""
    return Event(
        event_id=0,  # assigned once the window has been applied
        name=f"{label}{home_name} vs. {opponent}",
        category=category,
        home_team_id=home_team_id,
        away_team_id=opponent_ids[opponent],
        event_date=event_date,
        season=season,
        is_playoff=is_playoff,
        announced_date=event_date - timedelta(days=ON_SALE_LEAD_DAYS),
        draw=draw * (PLAYOFF_DRAW if is_playoff else 1.0),
    )


def _team_games(
    rng: random.Random,
    category: str,
    home_team_id: int,
    season: str,
    opponents: tuple[tuple[str, float], ...],
    schedule: tuple[date, date, int],
    is_playoff: int,
) -> list[Event]:
    """One block of home games — a regular season, or a postseason run."""
    start, end, games = schedule
    if not games:
        return []
    draws = list(opponents)
    rng.shuffle(draws)
    events = []
    for index, event_date in enumerate(_spread_dates(rng, start, end, games)):
        name, draw = draws[index % len(draws)]
        events.append(
            _sport_event(category, home_team_id, name, draw, event_date, season, is_playoff)
        )
    return events


def _nba_season(rng: random.Random, start_year: int) -> list[Event]:
    """One Nets season: 41 regular-season home games, then the playoff run."""
    season = f"{start_year}-{str(start_year + 1)[2:]}"
    regular = (
        date(start_year, *NBA_SEASON_START),
        date(start_year + 1, *NBA_SEASON_END),
        NBA_HOME_GAMES,
    )
    playoffs = (
        date(start_year + 1, *NBA_PLAYOFF_START),
        date(start_year + 1, *NBA_PLAYOFF_END),
        rng.choice(NBA_PLAYOFF_HOME_GAMES),
    )
    args = ("NBA", NETS_TEAM_ID, season, NBA_OPPONENTS)
    return _team_games(rng, *args, regular, is_playoff=0) + _team_games(
        rng, *args, playoffs, is_playoff=1
    )


def _wnba_season(rng: random.Random, year: int) -> list[Event]:
    """One Liberty season, which sits inside a single calendar year."""
    regular = (date(year, *WNBA_SEASON_START), date(year, *WNBA_SEASON_END), WNBA_HOME_GAMES)
    playoffs = (
        date(year, *WNBA_PLAYOFF_START),
        date(year, *WNBA_PLAYOFF_END),
        WNBA_PLAYOFF_HOME_GAMES,
    )
    args = ("WNBA", LIBERTY_TEAM_ID, str(year), WNBA_OPPONENTS)
    return _team_games(rng, *args, regular, is_playoff=0) + _team_games(
        rng, *args, playoffs, is_playoff=1
    )


def _show_event(name: str, category: str, draw: float, event_date: date) -> Event:
    return Event(
        event_id=0,
        name=f"{name} — {event_date:%b %-d, %Y}",  # dated, so two nights read distinctly
        category=category,
        home_team_id=None,
        away_team_id=None,
        event_date=event_date,
        season=None,
        is_playoff=0,
        announced_date=event_date - timedelta(days=ON_SALE_LEAD_DAYS),
        draw=draw,
    )


def _one_off_shows(
    rng: random.Random, year: int, category: str, acts: tuple[tuple[str, float], ...], number: int
) -> list[Event]:
    events = []
    for event_date in _spread_dates(rng, date(year, 1, 1), date(year, 12, 31), number):
        name, draw = rng.choice(acts)
        events.append(_show_event(name, category, draw * rng.uniform(0.85, 1.2), event_date))
    return events


def _family_engagements(rng: random.Random, year: int) -> list[Event]:
    """Family shows sell as a run of consecutive nights, not as one-off dates."""
    starts = _spread_dates(rng, date(year, 1, 20), date(year, 12, 10), FAMILY_ENGAGEMENTS_PER_YEAR)
    events = []
    for start in starts:
        name, draw = rng.choice(FAMILY_SHOWS)
        nightly_draw = draw * rng.uniform(0.85, 1.2)
        for night in range(rng.randint(*FAMILY_PERFORMANCES)):
            events.append(
                _show_event(name, "Family Show", nightly_draw, start + timedelta(days=night))
            )
    return events


def _non_sport_events(rng: random.Random, year: int) -> list[Event]:
    concerts = _one_off_shows(rng, year, "Concert", CONCERT_ACTS, rng.randint(*CONCERTS_PER_YEAR))
    comedy = _one_off_shows(rng, year, "Comedy", COMEDY_ACTS, rng.randint(*COMEDY_PER_YEAR))
    boxing = _one_off_shows(rng, year, "Boxing", BOXING_ACTS, rng.randint(*BOXING_PER_YEAR))
    return concerts + comedy + boxing + _family_engagements(rng, year)


def window_bounds(today: date) -> tuple[date, date]:
    """Whole calendar years behind, plus everything already on sale ahead."""
    return date(today.year - SEASONS_BACK, 1, 1), today + timedelta(days=FUTURE_WINDOW_DAYS)


def _nba_season_start_years(today: date) -> range:
    """Every NBA season with games in the window.

    The first year needs the season before it, for its January-to-April games.
    The last is whichever season has opened by the horizon, not the season in
    progress: from late June the horizon already reaches the autumn opener, and
    those games are on sale.
    """
    _, horizon = window_bounds(today)
    opener = date(horizon.year, *NBA_SEASON_START)
    latest = horizon.year if horizon >= opener else horizon.year - 1
    return range(today.year - SEASONS_BACK - 1, latest + 1)


def _build_events(rng: random.Random, today: date) -> list[Event]:
    """Every event in the window: team home games, then concerts and shows.

    The window is whole calendar years, so a question about "2024" has a full
    year of events behind it rather than the tail of one season.
    """
    window_start, horizon = window_bounds(today)
    events: list[Event] = []
    for start_year in _nba_season_start_years(today):
        events.extend(_nba_season(rng, start_year))
    for year in range(window_start.year, horizon.year + 1):
        events.extend(_wnba_season(rng, year))
        events.extend(_non_sport_events(rng, year))
    inside = sorted(
        (event for event in events if window_start <= event.event_date <= horizon),
        key=lambda event: (event.event_date, event.name),
    )
    return [replace(event, event_id=index) for index, event in enumerate(inside, start=1)]


def _customer_rows(
    rng: random.Random, today: date, total: int, member_count: int
) -> Iterator[list[tuple[object, ...]]]:
    """Customers in batches, so 400k rows never sit in one list.

    The first `member_count` ids are the season-ticket accounts, which is what
    `is_season_member` marks.
    """
    batch: list[tuple[object, ...]] = []
    for customer_id in range(1, total + 1):
        first, last = rng.choice(FIRST_NAMES), rng.choice(LAST_NAMES)
        city, state = rng.choice(BUYER_CITIES)
        created = today - timedelta(days=rng.randint(30, 1500))
        batch.append(
            (
                customer_id,
                f"{first} {last}",
                f"{first.lower()}.{last.lower()}{customer_id}@example.com",
                city,
                state,
                1 if customer_id <= member_count else 0,
                created.isoformat(),
            )
        )
        if len(batch) == CUSTOMER_BATCH:
            yield batch
            batch = []
    if batch:
        yield batch


def _season_key(event: Event) -> tuple[str, str] | None:
    """The team season a package covers, or None for playoffs and for shows."""
    if event.category in PACKAGE_HOUSE_SHARE and not event.is_playoff and event.season:
        return event.category, event.season
    return None


def _package_seat_counts(rng: random.Random, seats_target: int) -> list[int]:
    """Seats per account, drawn until the package allocation is filled."""
    counts: list[int] = []
    held = 0
    while held < seats_target:
        seats = rng.choices(PACKAGE_SEAT_SIZES, PACKAGE_SEAT_WEIGHTS)[0]
        counts.append(seats)
        held += seats
    return counts


def _package_order_timestamp(rng: random.Random, opener: date, today: date) -> str:
    """Packages are bought in the close season, well before the opener."""
    ordered = min(opener - timedelta(days=rng.randint(*PACKAGE_LEAD_DAYS)), today)
    return f"{ordered.isoformat()} {rng.randint(9, 20):02d}:{rng.randint(0, 59):02d}:00"


def _season_openers(events: list[Event]) -> dict[tuple[str, str], date]:
    openers: dict[tuple[str, str], date] = {}
    for event in events:
        key = _season_key(event)
        if key is not None:
            openers[key] = min(openers.get(key, event.event_date), event.event_date)
    return openers


def _account_pools(seat_counts: dict[tuple[str, str], list[int]]) -> tuple[dict[str, int], int]:
    """First customer id of each team's account pool, and how many accounts there are."""
    pool_start: dict[str, int] = {}
    next_id = 1
    for category in PACKAGE_HOUSE_SHARE:
        pool_start[category] = next_id
        sizes = [len(counts) for key, counts in seat_counts.items() if key[0] == category]
        next_id += max(sizes, default=0)
    return pool_start, next_id - 1


def _build_packages(
    rng: random.Random, events: list[Event], today: date, scale: float, order_ids: Iterator[int]
) -> tuple[dict[tuple[str, str], list[PackageHolder]], list[tuple[object, ...]], int]:
    """Season-ticket accounts per team season, plus the one order each places.

    Accounts renew, so each team draws from a fixed pool of customer ids; the
    two pools together are the customers flagged `is_season_member`.
    """
    openers = _season_openers(events)
    seat_counts = {
        key: _package_seat_counts(rng, _package_seats_target(key[0], scale)) for key in openers
    }
    pool_start, member_count = _account_pools(seat_counts)

    holders: dict[tuple[str, str], list[PackageHolder]] = {}
    orders: list[tuple[object, ...]] = []
    for key, counts in seat_counts.items():
        tiers = CATEGORIES[key[0]].tiers
        weights = [tier.share for tier in tiers]
        season_holders = []
        for index, seats in enumerate(counts):
            order_id = next(order_ids)
            tier = rng.choices(tiers, weights)[0]
            season_holders.append(PackageHolder(order_id, seats, tier, rng.choice(tier.sections)))
            orders.append(
                (
                    order_id,
                    pool_start[key[0]] + index,
                    _package_order_timestamp(rng, openers[key], today),
                    rng.choices(PACKAGE_CHANNELS, PACKAGE_CHANNEL_WEIGHTS)[0],
                    None,
                    1,
                )
            )
        holders[key] = season_holders
    return holders, orders, member_count


def _package_seats_target(category: str, scale: float) -> int:
    profile = CATEGORIES[category]
    return max(1, round(profile.capacity * scale * PACKAGE_HOUSE_SHARE[category]))


def _sell_through(event: Event, rng: random.Random) -> float:
    base = CATEGORIES[event.category].sell_through
    base *= 1.0 + SELL_THROUGH_DRAW_SENSITIVITY * (event.draw - 1.0)
    return min(0.995, max(0.30, base + rng.uniform(-0.03, 0.03)))


def _single_game_seats(
    event: Event, today: date, rng: random.Random, scale: float, package_seats: int
) -> int:
    """Seats left for single-game buyers once the season packages are counted.

    Packages are already in hand for a future game, so only the single-game
    seats are still filling, scaled by how far out the event is.
    """
    sold = CATEGORIES[event.category].capacity * scale * _sell_through(event, rng)
    singles = max(0.0, sold - package_seats)
    if event.event_date > today:
        days_out = (event.event_date - today).days
        singles *= min(0.72, max(0.02, 1.0 - days_out / ON_SALE_LEAD_DAYS))
    return max(1, int(singles))


def _ticket_price(tier: Tier, event: Event, today: date, rng: random.Random) -> float:
    years_ago = max(0.0, (today - event.event_date).days / 365.0)
    inflation = (1 - SEASON_INFLATION) ** years_ago
    weekend = WEEKEND_UPLIFT if event.event_date.weekday() >= 4 else 1.0
    draw = 1.0 + PRICE_DRAW_SENSITIVITY * (event.draw - 1.0)
    base = CATEGORIES[event.category].base_price * tier.multiplier
    return round(base * draw * inflation * weekend * rng.uniform(0.88, 1.18), 2)


def _order_timestamp(event: Event, today: date, rng: random.Random) -> str:
    latest = min(event.event_date, today)
    window = max(1, (latest - event.announced_date).days)
    roll = rng.random()
    if roll < 0.30:  # on-sale rush
        offset = rng.randint(0, min(21, window))
    elif roll < 0.72:  # steady middle
        offset = rng.randint(0, window)
    else:  # late buyers
        offset = rng.randint(max(0, window - 14), window)
    ordered = event.announced_date + timedelta(days=offset)
    return f"{ordered.isoformat()} {rng.randint(8, 23):02d}:{rng.randint(0, 59):02d}:00"


def _ticket_status(rng: random.Random) -> str:
    roll = rng.random()
    if roll < REFUND_RATE:
        return "refunded"
    if roll < REFUND_RATE + COMP_RATE:
        return "comp"
    return "sold"


def _ticket_row(
    ticket_id: int,
    order_id: int,
    event: Event,
    tier: Tier,
    section: str,
    price: float,
    status: str,
) -> tuple[object, ...]:
    paid = 0.0 if status == "comp" else price
    return (
        ticket_id,
        order_id,
        event.event_id,
        section,
        tier.name,
        paid,
        round(paid * FEE_RATE, 2),
        status,
    )


def _package_tickets(
    event: Event,
    holders: list[PackageHolder],
    today: date,
    rng: random.Random,
    ticket_ids: Iterator[int],
) -> list[tuple[object, ...]]:
    """One ticket per holder seat. Packages are sold outright — never comped or refunded."""
    rows: list[tuple[object, ...]] = []
    for holder in holders:
        price = _ticket_price(holder.tier, event, today, rng)
        rows.extend(
            _ticket_row(
                next(ticket_ids), holder.order_id, event, holder.tier, holder.section, price, "sold"
            )
            for _ in range(holder.seats)
        )
    return rows


class Buyers:
    """Picks who places an order. A small block of accounts buys far more often."""

    def __init__(self, total: int) -> None:
        self.total = total
        self.frequent_end = max(1, round(total * FREQUENT_BUYER_RATE))

    def pick(self, rng: random.Random) -> int:
        if rng.random() < FREQUENT_BUYER_SHARE:
            return rng.randint(1, self.frequent_end)
        return rng.randint(1, self.total)


def _single_game_rows(
    event: Event,
    seats: int,
    today: date,
    rng: random.Random,
    buyers: Buyers,
    ids: tuple[Iterator[int], Iterator[int]],
) -> tuple[list[tuple[object, ...]], list[tuple[object, ...]]]:
    """Group single-game seats into orders. Refunds and comps sit on top of `seats`."""
    order_ids, ticket_ids = ids
    tiers = CATEGORIES[event.category].tiers
    weights = [tier.share for tier in tiers]
    orders: list[tuple[object, ...]] = []
    tickets: list[tuple[object, ...]] = []
    remaining = round(seats / SOLD_RATE)
    while remaining > 0:
        group = min(remaining, rng.choices(GROUP_SIZES, GROUP_WEIGHTS)[0])
        remaining -= group
        order_id = next(order_ids)
        orders.append(
            (
                order_id,
                buyers.pick(rng),
                _order_timestamp(event, today, rng),
                rng.choices(CHANNELS, CHANNEL_WEIGHTS)[0],
                rng.choice(PROMO_CODES),
                0,
            )
        )
        tier = rng.choices(tiers, weights)[0]
        section = rng.choice(tier.sections)
        price = _ticket_price(tier, event, today, rng)
        tickets.extend(
            _ticket_row(
                next(ticket_ids), order_id, event, tier, section, price, _ticket_status(rng)
            )
            for _ in range(group)
        )
    return orders, tickets


INSERT_ORDER = "INSERT INTO orders VALUES (?, ?, ?, ?, ?, ?)"
INSERT_TICKET = "INSERT INTO tickets VALUES (?, ?, ?, ?, ?, ?, ?, ?)"


@dataclass(frozen=True)
class SalesContext:
    """Everything the per-event sales generator needs but does not own."""

    today: date
    rng: random.Random
    scale: float
    buyers: Buyers
    order_ids: Iterator[int]
    ticket_ids: Iterator[int]


def _write_sales(
    conn: sqlite3.Connection,
    events: list[Event],
    packages: dict[tuple[str, str], list[PackageHolder]],
    sales: SalesContext,
) -> tuple[int, int]:
    """Insert one event's orders and tickets at a time, counting as it goes."""
    ids = (sales.order_ids, sales.ticket_ids)
    order_count = ticket_count = 0
    for event in events:
        key = _season_key(event)
        holders = packages.get(key, []) if key is not None else []
        package_seats = sum(holder.seats for holder in holders)
        seats = _single_game_seats(event, sales.today, sales.rng, sales.scale, package_seats)
        orders, tickets = _single_game_rows(event, seats, sales.today, sales.rng, sales.buyers, ids)
        tickets.extend(_package_tickets(event, holders, sales.today, sales.rng, sales.ticket_ids))
        conn.executemany(INSERT_ORDER, orders)
        conn.executemany(INSERT_TICKET, tickets)
        order_count += len(orders)
        ticket_count += len(tickets)
    return order_count, ticket_count


def seed_database(
    db_path: Path = DATABASE_PATH, *, today: date | None = None, scale: float = 1.0
) -> dict[str, int]:
    """Create `db_path` from scratch and fill it with generated data.

    `today` defaults to `config.today()`, the real date; tests pass one in for
    determinism. `scale` shrinks the seats sold per event and
    the customer base together, so per-customer behavior stays realistic while
    tests run on a fraction of the rows. Row counts are returned for logging.
    """
    as_of = today or config.today()
    rng = random.Random(RNG_SEED)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    db_path.unlink(missing_ok=True)

    events = _build_events(rng, as_of)
    order_ids, ticket_ids = itertools.count(1), itertools.count(1)
    packages, package_orders, member_count = _build_packages(rng, events, as_of, scale, order_ids)
    customer_count = max(MIN_CUSTOMERS, round(CUSTOMER_COUNT * scale), member_count)

    conn = sqlite3.connect(db_path)
    try:
        conn.execute("PRAGMA journal_mode = OFF")
        conn.execute("PRAGMA synchronous = OFF")
        conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        conn.execute("INSERT INTO venues VALUES (?, ?, ?, ?, ?)", BARCLAYS_CENTER)
        team_rows = _team_rows()
        conn.executemany("INSERT INTO teams VALUES (?, ?, ?, ?)", team_rows)
        conn.executemany(
            "INSERT INTO events VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [event.row() for event in events],
        )
        for batch in _customer_rows(rng, as_of, customer_count, member_count):
            conn.executemany("INSERT INTO customers VALUES (?, ?, ?, ?, ?, ?, ?)", batch)
        conn.executemany(INSERT_ORDER, package_orders)
        sales = SalesContext(as_of, rng, scale, Buyers(customer_count), order_ids, ticket_ids)
        order_count, ticket_count = _write_sales(conn, events, packages, sales)
        conn.commit()
    finally:
        conn.close()

    return {
        "venues": 1,
        "teams": len(team_rows),
        "events": len(events),
        "customers": customer_count,
        "orders": order_count + len(package_orders),
        "tickets": ticket_count,
    }


def main(argv: list[str] | None = None) -> None:
    """The command line: `--scale` in, the scale and the row counts out, for the real today."""
    parser = argparse.ArgumentParser(description="Generate the synthetic ticketing database.")
    parser.add_argument(
        "--scale",
        type=float,
        default=1.0,
        help="fraction of the full dataset to generate (default 1.0, about 5 million tickets)",
    )
    args = parser.parse_args(argv)
    if args.scale <= 0:
        parser.error("--scale must be greater than 0")
    counts = seed_database(scale=args.scale)
    print(f"Seeded {DATABASE_PATH} at scale {args.scale:g}")
    for table, number in counts.items():
        print(f"  {table:<10} {number:>9,}")


if __name__ == "__main__":
    main()
