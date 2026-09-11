# Decisions

Each row: what was decided, what was rejected, and why. This is the source for
the README's tradeoffs section and for talking through the project.

## Product

**Scope.** A single-question agent: ask, get an answer plus the SQL. No
conversation memory, no auth, no user accounts. The brief explicitly says those
are not wanted, and every hour spent there is an hour not spent on the agent.

**Audience.** A non-technical user is the primary reader of the answer; the SQL
and the trace are there for a technical user to check the work.

## Data

**Synthetic ticketing dataset, generated in `src/nlq/db/seed.py`**, over a public
dataset such as Chinook. The exercise's example questions are about Nets home
games, Barclays Center and event categories; a purpose-built schema answers them
directly and shows domain thinking. Rejected: Chinook (nothing to do with the
business), a real ticketing dataset (none public at this grain).

**SQLite**, not DuckDB or Postgres. It ships with Python, the file is portable,
and a read-only connection plus `PRAGMA query_only` gives a real safety guarantee
rather than a prompt-level promise. Rejected: DuckDB (better analytics SQL, but
another dependency and no safety gain here).

**One row per seat in `tickets`.** "How many tickets were sold" becomes a plain
`COUNT(*)`, which is the shape the model handles most reliably. The cost is size:
2.6M ticket rows, 1.1M orders, about 289MB on disk, seeded in 12 seconds.
Aggregates over the whole ticket table still return in under 350ms, and the
container seeds at startup rather than baking that file into the image. Rejected:
an order-line table with a quantity column, which needs `SUM(quantity)` and invites
off-by-one errors in generated SQL.

**The window is whole calendar years** — the last two plus the year in progress,
and events on sale up to 120 days out. A question about "2024" needs a full year
behind it, not the tail of one season. A test enforces that every recent year has
club home games and non-sport events in it.

**The database is generated, not committed.** `seed.py` builds it relative to the
current date, so "last month" always has data in it. The seed is deterministic
(fixed RNG seed), so two machines produce identical data for the same date.

**Deliberate ambiguity in the data.** Refunded tickets, comps priced at zero, a
separate `fee` column, and a purchase date that is not the event date. These make
"revenue", "tickets sold" and "last month" genuinely ambiguous, which is what the
agent has to resolve and state. `src/nlq/db/dictionary.yaml` is the single place
those terms are defined, and it is injected into the prompt.

**Fictional performer names** for concerts and comedy. Real team and venue names
are used because the exercise's questions need them, but no real artist is shown
as having played a date they did not play.

## Model

**Anthropic API, model chosen by measurement.** The accuracy evaluation runs the
same question set against Claude Opus 5, Sonnet 5 and Haiku 4.5 and reports
accuracy, latency and cost per question. Decision rule, fixed before seeing
results: use the cheapest model that comes within one question of the best score
and gets every unsafe and unanswerable case right. Opus is included as a ceiling —
if it misses a question too, the fault is the prompt or the dictionary, not the
model. Model names live in `.env`, so the choice is one variable, not a rewrite.

**Structured outputs** (`messages.parse`) for SQL generation, so the response is a
validated object, not a string that has to be scraped for a code fence.

**Bedrock** is a client swap away and is mentioned in the README, but is not built.
The brief allows either and the direct API is one less moving part for a reviewer.

## Agent

**A fixed pipeline with one bounded repair loop**, not an open-ended tool-using
agent: build context → generate SQL → guard → execute → (on failure, send the
error back, at most twice) → write the answer. Each stage is separately testable,
latency and cost are bounded, and the behaviour is explainable in a sentence.
Rejected: giving the model `list_tables` / `run_sql` tools and letting it explore.
That earns its keep when the schema is too big for the prompt, which is the note
in "what I would do next", not at seven tables.

**Ambiguity is resolved, not escalated.** The model picks the most reasonable
reading and returns its assumptions, which the UI shows next to the answer. There
is no clarifying-question turn, because there is no conversation.

**The answer is written from the returned rows only**, in a second call that never
sees the database. Empty results are reported by code, not by the model, so there
is nothing to hallucinate.

## Interface

**React + Vite + TypeScript + Tailwind on a FastAPI backend**, served as one app
from one URL. The UI is a differentiator for this submission and Streamlit's
polish ceiling is low. The API split also means the agent core has no idea what is
calling it — the UI, the evaluation and the tests all use the same entry point.
Rejected: Streamlit (fast, but every Streamlit app looks the same and a custom
design cannot be built faithfully), plain HTML (no build step, but hand-rolled
state handling gets messy at this level of polish).

**Reviewers get a hosted link**, with the API key held server-side under a spend
cap and a per-visitor rate limit, plus a `docker run` fallback in the README for
anyone with their own key. Reviewers are not assumed to have an Anthropic account.

**No BSE, Nets, Liberty or Barclays Center logos or wordmarks in the interface.**
The app carries its own product identity and a line saying it was prepared for the
Brooklyn Sports & Entertainment AI Engineer exercise on synthetic data. A public
URL wearing a company's branding and serving invented ticket revenue would read as
an official tool, which it is not. Real names inside the dataset are fine and
necessary — the exercise's own example questions use them.
