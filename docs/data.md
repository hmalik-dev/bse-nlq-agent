# Data

What the generated database holds, and the ranges `tests/test_seed.py` asserts.
`src/nlq/db/seed.py` builds it; `src/nlq/db/dictionary.yaml` defines its terms.

## Tables

| Table | One row per | Notes |
|---|---|---|
| `venues` | venue | Barclays Center only. Kept so "at Barclays Center" resolves through a join. |
| `teams` | club | The Nets and the Liberty (`is_home_club = 1`) and every visiting opponent |
| `events` | game, concert or show | Category, date, season, playoff flag, `seating_capacity` |
| `customers` | buyer | `is_season_member` marks season-package holders |
| `orders` | purchase | Time, channel, promo code, `is_season_package` |
| `tickets` | seat | Price, fee, status (`sold`, `refunded`, `comp`) |

Categories: NBA, WNBA, Concert, Comedy, Boxing, Family Show.

## Calendar

The last two calendar years, the year in progress, and events on sale up to 120
days out. The data holds **Barclays Center home games only**, because BSE sells
tickets only to home games.

| Per calendar year | Generated | Asserted |
|---|---|---|
| Nets home games | 41 regular + 0, 2, 3 or 4 playoff | ≥ 36 |
| Liberty home games | 20 regular + 2 playoff | exactly 20 + 2 |
| Concerts | 29–33 | 27–33 |
| Family shows | 3 runs × 7–9 nights | 18–27 |
| Comedy | 11–14 | 10–14 |
| Boxing | 4–5 | 3–5 |
| **Total** | | **125–150** |

Season dates are the same every year, close to the real calendars: Nets 21 Oct –
12 Apr, playoffs 18 Apr – 20 Jun; Liberty 12 May – 20 Sep, playoffs 24 Sep – 25 Oct.
Season labels are `YYYY-YY` for the Nets and `YYYY` for the Liberty. "Last season"
is per club: its latest season with no home games left.

## Realism targets

Medians across played events. Sell-through is tickets sold ÷ `seating_capacity`.

| Category | Capacity | Tickets sold | Sell-through | Average price | Gate per event |
|---|---|---|---|---|---|
| NBA (Nets) | 17,732 | 15,500–17,300 | 87–98% | $140–190 | $2.2–3.0M |
| WNBA (Liberty) | 17,732 | 11,500–14,500 | 64–82% | $55–90 | $0.7–1.2M |
| Concert | 19,000 | 10,500–13,500 | 55–71% | $110–150 | $1.2–1.9M |
| Boxing | 19,000 | 9,000–13,000 | 47–69% | $100–180 | $1.0–2.0M |
| Comedy | 8,000 | 5,500–7,500 | 68–94% | $70–95 | $0.4–0.7M |
| Family Show | 8,000 | 5,000–7,500 | 62–94% | $45–70 | $0.25–0.5M |

## Deliberate quirks

These make the questions genuinely ambiguous, which the agent has to resolve.

- **Refunds about 3%, comps about 2%** (price 0), and an **18% fee** in its own
  column. Revenue excludes all three.
- **Purchase date is not event date.** "Sold last month" filters on purchase time.
- **Season packages:** a third of the Nets house and a quarter of the Liberty
  house, bought 30–120 days before opening night, 28–38% of each club's sold
  regular-season tickets. Packages are never refunded or comped.
- **Single-game sales** rush in the first three weeks and spike in the last two.
- **Channels:** web ~44%, app ~31%, resale ~11%, box office ~9%, group ~5%.
- **Customers:** 400,000. 3% of them place a quarter of single-game orders; the
  median buyer places 3 orders and the 90th percentile 6.
- Nothing is bought after its event or after today.

## Scale and size

`--scale` shrinks seats per event and customers together, never the calendar.
Full scale, measured on 2026-09-12: 5,082,400 tickets, 1,717,269 orders, 419
events, 644 MB, 34 s, 52 MB peak memory. At `--scale 0.2`: about a million
tickets, 128 MB, 5 s. The seed is deterministic for a given date.

## Not modelled

Attendance scans (sell-through answers "how full"), dynamic repricing, suites,
secondary-market pricing, private hires and college games. Barclays' "200+ events
a year" counts those, which is why the total above is lower.
