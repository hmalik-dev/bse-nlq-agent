# Data specification

What the generated database has to look like for it to pass as an accurate mock of
BSE's ticketing operation, and how that is enforced. `src/nlq/db/seed.py` implements
this; the tests in `tests/test_seed.py` assert it.

The rule of thumb behind every number here: a BSE reviewer knows their own business.
If a Nets game shows 12,000 tickets sold, they spot it before they read any code.
So the figures below are checked against published real-world numbers, and the tests
assert ranges rather than the README asserting good intentions.

## Scope

Barclays Center only. Two clubs: the Brooklyn Nets (NBA) and the New York Liberty
(WNBA). Six event categories: NBA, WNBA, Concert, Comedy, Boxing, Family Show.

`venues` stays in the schema as a one-row table. A real ticketing system has one,
and "at Barclays Center" should still resolve through a join rather than vanishing
into a constant.

## Seating capacity lives on the event

Barclays reconfigures per event, and a real ticketing manifest records the house
that was actually sold. `events.seating_capacity` carries it:

| Configuration | Capacity | Used by |
|---|---|---|
| Basketball | 17,732 | NBA, WNBA |
| End-stage concert | ~19,000 | Concert, Boxing |
| Curtained house | ~8,000 | Comedy, Family Show |

This also makes sell-through a question the agent can answer, which is one of the
more interesting things a ticketing analyst actually asks.

## Calendar

Whole calendar years: the last two plus the year in progress, and events on sale up
to 120 days out. Because NBA seasons straddle the new year, the window also picks up
the January-to-April home games of the season *before* it starts — without those,
the first calendar year in range shows 16 Nets home games instead of 41.

| Per year | Count | Notes |
|---|---|---|
| Nets home games | 41 regular + up to 4 playoff | 2 playoff rounds at home in a good year |
| Liberty home games | 20 regular + 2 playoff | |
| Concerts | ~30 | |
| Family shows | ~21 | 3 engagements × 6–9 performances, the way they really sell |
| Comedy | ~12 | curtained house |
| Boxing | ~4 | |
| **Total** | **~150–170** | |

Barclays markets "200+ events a year". That number includes private hires, college
games and other events this dataset does not model. Worth knowing if a reviewer asks.

## Per-category targets

Medians across played events. A test asserts each range.

| Category | Tickets sold | Sell-through | Average price | Gate per event |
|---|---|---|---|---|
| NBA (Nets) | 15,500–17,300 | 88–97% | $140–190 | $2.2–3.0M |
| WNBA (Liberty) | 11,500–14,500 | 65–85% | $55–90 | $0.7–1.2M |
| Concert | 10,500–13,500 | 80–92% | $110–150 | $1.2–1.9M |
| Boxing | 9,000–13,000 | 65–85% | $100–180 | $1.0–2.0M |
| Comedy | 5,500–7,500 | 70–90% | $70–95 | $0.4–0.7M |
| Family Show | 5,000–7,500 | 60–80% | $45–70 | $0.25–0.5M |

Price drivers: opponent draw, playoff status, weekend, and a mild year-on-year
increase. Upcoming events are partially sold, scaled by how far out they are.

## How tickets get bought

- **Season tickets.** About a third of Nets and Liberty seats sell as a single
  pre-season order covering every home game, placed before the season opener. This
  is the biggest single thing that makes the purchase-date distribution look real,
  and it is what makes "how many tickets did we sell last month" an interesting
  question rather than a flat random spread.
- **Single-game sales** follow an on-sale curve: a rush in the first three weeks,
  a steady middle, and a late spike in the final fortnight.
- **Channels:** web ~44%, mobile app ~31%, resale ~11%, box office ~9%,
  group sales ~5%.
- **Refunds ~3%, comps ~2%** (priced at zero), **fees 18%** on top of face value.
- Nothing is ever bought after its event, or after today.

## Customers

About 400,000. Most appear once or twice; season members and resellers appear
often. The first pass had 30,000 buyers holding 1.1M orders — 36 purchases each,
which no ticketing database looks like.

## Expected size

About 5M ticket rows, 2M orders, ~650MB on disk, roughly 40 seconds to seed. The
file is generated locally and seeded at container start, so it costs disk rather
than deploy weight, and aggregates still return in under a second.

The seed is deterministic: the same date produces the same database, so evaluation
runs are reproducible. Tests generate a fractional-scale database to stay fast.

## Deliberately not modelled

Worth being able to say out loud, because each one is a judgement call rather than
an oversight:

- **Attendance and scan data.** Tickets sold is not the same as people through the
  gate. Modelling both would be more realistic and would double the ambiguity with
  no benefit to the exercise, so "how full was the arena" is answered by
  sell-through, and the dictionary says so.
- **Dynamic repricing.** A ticket's price is fixed at purchase. Real pricing moves
  daily.
- **Premium and suite contracts.** Suites sell on multi-year deals, not per event.
- **Secondary market economics.** Resale is a channel here, not a marketplace with
  its own price discovery.
- **Private hires, college games, G League.** Out of the modelled calendar.
