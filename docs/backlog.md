# Backlog

Eight tickets, one per concern, each implementable unattended by Claude Code. These
get created in the Linear project **BSE NLQ** once the Linear MCP connection is
authorised; this file stays as the readable source they were written from.

Dependencies: **1, 2 and 3 are independent** and can run in parallel lanes. 4 needs
2 and 3. 5 needs 4. 6 needs 5. 7 needs 4. 8 needs 5, 6 and 7.

---

## 1. Data realism pass

**Goal.** The generated database matches the real operation, as specified in
`docs/data-spec.md`.

**Acceptance criteria**
- `venues` holds one row, Barclays Center. The invented venues are gone.
- `events.seating_capacity` exists and carries the per-event house: 17,732
  basketball, ~19,000 end-stage concert, ~8,000 curtained.
- Every calendar year in the window has 36–41 Nets home games, including the year
  the window opens in.
- Liberty plays 20 regular plus 2 playoff home games in each modelled season.
- Non-sport calendar matches `docs/data-spec.md`, with family shows generated as
  6–9 performance engagements.
- A test asserts the per-category median tickets sold, sell-through, average price
  and gate all fall inside the ranges in `docs/data-spec.md`.
- About a third of club seats sell as pre-season season-ticket orders; a test
  asserts both the share and that they are ordered before the season opener.
- About 400,000 customers, and a test asserts the median customer has at most three
  orders.
- The seed stays deterministic, and a full seed finishes in under 60 seconds.

---

## 2. Question to SQL

**Goal.** A question becomes a validated SQL plan, with no execution and no I/O
beyond the model call.

**Acceptance criteria**
- `agent/context.py` builds the prompt payload from `schema.sql`,
  `dictionary.yaml`, the few-shot examples and today's date. Pure, cached, no API
  calls, covered by a snapshot test.
- At least five few-shot examples: a count, a multi-table join, a relative date, a
  group-by with ordering, and a refusal.
- `agent/llm.py` wraps the Anthropic client and returns a Pydantic `SqlPlan`
  (`answerable`, `sql`, `assumptions`, `decline_reason`) using structured output.
- Model IDs and the API key come from the environment; nothing is hardcoded.
- Typed errors for missing key, rate limit, timeout and refusal.
- Tests use a fake client. No test touches the network.

---

## 3. SQL guard and read-only executor

**Goal.** Nothing but a single read can reach the database, proven twice over.

**Acceptance criteria**
- `agent/sql_guard.py` parses with `sqlglot` and rejects anything that is not one
  `SELECT` (or `WITH … SELECT`): rejects `DROP`, `DELETE`, `UPDATE`, `INSERT`,
  `ATTACH`, `PRAGMA`, multiple statements, and a CTE that hides a write.
- Unknown tables are rejected against an allowlist built from the schema.
- A `LIMIT` is injected when the query has none.
- `agent/executor.py` opens SQLite read-only (URI `mode=ro` plus
  `PRAGMA query_only`), enforces a statement timeout and a row cap, and returns
  columns, rows and elapsed milliseconds.
- Tests cover every rejection above, a valid `SELECT`, a valid CTE, `LIMIT`
  injection, the row cap and the timeout.

---

## 4. Agent orchestration

**Goal.** One entry point the UI, the tests and the evaluation all call.

**Acceptance criteria**
- `agent/agent.py` exposes `ask(question) -> AskResult` carrying status, answer,
  assumptions, sql, columns, rows, row_count, truncated, chart, trace and error,
  matching the shape in `docs/design-brief.md`.
- On a guard or execution failure the error is fed back to the model, at most
  twice, and the repair count lands in the trace.
- `agent/answer.py` writes the answer in a second call from the returned rows
  only, with a cap on rows sent. It never sees the database.
- Empty results are reported by code, not by the model.
- A chart is suggested only for two columns, one categorical and one numeric, with
  25 rows or fewer.
- Tests with the fake client cover: answered, empty, unanswerable, blocked,
  repaired-then-succeeded, repairs exhausted, and an API error.

---

## 5. HTTP API

**Goal.** The agent behind a small, typed HTTP surface.

**Acceptance criteria**
- FastAPI app with `POST /api/ask`, `GET /api/schema`, `GET /api/examples`.
- `/api/ask` always returns 200 with a `status` field; only a malformed request
  body returns 422. Internal details never reach the response body.
- Questions are capped in length, and a per-visitor rate limit is enforced.
- The built frontend is served from the app root.
- Tests use `TestClient` with a fake agent. No network.

---

## 6. Web interface

**Goal.** The design in `docs/design-brief.md`, built.

**Acceptance criteria**
- Vite + React + TypeScript + Tailwind in `web/`, built into the package's static
  directory by one command.
- All eleven states from the design brief are implemented.
- Brand assets are used per the rules in the design brief: white marks on dark only,
  correct aspect ratios, Liberty on a panel light enough for its dark detail.
- Layouts verified at 1440, 1024, 768 and 390 × 844.
- Session history, schema drawer, copy-SQL and the chart all work.
- Accessible names on every control, a real label on the input, visible focus
  rings, and the results table is a real `<table>`.
- A browser pass drives ask → answer → SQL tab → schema drawer without errors.

---

## 7. Accuracy evaluation and model choice

**Goal.** The model is chosen by measurement, and regressions get caught.

**Acceptance criteria**
- `eval/golden.yaml` holds about 25 questions with reference SQL and tags: simple,
  join, relative-date, ambiguous, unanswerable, unsafe.
- Scoring compares result sets, not SQL text: order-insensitive unless the
  reference has `ORDER BY`, with a numeric tolerance. Refusal cases pass when the
  agent declines.
- `eval/run.py` runs the set against `claude-opus-5`, `claude-sonnet-5` and
  `claude-haiku-4-5`, reporting accuracy by tag, median latency and cost per
  question from reported token usage.
- Results are written to `docs/eval-results.md`, and the chosen default model is
  recorded in `docs/decisions.md` with its numbers.
- The decision rule is applied as written: the cheapest model within one question
  of the best that also gets every unsafe and unanswerable case right.

---

## 8. Ship

**Goal.** A reviewer can use it in one click, or run it in one command.

**Acceptance criteria**
- Multi-stage Dockerfile: frontend build, then Python runtime. The container seeds
  the database at startup when it is missing.
- Deployed, with the URL in the README, the API key held server-side, and a spend
  cap on the key.
- README covers setup in three commands, architecture with a diagram, the schema
  and dataset, model choice with the measured numbers, error handling, tradeoffs,
  what would come next with more time, and the AI-tool citation the brief asks for.
- The local fallback path (`docker run` with your own key) is documented and tested
  from a clean clone.
