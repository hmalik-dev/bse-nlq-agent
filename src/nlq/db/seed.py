"""Generate the synthetic ticketing dataset.

Everything here is fabricated. Club, venue and opponent names are real so the
exercise's example questions are answerable; artists, customers, orders and
tickets are invented. The generator is seeded, so the same inputs always give
the same database.

Run with: python -m nlq.db.seed
"""

from __future__ import annotations

import random
import sqlite3
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

from nlq import config
from nlq.config import DATABASE_PATH, SCHEMA_PATH

RNG_SEED = 20260911

NBA_HOME_GAMES = 41
NBA_PLAYOFF_HOME_GAMES = 4
WNBA_HOME_GAMES = 20
WNBA_PLAYOFF_HOME_GAMES = 2
SEASONS_BACK = 2  # in addition to the season in progress
FUTURE_WINDOW_DAYS = 120
SPECIAL_EVENTS_PER_YEAR = 22

CUSTOMER_COUNT = 30_000
FREQUENT_BUYER_COUNT = 5_000
FREQUENT_BUYER_SHARE = 0.55

REFUND_RATE = 0.03
COMP_RATE = 0.02
FEE_RATE = 0.18
SEASON_INFLATION = 0.05

ON_SALE_LEAD_DAYS = 150
GROUP_SIZES = (1, 2, 3, 4, 6)
GROUP_WEIGHTS = (0.22, 0.46, 0.10, 0.18, 0.04)
CHANNELS = ("web", "mobile_app", "box_office", "resale", "group_sales")
CHANNEL_WEIGHTS = (0.44, 0.31, 0.09, 0.11, 0.05)
PROMO_CODES = (None, None, None, None, "SPRING20", "FLASH15", "MEMBER10", "GROUP25")

VENUES = (
    (1, "Barclays Center", "Brooklyn", "NY", 19000),
    (2, "Nassau Coliseum", "Uniondale", "NY", 13900),
    (3, "Gowanus Pavilion", "Brooklyn", "NY", 2800),
)

NETS_TEAM_ID = 1
LIBERTY_TEAM_ID = 2
HOME_CLUBS = (
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
SPECIAL_ACTS = (
    ("Neon Harbor", "Concert", 1, 1.30),
    ("Kaia Monroe", "Concert", 1, 1.45),
    ("Static Parade", "Concert", 1, 1.15),
    ("The Velvet Line", "Concert", 2, 1.00),
    ("Rumble & Vine", "Concert", 2, 0.95),
    ("Sofia Reign", "Concert", 1, 1.35),
    ("Bridge & Tunnel Collective", "Concert", 3, 0.80),
    ("Harbor Lights Session", "Concert", 3, 0.75),
    ("Danny Ortiz: Third Act", "Comedy", 3, 0.85),
    ("Late Shift Comedy Tour", "Comedy", 2, 0.90),
    ("Brooklyn Fight Night", "Boxing", 1, 1.10),
    ("Atlantic Title Bout", "Boxing", 2, 1.00),
    ("Wonderworld on Ice", "Family Show", 2, 0.80),
    ("Dino Adventure Live", "Family Show", 2, 0.75),
    ("Circus Aurora", "Family Show", 1, 0.85),
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
    """A seating tier: what share of the house it is and what it costs."""

    name: str
    share: float
    base_price: float
    sections: tuple[str, ...]


ARENA_TIERS = (
    Tier("Courtside", 0.01, 1150.0, tuple(f"A{n}" for n in range(1, 9))),
    Tier("Suite", 0.02, 620.0, tuple(f"S{n}" for n in range(1, 21))),
    Tier("Club", 0.08, 310.0, tuple(f"C{n}" for n in range(1, 13))),
    Tier("Lower Bowl", 0.34, 175.0, tuple(str(n) for n in range(101, 129))),
    Tier("Upper Bowl", 0.55, 72.0, tuple(str(n) for n in range(201, 232))),
)
MIDSIZE_TIERS = (
    Tier("Club", 0.06, 190.0, tuple(f"C{n}" for n in range(1, 9))),
    Tier("Lower Bowl", 0.44, 120.0, tuple(str(n) for n in range(101, 121))),
    Tier("Upper Bowl", 0.50, 58.0, tuple(str(n) for n in range(201, 221))),
)
GA_TIERS = (Tier("General Admission", 1.0, 65.0, ("FLOOR", "BALCONY")),)
VENUE_TIERS = {1: ARENA_TIERS, 2: MIDSIZE_TIERS, 3: GA_TIERS}
VENUE_CAPACITY = {venue_id: capacity for venue_id, _, _, _, capacity in VENUES}


@dataclass(frozen=True)
class Event:
    event_id: int
    venue_id: int
    name: str
    category: str
    home_team_id: int | None
    away_team_id: int | None
    event_date: date
    season: str | None
    is_playoff: int
    announced_date: date
    draw: float  # demand multiplier, drives both sell-through and price

    def row(self) -> tuple[object, ...]:
        return (
            self.event_id,
            self.venue_id,
            self.name,
            self.category,
            self.home_team_id,
            self.away_team_id,
            self.event_date.isoformat(),
            self.season,
            self.is_playoff,
            self.announced_date.isoformat(),
        )


def _team_rows() -> list[tuple[object, ...]]:
    rows: list[tuple[object, ...]] = list(HOME_CLUBS)
    team_id = 10
    for name, _ in NBA_OPPONENTS:
        rows.append((team_id, name, "NBA", 0))
        team_id += 1
    for name, _ in WNBA_OPPONENTS:
        rows.append((team_id, name, "WNBA", 0))
        team_id += 1
    return rows


def _build_opponent_ids() -> tuple[dict[str, int], dict[str, int]]:
    """Map opponent name to team_id, for the NBA and the WNBA."""
    nba: dict[str, int] = {}
    wnba: dict[str, int] = {}
    team_id = 10
    for name, _ in NBA_OPPONENTS:
        nba[name] = team_id
        team_id += 1
    for name, _ in WNBA_OPPONENTS:
        wnba[name] = team_id
        team_id += 1
    return nba, wnba


NBA_OPPONENT_IDS, WNBA_OPPONENT_IDS = _build_opponent_ids()


def _spread_dates(rng: random.Random, start: date, end: date, count: int) -> list[date]:
    """Pick `count` distinct dates between start and end, evenly-ish spread."""
    span = (end - start).days
    candidates = sorted(rng.sample(range(span), min(count, span)))
    return [start + timedelta(days=offset) for offset in candidates]


def _nba_season_start_years(today: date) -> list[int]:
    """NBA seasons run Oct-Apr, so the season in progress started last autumn."""
    current = today.year if today.month >= 9 else today.year - 1
    return [current - back for back in range(SEASONS_BACK, -1, -1)]


def _wnba_seasons(today: date) -> list[int]:
    """WNBA seasons sit inside one calendar year."""
    return list(range(today.year - SEASONS_BACK, today.year + 1))


def _nba_events(rng: random.Random, start_year: int, next_id: int) -> list[Event]:
    """One NBA regular season of home games, plus playoff games for that season."""
    season = f"{start_year}-{str(start_year + 1)[2:]}"
    opponents = list(NBA_OPPONENTS)
    rng.shuffle(opponents)
    dates = _spread_dates(
        rng, date(start_year, 10, 22), date(start_year + 1, 4, 12), NBA_HOME_GAMES
    )
    events = []
    for index, event_date in enumerate(dates):
        name, draw = opponents[index % len(opponents)]
        events.append(
            _sport_event(
                next_id + index, "NBA", NETS_TEAM_ID, name, draw, event_date, season, is_playoff=0
            )
        )
    playoff_dates = _spread_dates(
        rng, date(start_year + 1, 4, 20), date(start_year + 1, 5, 28), NBA_PLAYOFF_HOME_GAMES
    )
    for index, event_date in enumerate(playoff_dates):
        name, draw = opponents[index % len(opponents)]
        events.append(
            _sport_event(
                next_id + NBA_HOME_GAMES + index,
                "NBA",
                NETS_TEAM_ID,
                name,
                draw * 1.35,
                event_date,
                season,
                is_playoff=1,
            )
        )
    return events


def _wnba_events(rng: random.Random, year: int, next_id: int) -> list[Event]:
    season = str(year)
    opponents = list(WNBA_OPPONENTS)
    rng.shuffle(opponents)
    dates = _spread_dates(rng, date(year, 5, 15), date(year, 9, 8), WNBA_HOME_GAMES)
    events = []
    for index, event_date in enumerate(dates):
        name, draw = opponents[index % len(opponents)]
        events.append(
            _sport_event(
                next_id + index,
                "WNBA",
                LIBERTY_TEAM_ID,
                name,
                draw,
                event_date,
                season,
                is_playoff=0,
            )
        )
    playoff_dates = _spread_dates(
        rng, date(year, 9, 14), date(year, 10, 8), WNBA_PLAYOFF_HOME_GAMES
    )
    for index, event_date in enumerate(playoff_dates):
        name, draw = opponents[index % len(opponents)]
        events.append(
            _sport_event(
                next_id + WNBA_HOME_GAMES + index,
                "WNBA",
                LIBERTY_TEAM_ID,
                name,
                draw * 1.4,
                event_date,
                season,
                is_playoff=1,
            )
        )
    return events


def _sport_event(
    event_id: int,
    category: str,
    home_team_id: int,
    opponent: str,
    draw: float,
    event_date: date,
    season: str,
    is_playoff: int,
) -> Event:
    opponent_ids = NBA_OPPONENT_IDS if category == "NBA" else WNBA_OPPONENT_IDS
    away_id = opponent_ids[opponent]
    home_name = "Brooklyn Nets" if home_team_id == NETS_TEAM_ID else "New York Liberty"
    label = "Playoffs: " if is_playoff else ""
    return Event(
        event_id=event_id,
        venue_id=1,
        name=f"{label}{home_name} vs. {opponent}",
        category=category,
        home_team_id=home_team_id,
        away_team_id=away_id,
        event_date=event_date,
        season=season,
        is_playoff=is_playoff,
        announced_date=event_date - timedelta(days=ON_SALE_LEAD_DAYS),
        draw=draw,
    )


def _special_events(rng: random.Random, start: date, end: date, next_id: int) -> list[Event]:
    """Concerts, comedy, boxing and family shows across the whole window."""
    years = max(1, (end - start).days // 365)
    count = SPECIAL_EVENTS_PER_YEAR * years
    dates = _spread_dates(rng, start, end, count)
    events = []
    for index, event_date in enumerate(dates):
        name, category, venue_id, draw = SPECIAL_ACTS[index % len(SPECIAL_ACTS)]
        events.append(
            Event(
                event_id=next_id + index,
                venue_id=venue_id,
                name=f"{name} — {event_date:%b %-d, %Y}",  # dated, so two nights read distinctly
                category=category,
                home_team_id=None,
                away_team_id=None,
                event_date=event_date,
                season=None,
                is_playoff=0,
                announced_date=event_date - timedelta(days=ON_SALE_LEAD_DAYS),
                draw=draw * rng.uniform(0.85, 1.2),
            )
        )
    return events


def _build_events(rng: random.Random, today: date) -> list[Event]:
    """Every event in the window: club home games, then concerts and shows.

    The window is whole calendar years, so a question about "2024" has a full
    year of events behind it rather than the tail of one season.
    """
    window_start = date(today.year - SEASONS_BACK, 1, 1)
    horizon = today + timedelta(days=FUTURE_WINDOW_DAYS)
    events: list[Event] = []
    for start_year in _nba_season_start_years(today):
        events.extend(_nba_events(rng, start_year, next_id=len(events) + 1))
    for year in _wnba_seasons(today):
        events.extend(_wnba_events(rng, year, next_id=len(events) + 1))
    events.extend(_special_events(rng, window_start, horizon, next_id=len(events) + 1))
    return [event for event in events if window_start <= event.event_date <= horizon]


def _build_customers(rng: random.Random, today: date) -> list[tuple[object, ...]]:
    rows = []
    for customer_id in range(1, CUSTOMER_COUNT + 1):
        first = rng.choice(FIRST_NAMES)
        last = rng.choice(LAST_NAMES)
        city, state = rng.choice(BUYER_CITIES)
        created = today - timedelta(days=rng.randint(30, 1500))
        rows.append(
            (
                customer_id,
                f"{first} {last}",
                f"{first.lower()}.{last.lower()}{customer_id}@example.com",
                city,
                state,
                1 if rng.random() < 0.08 else 0,
                created.isoformat(),
            )
        )
    return rows


def _sell_through(event: Event, rng: random.Random) -> float:
    base = 0.62 + 0.22 * (event.draw - 1.0) + rng.uniform(-0.06, 0.06)
    if event.is_playoff:
        base += 0.12
    return min(0.99, max(0.42, base))


def _tickets_for_event(event: Event, today: date, rng: random.Random, scale: float) -> int:
    capacity = VENUE_CAPACITY[event.venue_id]
    seats = capacity * _sell_through(event, rng)
    if event.event_date > today:
        days_out = (event.event_date - today).days
        progress = min(0.72, max(0.06, 1.0 - days_out / ON_SALE_LEAD_DAYS))
        seats *= progress
    return max(1, int(seats * scale))


def _ticket_price(tier: Tier, event: Event, today: date, rng: random.Random) -> float:
    years_ago = (today - event.event_date).days / 365.0
    inflation = (1 - SEASON_INFLATION) ** max(0.0, years_ago)
    weekend = 1.08 if event.event_date.weekday() >= 4 else 1.0
    price = tier.base_price * event.draw * inflation * weekend * rng.uniform(0.88, 1.18)
    return round(price, 2)


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


def _build_sales(
    rng: random.Random, events: list[Event], today: date, scale: float
) -> tuple[list[tuple[object, ...]], list[tuple[object, ...]]]:
    """Group seats into orders, one order per buyer per event."""
    orders: list[tuple[object, ...]] = []
    tickets: list[tuple[object, ...]] = []
    order_id = 0
    ticket_id = 0
    for event in events:
        tiers = VENUE_TIERS[event.venue_id]
        weights = [tier.share for tier in tiers]
        seats_left = _tickets_for_event(event, today, rng, scale)
        while seats_left > 0:
            group = min(seats_left, rng.choices(GROUP_SIZES, GROUP_WEIGHTS)[0])
            seats_left -= group
            order_id += 1
            orders.append(
                (
                    order_id,
                    _pick_customer(rng),
                    _order_timestamp(event, today, rng),
                    rng.choices(CHANNELS, CHANNEL_WEIGHTS)[0],
                    rng.choice(PROMO_CODES),
                )
            )
            tier = rng.choices(tiers, weights)[0]
            price = _ticket_price(tier, event, today, rng)
            for _ in range(group):
                ticket_id += 1
                status = _ticket_status(rng)
                paid = 0.0 if status == "comp" else price
                tickets.append(
                    (
                        ticket_id,
                        order_id,
                        event.event_id,
                        rng.choice(tier.sections),
                        tier.name,
                        paid,
                        round(paid * FEE_RATE, 2),
                        status,
                    )
                )
    return orders, tickets


def _pick_customer(rng: random.Random) -> int:
    if rng.random() < FREQUENT_BUYER_SHARE:
        return rng.randint(1, FREQUENT_BUYER_COUNT)
    return rng.randint(1, CUSTOMER_COUNT)


def seed_database(
    db_path: Path = DATABASE_PATH, *, today: date | None = None, scale: float = 1.0
) -> dict[str, int]:
    """Create `db_path` from scratch and fill it with generated data.

    `today` defaults to `config.today()`, so NLQ_TODAY pins the seed, the agent
    and the evaluation to one date. `scale` shrinks attendance per event; tests
    use a small value to keep the fixture fast. Row counts are returned for
    logging.
    """
    as_of = today or config.today()
    rng = random.Random(RNG_SEED)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    db_path.unlink(missing_ok=True)

    events = _build_events(rng, as_of)
    customers = _build_customers(rng, as_of)
    orders, tickets = _build_sales(rng, events, as_of, scale)

    conn = sqlite3.connect(db_path)
    try:
        conn.execute("PRAGMA journal_mode = OFF")
        conn.execute("PRAGMA synchronous = OFF")
        conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        conn.executemany("INSERT INTO venues VALUES (?, ?, ?, ?, ?)", VENUES)
        conn.executemany("INSERT INTO teams VALUES (?, ?, ?, ?)", _team_rows())
        conn.executemany(
            "INSERT INTO events VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [event.row() for event in events],
        )
        conn.executemany("INSERT INTO customers VALUES (?, ?, ?, ?, ?, ?, ?)", customers)
        conn.executemany("INSERT INTO orders VALUES (?, ?, ?, ?, ?)", orders)
        conn.executemany("INSERT INTO tickets VALUES (?, ?, ?, ?, ?, ?, ?, ?)", tickets)
        conn.commit()
    finally:
        conn.close()

    return {
        "venues": len(VENUES),
        "teams": len(_team_rows()),
        "events": len(events),
        "customers": len(customers),
        "orders": len(orders),
        "tickets": len(tickets),
    }


if __name__ == "__main__":
    counts = seed_database()
    print(f"Seeded {DATABASE_PATH}")
    for table, count in counts.items():
        print(f"  {table:<10} {count:>9,}")
