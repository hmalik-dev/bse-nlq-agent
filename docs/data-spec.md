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
| End-stage concert | 19,000 | Concert, Boxing |
| Curtained house | 8,000 | Comedy, Family Show |

Exact figures, not jittered ones, so sell-through is reproducible and the tests are
arithmetic rather than approximate. This also makes sell-through a question the
agent can answer, which is one of the more interesting things a ticketing analyst
actually asks.

## Calendar

Whole calendar years: the last two plus the year in progress, and events on sale up
to 120 days out. Because NBA seasons straddle the new year, the window also picks up
the January-to-April home games of the season *before* it starts — without those,
the first calendar year in range shows 16 Nets home games instead of 41. At the
other end, which NBA seasons are generated is decided by the horizon rather than by
the season in progress: from late June the 120-day horizon already reaches the
autumn opener, and those games are on sale.

The right-hand column is the band the tests assert; the generator draws from the
narrower range in brackets, because at the bottom of every asserted band the yearly
total comes to 121, below the 125 the same table asserts.

| Per year | Generated | Asserted |
|---|---|---|
| Nets home games | 41 regular + 0, 2, 3 or 4 playoff | ≥ 36 per calendar year |
| Liberty home games | 20 regular + 2 playoff | exactly 20 + 2 |
| Concerts | 29-33 | 27-33 |
| Family shows | 3 engagements × 7-9 nights (21-27 rows) | 18-27 rows |
| Comedy | 11-14 | 10-14 |
| Boxing | 4-5 | 3-5 |
| **Total** | | **125-150** |

Nets home games run 22 Oct - 12 Apr, then 18 Apr - 30 May for the playoffs; Liberty
15 May - 8 Sep, then 14 Sep - 8 Oct. A calendar year is not a season: it straddles
two NBA regular seasons plus a playoff run, which is why the Nets figure is asserted
per calendar year rather than per season, and why the yearly total sits above the
41 + 22 a single pair of seasons would give.

Barclays markets "200+ events a year". That number includes private hires, college
games and other events this dataset does not model, which is why the total above is
lower. Worth knowing if a reviewer asks.

## Per-category targets

Medians across played events. A test asserts each range.

| Category | Tickets sold | Sell-through | Average price | Gate per event |
|---|---|---|---|---|
| NBA (Nets) | 15,500–17,300 | 87–98% | $140–190 | $2.2–3.0M |
| WNBA (Liberty) | 11,500–14,500 | 64–82% | $55–90 | $0.7–1.2M |
| Concert | 10,500–13,500 | 55–71% | $110–150 | $1.2–1.9M |
| Boxing | 9,000–13,000 | 47–69% | $100–180 | $1.0–2.0M |
| Comedy | 5,500–7,500 | 68–94% | $70–95 | $0.4–0.7M |
| Family Show | 5,000–7,500 | 62–94% | $45–70 | $0.25–0.5M |

Sell-through is tickets sold ÷ `seating_capacity`, so each band above is the
tickets-sold band divided by that category's capacity, and the two columns rise and
fall together rather than constraining the data independently. The test reads
`seating_capacity` back from each event row rather than from the generator's
constants, so it still catches an event written with the wrong house. An earlier
draft of this
table quoted 80–92% for concerts, which cannot hold: 80% of a 19,000 end-stage
house is 15,200 tickets, well above what an arena concert actually sells. The
tickets-sold column is the one a reviewer recognises, so it won and the
sell-through column was recomputed from it.

Price drivers: a per-category base price and a tier multiplier table at the top of
`seed.py`, opponent draw, playoff ×1.35 draw, weekend ×1.08, and 5% yearly
inflation. Tier shares are weighted so a whole house averages out to the category's
base price. Upcoming events are partially sold, scaled by how far out they are.

## How tickets get bought

- **Season packages.** A third of the Nets house and a quarter of the Liberty house
  sells as `is_season_package = 1` orders: one pre-season purchase, 30 to 120 days
  before the opener, holding 1–4 seats in one tier and section at every
  regular-season home game (playoffs are sold separately). That is 28–38% of sold
  regular-season tickets for each club, and it is the biggest single thing that
  makes the purchase-date distribution look real — it is what makes "how many
  tickets did we sell last month" an interesting question rather than a flat random
  spread. `customers.is_season_member` marks exactly these accounts.
- **Single-game sales** follow an on-sale curve: a rush in the first three weeks,
  a steady middle, and a late spike in the final fortnight.
- **Channels:** web ~44%, mobile app ~31%, resale ~11%, box office ~9%,
  group sales ~5%.
- **Refunds ~3%, comps ~2%** (priced at zero), **fees 18%** on top of face value.
  Package tickets are sold outright and are never refunded or comped.
- Nothing is ever bought after its event, or after today.

## Customers

400,000, scaled with the dataset. 3% of them place 25% of the single-game orders;
everyone else is drawn uniformly, so the median buyer places 3 orders and the 90th
percentile places 6. The first pass had 30,000 buyers holding 1.1M orders — 36
purchases each, which no ticketing database looks like.

`scale` shrinks the seats sold per event and the customer base together, so
per-customer behaviour stays realistic in the test fixture. The calendar never
scales, because the per-year counts above are asserted at fixture scale.

## Expected size

Measured on 2026-09-12, `/usr/bin/time -l uv run python -m nlq.db.seed`:

| | |
|---|---|
| Tickets | 5,082,400 |
| Orders | 1,717,269 |
| Customers | 400,000 |
| Events | 419 |
| Wall clock | 34s |
| Peak RSS | 52 MB |
| On disk | 644 MB |

Rows are inserted per event rather than accumulated, which is what keeps peak
memory at 52 MB; building the whole dataset in lists first needed 834 MB for 2.6M
tickets. The file is generated locally and seeded at container start, so it costs
disk rather than deploy weight, and aggregates still return in under a second.

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
