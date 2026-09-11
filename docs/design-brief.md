# Design brief

The source of truth for the UI: what screens exist, what state each one shows, and
the tokens to build them with. The Claude Design prompt at the bottom of this file
is what was pasted into Claude Design to produce the mockups; keep the two in sync.

## Product

**Marquee** — ask a ticketing database a question in plain English, get an answer
and the SQL behind it. One screen, one question at a time.

Byline used in the footer: *Prepared for the Brooklyn Sports & Entertainment AI
Engineer exercise. All data is synthetic.*

No club or venue logos or wordmarks anywhere in the interface (see
`docs/decisions.md`).

## The response the UI renders

`POST /api/ask` with `{"question": "..."}` returns:

```jsonc
{
  "status": "answered" | "empty" | "unanswerable" | "blocked" | "error",
  "question": "How many tickets were sold for Nets home games last month?",
  "answer": "About 24,100 tickets…",       // plain English, empty unless answered
  "assumptions": [                          // 0-3 short lines, shown as chips
    "\"Last month\" means August 2026, by purchase date.",
    "Revenue excludes fees, refunds and comps."
  ],
  "sql": "SELECT …",                       // null when nothing was generated
  "columns": ["category", "revenue"],
  "rows": [["Concert", 4821900.0]],
  "row_count": 5,
  "truncated": false,                       // true when more rows exist than shown
  "chart": { "type": "bar", "x": "category", "y": "revenue" } | null,
  "trace": {                                // always present, powers the trace strip
    "steps": [{"name": "Writing SQL", "ms": 1240}, {"name": "Running query", "ms": 18}],
    "repairs": 1,
    "model": "claude-sonnet-5",
    "total_ms": 2160
  },
  "error": { "code": "rate_limited", "message": "…" } | null
}
```

`GET /api/schema` returns the tables, columns and business rules for the schema
drawer. `GET /api/examples` returns the starter questions.

## Screens and states

1. **Ask — empty.** Product mark, one-line explanation, large question input,
   6 example question chips, a "What's in the data?" button, footer byline.
2. **Ask — thinking.** The question locked in place; the pipeline steps reveal as
   they complete: Reading schema → Writing SQL → Checking safety → Running query →
   Writing answer. Honest progress, not a spinner.
3. **Answer.** Answer card (largest type on the page), assumption chips beneath it,
   then a panel with three tabs: Results (table), SQL (mono, copy button), Chart
   (only when `chart` is present). Trace strip along the bottom: model, timings,
   "repaired once" when `repairs > 0`.
4. **Answer — empty result.** Same frame, answer card replaced by "No rows matched
   this question", the assumptions, the SQL, and two suggested rewordings.
5. **Unanswerable.** The agent explains what the data does not contain, lists what
   it does cover, and offers example questions.
6. **Blocked.** A write or destructive request was refused before execution. Shows
   the reason and that the connection is read-only.
7. **Error.** API key missing, rate limited or timed out. Plain wording, a retry
   button, no stack traces.
8. **Schema drawer.** Slide-over listing the seven tables, their columns and the
   business rules (revenue, tickets sold, home games). Reachable from every state.
9. **Session history.** A list of questions asked in this session; clicking one
   restores its answer. Session only, nothing is persisted.

## Tokens

- **Surface:** near-black `#0B0B0D`, panels `#141417`, hairline borders `#26262B`.
- **Text:** `#F5F5F4` primary, `#A1A1AA` secondary.
- **Accent:** marquee gold `#F5C451` for the primary action and the active tab.
- **Semantic:** positive `#4ADE80`, warning `#FBBF24`, blocked/error `#F87171`.
- **Type:** display and headings in a tight grotesk; body in Inter; SQL and numbers
  in a mono face. Numeric columns are tabular and right-aligned.
- **Shape:** 12px radius on cards, 8px on chips and inputs, one soft shadow level.
- **Motion:** 150-200ms fades; pipeline steps tick in one after another; nothing
  bounces.

## Breakpoints

1440 (design reference) · 1024 · 768 · 390 × 844 mobile. The answer card, the
assumption chips and the SQL panel stack on 768 and below; the results table scrolls
horizontally inside its own container rather than pushing the page wide; the schema
drawer becomes full-screen on mobile.

## Accessibility

Every control has an accessible name; the question input has a real label; icon-only
buttons carry `aria-label`. Text contrast at least 4.5:1 against its surface — check
the gold accent on dark, and use dark text on gold buttons. Focus rings are visible
on the accent colour.

---

## The Claude Design prompt

> Paste into Claude Design. It produces the mockups this brief describes.

```text
Design a web app called Marquee — a natural language query tool for a sports and
entertainment ticketing database. A non-technical user types a question in plain
English ("How many tickets were sold for Brooklyn Nets home games last month?") and
gets back a written answer, the assumptions the system made, the SQL it ran, a
results table and, when the shape fits, a simple chart.

Audience and tone: analysts and executives at an arena operator. The product should
feel like a premium internal analytics tool — confident, quiet, arena-at-night. Not
a chatbot, not a dashboard, not a developer toy. The written answer is the hero of
the page; the SQL is supporting evidence.

Do not use any real company, club or venue logos, wordmarks or brand colours.
Marquee has its own identity: design a simple wordmark for it.

Visual direction:
- Dark interface. Canvas #0B0B0D, panels #141417, hairline borders #26262B.
- Text #F5F5F4 primary, #A1A1AA secondary.
- One accent: marquee-bulb gold #F5C451, used for the primary action and the active
  tab only. Semantic colours: #4ADE80 positive, #FBBF24 warning, #F87171 error.
- Display and headings in a tight grotesk, body in Inter, SQL and all numbers in a
  monospace face. Numbers are tabular and right-aligned.
- 12px radius on cards, 8px on chips and inputs, one soft shadow level, generous
  whitespace, no gradients, no glassmorphism.

Design these frames at 1440 wide:
1. Ask, empty state: wordmark, one-line explanation, a large question input with a
   gold "Ask" button, six example question chips, a "What's in the data?" link, and
   a footer line reading "Prepared for the Brooklyn Sports & Entertainment AI
   Engineer exercise. All data is synthetic."
2. Ask, thinking state: the question pinned at the top and five pipeline steps that
   complete one at a time — Reading schema, Writing SQL, Checking safety, Running
   query, Writing answer — each with its own elapsed time.
3. Answer state: an answer card with the written answer in the largest type on the
   page, two assumption chips beneath it, then a panel with three tabs (Results,
   SQL, Chart). Results shows a data table of about eight rows; SQL shows syntax-
   highlighted SQL with a copy button; a trace strip runs along the bottom showing
   the model name, the total time and "repaired once".
4. Answer state, Chart tab active: a horizontal bar chart of five event categories
   by revenue, using the accent colour with one bar emphasised.
5. Empty result state: the same frame with "No rows matched this question" in place
   of the answer, the assumptions, the SQL, and two suggested rewordings.
6. Unanswerable state: the system explains that the data has no weather information,
   lists what it does cover, and offers three example questions.
7. Blocked state: a destructive request ("delete all ticket records") was refused
   before it ran, with a short explanation and a note that the connection is
   read-only.
8. Error state: the service is rate limited; plain wording and a retry button.
9. Schema drawer: a slide-over panel listing seven tables (venues, teams, events,
   customers, orders, tickets) with their columns, plus a short "how we define
   revenue, tickets sold and home games" section.
10. Session history: a narrow left rail listing the questions asked this session,
    with the current one highlighted.

Then design responsive versions of the ask-empty frame and the answer frame at
1024, 768, and 390 x 844 mobile. On 768 and below the answer card, assumption chips
and tabs stack vertically; the results table scrolls horizontally inside its own
container instead of widening the page; the schema drawer becomes full-screen; the
left rail collapses into a menu.

Accessibility: text contrast at least 4.5:1, dark text on the gold button, visible
focus rings, and a real label on the question input.
```
