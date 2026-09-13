-- Synthetic ticketing schema for Barclays Center, the Brooklyn Nets and the
-- New York Liberty. One row per seat sold keeps "how many tickets" a plain
-- COUNT for the agent.

CREATE TABLE venues (
    venue_id   INTEGER PRIMARY KEY,
    name       TEXT    NOT NULL,
    city       TEXT    NOT NULL,
    state      TEXT    NOT NULL,
    capacity   INTEGER NOT NULL  -- largest full-house configuration
);

CREATE TABLE teams (
    team_id      INTEGER PRIMARY KEY,
    name         TEXT    NOT NULL,
    league       TEXT    NOT NULL CHECK (league IN ('NBA', 'WNBA')),
    is_home_team INTEGER NOT NULL DEFAULT 0  -- 1 for the teams this operator owns
);

CREATE TABLE events (
    event_id         INTEGER PRIMARY KEY,
    venue_id         INTEGER NOT NULL REFERENCES venues(venue_id),
    name             TEXT    NOT NULL,
    category         TEXT    NOT NULL CHECK (
                         category IN ('NBA', 'WNBA', 'Concert', 'Comedy', 'Boxing', 'Family Show')),
    home_team_id     INTEGER REFERENCES teams(team_id),  -- NULL for non-sport events
    away_team_id     INTEGER REFERENCES teams(team_id),  -- NULL for non-sport events
    event_date       TEXT    NOT NULL,  -- ISO date, venue local time
    season           TEXT,              -- '2025-26' for NBA, '2026' for WNBA, NULL otherwise
    is_playoff       INTEGER NOT NULL DEFAULT 0,
    seating_capacity INTEGER NOT NULL,  -- seats this event's house was configured for
    announced_date   TEXT    NOT NULL   -- date tickets first went on sale
);

CREATE TABLE customers (
    customer_id      INTEGER PRIMARY KEY,
    full_name        TEXT    NOT NULL,
    email            TEXT    NOT NULL,
    city             TEXT    NOT NULL,
    state            TEXT    NOT NULL,
    is_season_member INTEGER NOT NULL DEFAULT 0,
    created_at       TEXT    NOT NULL  -- ISO date the account was opened
);

CREATE TABLE orders (
    order_id          INTEGER PRIMARY KEY,
    customer_id       INTEGER NOT NULL REFERENCES customers(customer_id),
    ordered_at        TEXT    NOT NULL,  -- ISO timestamp the purchase was made
    channel           TEXT    NOT NULL CHECK (
                          channel IN ('web', 'mobile_app', 'box_office', 'resale', 'group_sales')),
    promo_code        TEXT,              -- NULL when no promotion was applied
    is_season_package INTEGER NOT NULL DEFAULT 0  -- 1 for a pre-season package order
);

CREATE TABLE tickets (
    ticket_id INTEGER PRIMARY KEY,
    order_id  INTEGER NOT NULL REFERENCES orders(order_id),
    event_id  INTEGER NOT NULL REFERENCES events(event_id),
    section   TEXT    NOT NULL,
    seat_tier TEXT    NOT NULL CHECK (seat_tier IN (
                  'Courtside', 'Suite', 'Club', 'Lower Bowl', 'Upper Bowl', 'General Admission')),
    price     REAL    NOT NULL,  -- face value paid, excludes fee; 0 for comps
    fee       REAL    NOT NULL,  -- service fee charged on top of price
    status    TEXT    NOT NULL CHECK (status IN ('sold', 'refunded', 'comp'))
);

CREATE INDEX idx_events_date      ON events(event_date);
CREATE INDEX idx_events_venue     ON events(venue_id);
CREATE INDEX idx_events_away_team ON events(away_team_id);
CREATE INDEX idx_events_category  ON events(category, event_date);
CREATE INDEX idx_orders_time      ON orders(ordered_at);
CREATE INDEX idx_orders_customer  ON orders(customer_id);
CREATE INDEX idx_tickets_event    ON tickets(event_id);
CREATE INDEX idx_tickets_order    ON tickets(order_id);
CREATE INDEX idx_tickets_status   ON tickets(event_id, status);
