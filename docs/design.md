# Design

What the interface looks like and what it renders: brand rules, tokens, screens,
states and the API response. Why it looks this way is in `docs/decisions.md`.

## Product

**BSE Insights**, an internal tool for Brooklyn Sports & Entertainment. The header
lockup is the BSE wordmark, a hairline divider and the word "Insights". The footer
carries a small `Demo · synthetic data` pill.

## Brand assets

Committed at `web/public/brand/`. Never stretch, recolour or outline them.

| File | Artwork | Use |
|---|---|---|
| `bse.svg` | White, 672 × 254 | Header lockup, about 28px tall. Dark surfaces only. |
| `nets.svg` | White, 215 × 215 | 24px badge on Nets rows and chips |
| `liberty.svg` | Seafoam `#87D5B5` with near-black `#100F0D` detail, 200 × 170 | 24px badge. Sit it on `#16161A` or lighter. |
| `barclays-center.svg` | White, cyan and gradients, 567 × 222 | Footer venue line, about 20px tall |

## Tokens

Declared once in the `@theme` block of `web/src/index.css`.

| Role | Value |
|---|---|
| Canvas · panel · raised · SQL block | `#08080A` · `#16161A` · `#1E1E23` · `#121215` |
| Hairline · hairline hover · gutter | `#26262B` · `#3A3A42` · `#3F3F46` |
| Text primary · secondary · tertiary | `#FFFFFF` · `#A1A1AA` · `#71717A` |
| Accent (buttons with black text, active tab, focus, links) · hover | Barclays cyan `#00AEEF` · `#5CCBF5` |
| Data (chart bars, "sold") | Liberty seafoam `#87D5B5` |
| Warning · error and blocked | `#FBBF24` · `#F87171` |
| Type | Archivo for headings, Inter for body, JetBrains Mono for SQL, labels and numbers (tabular, right-aligned) |
| Shape | 12px radius on cards, 8px on controls; no gradients in the UI |
| Motion and grid | 150–200ms fades, nothing bounces; 1200px max content width, 24px gutters |

## Example questions

The six chips on the ask screen, in order, served by `GET /api/examples` from
`src/nlq/examples.py`.

| # | Question | Badge |
|---|---|---|
| 1 | How many tickets did we sell for Nets home games last month? | Nets |
| 2 | Top 5 event categories by total revenue | |
| 3 | Which 2024 events had the highest average ticket price? | |
| 4 | Which Liberty home games sold the most tickets this season? | Liberty |
| 5 | How much revenue did refunds cost us last season? | |
| 6 | Compare web and box office sales for concerts | |

## Screens and states

| Frame | Screen | What it shows |
|---|---|---|
| 01 | Ask, empty | Lockup, question input, six chips, "What's in the data?", footer |
| 02 | Thinking | The question pinned; the five step names with a spinner |
| 03–05 | Answer | Answer card, assumption chips, Results · SQL · Chart tabs, trace strip with real step times |
| 06 | Empty result | "No rows matched", opens on the SQL tab, three example questions |
| 07 | Unanswerable | The model's reason and three example questions |
| 08 | Blocked | A fixed refusal, the read-only note, the rejected statement dimmed |
| 09 | Error | One sentence per `error.code`, Retry, the question kept in the input |
| 10 | Schema drawer | Slide-over: plain definitions and six tables; `events` and `tickets` open |
| 11 | Session history | Left rail of this session's questions and "New question" |
| 12–17 | 1024, 768, 390 | Reference only. The app has two layouts: 1440 at 1024 and up, one column below. |

Below 1024 the rail moves behind a header button, the drawer goes full width and
tables scroll inside their own container.

**Results table.** A total row leads with what it totals (`YEAR | TICKETS SOLD`), and a
lone column is left-aligned so its header and value sit together.

**Accessibility.** A real label on the input, `aria-label` on icon buttons,
4.5:1 text contrast, visible cyan focus rings, and a real `<table>` with header cells.

## Parity source

The design of record is `design-plan/BSE Insights.dc.html`, the committed Claude
Design canvas (how to open it: `design-plan/README.md`). Where it and this file
disagree on styling, the canvas wins. Anything in it that looks like data (names,
numbers, columns, SQL) is illustrative: parity compares layout, tokens, type,
components and chrome copy, never data.

## The API response

`POST /api/ask` with `{"question": "..."}` returns one shape for every outcome:

```jsonc
{
  "status": "answered",          // answered | empty | unanswerable | blocked | error
  "question": "Top 5 event categories by total revenue",
  "answer": "NBA leads…",         // empty unless answered
  "assumptions": ["Revenue excludes fees, refunds and comps."],   // 0-3
  "sql": "SELECT …",              // null when nothing was generated
  "columns": ["category", "revenue"],
  "rows": [["NBA", 201512122.83]],
  "row_count": 5,
  "truncated": false,
  "chart": {"type": "bar", "x": "category", "y": "revenue"},       // or null
  "trace": {"steps": [{"name": "Writing SQL", "ms": 1240}], "repairs": 0,
            "model": "claude-sonnet-5", "total_ms": 2160,
            "input_tokens": 9800, "output_tokens": 310, "cost_usd": 0.0227},
  "error": null,                  // or {"code": "rate_limited", "message": "…"}
  "suggestions": []               // example questions, for empty and unanswerable
}
```

Steps are `Reading schema`, `Writing SQL`, `Checking safety`, `Running query` and
`Writing answer`, in that order; a step that never ran is left out. A missing, blank
or over-long question gets a 422.

| Route | Returns |
|---|---|
| `GET /api/schema` | `tables` (name, description, columns with type and `references`) and `definitions` for the drawer |
| `GET /api/examples` | `[{"question": "...", "badge": "nets" \| "liberty" \| null}]` |
| `GET /api/health` | `{"ok": true, "database": true, "fake": false}` |

**Fake agent.** `NLQ_FAKE_AGENT=1` answers without a key or database. A word in
the question picks the screen: `delete`, `drop`, `update` → blocked; `weather` →
unanswerable; `nothing` → empty; `rate limit`, `no key`, `no database`,
`out of credit` → that error; `slow` → a two-second wait; `nets` → a results
table; anything else → the category chart.
