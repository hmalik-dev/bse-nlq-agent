# Design brief

The source of truth for the UI: brand assets, screens, states and tokens. The
Claude Design prompt at the bottom is what produced the mockups — keep the two in
sync when either changes.

## Product

**BSE Insights** — an internal tool where anyone at Brooklyn Sports &
Entertainment asks a question about ticket sales in plain English and gets an
answer, the assumptions behind it, and the SQL that produced it.

Header lockup: the BSE wordmark, a hairline divider, then the product word
"Insights". A small `Demo · synthetic data` badge sits in the footer.

## Example questions

The six starter chips on the ask screen, in order. `GET /api/examples` serves this
list; the badge column is the club mark shown on the chip.

| # | Question | Badge |
|---|---|---|
| 1 | How many tickets did we sell for Nets home games last month? | Nets |
| 2 | Top 5 event categories by total revenue | |
| 3 | Which 2024 events had the highest average ticket price? | |
| 4 | Which Liberty home games sold the most tickets this season? | Liberty |
| 5 | How much revenue did refunds cost us last season? | |
| 6 | Compare web and box office sales for concerts | |

Chip 4 replaces the canvas's "Which opponent drives the biggest gate?", which put
the Liberty mark on a question that had nothing to do with the Liberty. It keeps the
canvas's position and styling.

## The canvas is a style reference

Everything in `design-plan/BSE Insights.dc.html` that looks like data is
illustrative: event names, categories, numbers, column names and SQL text. The
running app always shows the real dataset, and design parity is judged on layout,
tokens, typography and component presence, never on data content.

## Brand assets

Committed at `web/public/brand/`. Measured, not assumed:

| File | Contents | Dimensions | Use |
|---|---|---|---|
| `bse.svg` | Single white fill `#fff` | 672 × 254 | Header lockup, ~28px tall. **Dark backgrounds only** — it is invisible on light. |
| `nets.svg` | White paths `#fff` | 215 × 215 (square) | 24px badge on Nets rows, chips and team filters |
| `liberty.svg` | Seafoam `#87D5B5` + near-black `#100F0D` detail | 200 × 170 | 24px badge for Liberty. Place on a panel (`#16161A`) or lighter, so the dark detail still reads. |
| `barclays-center.svg` | White + cyan `#00AEEF` + three gradients | 567 × 222 | Footer venue line, ~20px tall |

The white BSE and Nets marks are the reason the interface is dark. That is not a
style preference; it is what the assets require.

## Tokens

Taken from the assets themselves, so the UI and the logos share one palette.

- **Canvas** `#0B0B0D` · **panels** `#16161A` · **raised** `#1E1E23` · **hairline
  borders** `#26262B`
- **Text** `#FFFFFF` primary · `#A1A1AA` secondary · `#71717A` tertiary
- **Primary accent** Barclays cyan `#00AEEF` — primary button (with black text),
  active tab, focus ring, links
- **Secondary accent** Liberty seafoam `#87D5B5` — chart bars, positive badges,
  "sold" status
- **Semantic** warning `#FBBF24` · error and blocked `#F87171`
- **Type** tight grotesk for display and headings, Inter for body, a monospace
  face for SQL and every number. Numbers are tabular and right-aligned.
- **Shape** 12px radius on cards, 8px on chips, inputs and buttons; one soft
  shadow level; no gradients in the UI itself (the Barclays logo owns the only
  gradient on the page).
- **Motion** 150–200ms fades. Pipeline steps tick in one after another. Nothing
  bounces.
- **Grid** 1200px max content width inside a 1440 viewport, 24px gutters.

## The response the UI renders

`POST /api/ask` with `{"question": "..."}` returns:

```jsonc
{
  "status": "answered" | "empty" | "unanswerable" | "blocked" | "error",
  "question": "How many tickets were sold for Nets home games last month?",
  "answer": "About 26,400 tickets…",       // plain English, empty unless answered
  "assumptions": [                          // 0-3 short lines, rendered as chips
    "\"Last month\" means August 2026, by purchase date.",
    "Revenue excludes fees, refunds and comps."
  ],
  "sql": "SELECT …",                       // null when nothing was generated
  "columns": ["category", "revenue"],
  "rows": [["NBA", 201512122.83]],
  "row_count": 5,
  "truncated": false,                       // more rows exist than were returned
  "chart": { "type": "bar", "x": "category", "y": "revenue" } | null,
  "trace": {
    "steps": [{"name": "Writing SQL", "ms": 1240}, {"name": "Running query", "ms": 18}],
    "repairs": 1,
    "model": "claude-sonnet-5",
    "total_ms": 2160
  },
  "error": { "code": "rate_limited", "message": "…" } | null
}
```

`GET /api/schema` feeds the schema drawer. `GET /api/examples` feeds the starter
chips.

## Screens and states

1. **Ask — empty.** Header lockup, one-line explanation, large question input,
   six example chips, "What's in the data?" button, footer.
2. **Ask — thinking.** Question pinned; five pipeline steps complete one at a
   time with their own elapsed times. Honest progress, not a spinner.
3. **Answer — Results tab.** Answer card (largest type on the page), assumption
   chips, tabbed panel, trace strip.
4. **Answer — Chart tab.** Horizontal bars in seafoam, one emphasised.
5. **Answer — SQL tab.** Monospace, syntax-highlighted, copy button.
6. **Empty result.** "No rows matched", the assumptions, the SQL, two suggested
   rewordings.
7. **Unanswerable.** What the data does not hold, what it does, three examples.
8. **Blocked.** A destructive request refused before execution, with the reason
   and a note that the connection is read-only.
9. **Error.** Rate limited or key missing. Plain wording, retry button.
10. **Schema drawer.** Slide-over: six tables with columns, plus how revenue,
    tickets sold and home games are defined.
11. **Session history rail.** Questions asked this session; session only.

## Breakpoints

1440 reference · 1024 · 768 · 390 × 844 mobile. At 768 and below the answer card,
chips and tabs stack; the results table scrolls inside its own container instead of
widening the page; the drawer goes full-screen; the history rail collapses to a
menu.

## Accessibility

Real label on the question input; `aria-label` on icon-only buttons; 4.5:1 minimum
text contrast (black text on the cyan button, never white); visible cyan focus
rings; the table is a real `<table>` with scope'd headers.

---

## The Claude Design prompt

> Pasted into Claude Design to produce the mockups. Kept as a record; where it
> lists example questions or sample data, the sections above win.

```text
Design an internal web tool called BSE Insights for Brooklyn Sports & Entertainment
(BSE Global) — the company that owns the Brooklyn Nets, the New York Liberty and
Barclays Center. Someone in ticketing, finance or marketing types a question in
plain English ("How many tickets did we sell for Nets home games last month?") and
gets back a written answer, the assumptions the system made, the SQL it ran, a
results table and, where the shape fits, a simple chart. It should look like a real
internal analytics product owned by the company, not a demo or a chatbot.

BRAND ASSETS — four real SVG logos exist in the repository at web/public/brand/.
Use them exactly as described; do not redraw, recolour or invent marks.
- brand/bse.svg — the BSE Global wordmark, solid white, aspect ratio 672 x 254.
  Goes top-left in the header at about 28px tall. It is white artwork, so it only
  works on a dark surface.
- brand/nets.svg — the Brooklyn Nets mark, solid white, square (215 x 215). Use at
  24px as a badge beside Nets events, in team filter chips, and in example
  questions about the Nets.
- brand/liberty.svg — the New York Liberty mark, seafoam green #87D5B5 with
  near-black #100F0D interior detail, aspect ratio 200 x 170. Use at 24px the same
  way for Liberty events. Because part of it is near-black, sit it on a panel of
  #16161A or lighter so that detail does not disappear.
- brand/barclays-center.svg — the Barclays Center wordmark, white with cyan #00AEEF
  and subtle gradients, aspect ratio 567 x 222. Use once, in the footer, at about
  20px tall, on the line that says the data covers events at Barclays Center.
Show each logo in at least one frame at its real aspect ratio. Never stretch them,
never place the white marks on a light background, and do not add glows or outlines.

The interface must be dark, because the BSE and Nets marks are white artwork.

COLOUR — drawn from the logos themselves so the UI and the brand share one palette:
- Canvas #0B0B0D, panels #16161A, raised surfaces #1E1E23, hairline borders #26262B.
- Text #FFFFFF primary, #A1A1AA secondary, #71717A tertiary.
- Primary accent Barclays cyan #00AEEF: the Ask button (black text on cyan), the
  active tab, focus rings, links.
- Secondary accent Liberty seafoam #87D5B5: chart bars, positive badges, "sold".
- Warning #FBBF24. Error and blocked states #F87171.
Use exactly one accent per surface. No gradients in the UI — the Barclays logo owns
the only gradient on the page. No glassmorphism, no neon glow.

TYPE AND SHAPE — a tight grotesk for display and headings, Inter for body copy, and
a monospace face for SQL and for every number. All numbers tabular and
right-aligned. 12px radius on cards, 8px on chips, inputs and buttons. One soft
shadow level. Generous whitespace: 1200px max content width inside 1440, 24px
gutters. Transitions 150-200ms, no bouncing.

Design these frames at 1440 wide.

1. ASK, EMPTY STATE. Header: BSE wordmark, hairline divider, the product word
   "Insights", and on the right a "What's in the data?" button. Centred below: a
   headline like "Ask anything about ticket sales", a large question input with
   placeholder "e.g. How many tickets did we sell for Nets home games last month?"
   and a cyan Ask button. Under it, six example question chips, two of them
   carrying the Nets and Liberty badges:
   - How many tickets did we sell for Nets home games last month?
   - Top 5 event categories by total revenue
   - Which 2024 events had the highest average ticket price?
   - Which opponent drives the biggest gate?
   - How much revenue did refunds cost us last season?
   - Compare web and box office sales for concerts
   Footer: the Barclays Center wordmark with "Events at Barclays Center, 2024 to
   today" and a small muted pill reading "Demo · synthetic data".

2. ASK, THINKING STATE. The question pinned at the top in a card. Below it five
   pipeline steps that complete one at a time, each with a tick and its own
   elapsed time: Reading schema (0.0s), Writing SQL (1.2s), Checking safety
   (0.01s), Running query (0.02s), Writing answer (in progress). Honest progress,
   not a spinner.

3. ANSWER, RESULTS TAB. The question small and muted at the top. An answer card
   with the written answer in the largest type on the page: "We sold 26,412
   tickets in August 2026 — all of them for upcoming games, since the Nets play no
   home games in August." Beneath it two assumption chips: "'Last month' means
   August 2026, by purchase date" and "Counts sold tickets only; refunds and comps
   excluded". Then a panel with three tabs — Results, SQL, Chart — Results active,
   showing an eight-row table (columns: Event, Date, Tickets sold, Avg price,
   Gate revenue) with the Nets badge on Nets rows. A trace strip along the bottom:
   "claude-sonnet-5 · 2.16s · repaired once" with a small clock icon.

4. ANSWER, CHART TAB. Same frame, Chart tab active: a horizontal bar chart,
   "Total revenue by event category", five bars in seafoam #87D5B5 with the top bar
   emphasised, values labelled at the end of each bar in monospace.

5. ANSWER, SQL TAB. Same frame, SQL tab active: syntax-highlighted SQL on a
   #121215 block, about 12 lines with a JOIN and a GROUP BY, line numbers, and a
   copy button top-right. Keywords in cyan, strings in seafoam, comments muted.

6. EMPTY RESULT. Same frame shape, but the answer card reads "No rows matched this
   question" with a muted explanation, the assumption chips, the SQL still shown,
   and two suggested rewordings as clickable chips.

7. UNANSWERABLE. The question was "What's the weather for the next home game?".
   The card explains the data holds no weather information, lists what it does
   cover (events, tickets, orders, customers, revenue), and offers three example
   questions. Informational tone, warning colour only as a small icon.

8. BLOCKED. The question was "Delete all ticket records". A refusal card in
   #F87171 accent: the request was rejected before it ran, the connection is
   read-only, and only single SELECT statements are permitted. Show the rejected
   statement in monospace, struck through or dimmed.

9. ERROR. The service is rate limited. Plain wording, a retry button, no stack
   trace, the question preserved in the input so nothing is lost.

10. SCHEMA DRAWER. A slide-over panel from the right, about 480px wide, over a
    dimmed ask screen. Lists six tables — venues, teams, events, customers,
    orders, tickets — as collapsible groups with column names and types in
    monospace. At the top, a short "How we define things" block: revenue excludes
    fees, refunds and comps; tickets sold counts sold status only; home games mean
    Nets or Liberty home fixtures.

11. SESSION HISTORY. The answer screen with a 240px left rail listing five
    questions asked this session, the current one highlighted in cyan, each with
    its elapsed time. A "New question" button at the top of the rail.

Then design responsive versions of frame 1 (ask, empty) and frame 3 (answer,
results) at three more widths:
- 1024: rail collapses to icons, content keeps its two-column feel, chips wrap to
  three rows.
- 768: single column. The answer card, assumption chips and tab panel stack. The
  results table scrolls horizontally inside its own bordered container rather than
  widening the page. The header keeps the BSE wordmark but the "What's in the data?"
  button becomes an icon.
- 390 x 844 mobile: single column, 16px side gutters, the question input becomes
  full-width with the Ask button beneath it, example chips scroll horizontally in
  one row, the schema drawer is full-screen, and the history rail becomes a menu
  behind an icon in the header. The BSE wordmark shrinks to 20px tall.

ACCESSIBILITY. Minimum 4.5:1 text contrast. Black text on the cyan button, never
white. Visible cyan focus rings on inputs, chips and tabs. The question input has a
real visible label or a persistent floating label, not placeholder-only. Icon-only
buttons show their accessible name in the design annotation. The results table is a
real table with header cells, not a grid of divs.
```
