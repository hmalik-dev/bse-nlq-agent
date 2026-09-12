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
about 5M ticket rows and 2M orders once the data pass lands, roughly 650MB on
disk and a 40-second seed, with the measured figures recorded in
`docs/data-spec.md`. Aggregates over the whole ticket table still return in under
a second, and the container seeds at startup rather than baking that file into
the image. Rejected:
an order-line table with a quantity column, which needs `SUM(quantity)` and invites
off-by-one errors in generated SQL.

**The window is whole calendar years** — the last two plus the year in progress,
and events on sale up to 120 days out. A question about "2024" needs a full year
behind it, not the tail of one season. A test enforces that every recent year has
club home games and non-sport events in it. This means the NBA season before the
window also contributes its January-to-April home games.

**Scope: Barclays Center, the Brooklyn Nets and the New York Liberty**, matching
BSE's actual portfolio. The invented second and third venues are gone. `venues`
stays as a one-row table, because a real ticketing system has one and "at Barclays
Center" should still resolve through a join.

**Seating capacity moves onto the event**, not the venue. Barclays runs about
17,732 seats for basketball, about 19,000 end-stage for concerts, and a curtained
house near 8,000 for smaller shows. Per-event capacity is what a real ticketing
manifest looks like, and it makes sell-through a question the agent can answer.

**Realism is a measured target, not a vibe.** Generated figures have to land inside
published real-world ranges, and a test asserts it per category: Nets around 16,500
tickets a game at roughly 93% sell-through and a $140-190 average price; Liberty
around 13,000 at a $55-90 average; arena concerts around 12,000 at $110-150; family
shows near $45-70. The first pass got Nets attendance 30% low and priced Liberty
like an NBA game, which is exactly the kind of error a reviewer would spot.

**Season-ticket packages are modelled.** A third of Nets and Liberty seats sell as
one pre-season order covering the whole season, which puts a real spike in the
purchase-date distribution and makes "tickets sold last month" a more interesting
question than a flat random spread would.

**About 400,000 customers.** The first pass had 30,000 buyers holding 1.1M orders —
36 purchases each, which no ticketing database looks like. Most buyers now appear
once or twice; season members and resellers appear often.

**Cost of that realism: about 5M ticket rows, roughly 650MB, a 40-second seed.**
Accepted, because the file is generated locally and seeded at container start, so it
costs disk rather than deploy weight, and aggregates still return in under a second.
The full specification, including what is deliberately not modelled, is in
`docs/data-spec.md`.

## Process

**Tickets live in Linear**, project `BSE NLQ`, one per concern, sized so each can
be implemented unattended and reviewed on its own. The tickets carry the
acceptance criteria; `docs/backlog.md` is the map of which exist and in what
order. They were drafted in that file first, which is why the early history has
them there.

**Work order.** Pipeline setup comes first and unblocks everything. The data pass
and the SQL guard are independent of each other and run in parallel; SQL
generation needs both, orchestration joins them, and the API, the evaluation, the
interface and shipping follow. Nothing about the interface blocks the agent, which
is the part being graded hardest. The graph is in `docs/backlog.md`.

**The database is generated, not committed.** `seed.py` builds it relative to the
current date, so "last month" always has data in it. The seed is deterministic
(fixed RNG seed), so two machines produce identical data for the same date.

**The seed and the agent share one "today".** `seed_database()` defaults to
`config.today()`, which honours `NLQ_TODAY`, so a pinned date drives the seed, the
agent's relative-date resolution and the evaluation together. Without that, a
container seeded on the real date and an agent pinned to another would disagree on
what "last month" holds. Rejected: pinning only the agent (the "nothing bought
after today" guarantee would silently break).

**Deliberate ambiguity in the data.** Refunded tickets, comps priced at zero, a
separate `fee` column, and a purchase date that is not the event date. These make
"revenue", "tickets sold" and "last month" genuinely ambiguous, which is what the
agent has to resolve and state. `src/nlq/db/dictionary.yaml` is the single place
those terms are defined, and it is injected into the prompt.

**Fictional performer names** for concerts and comedy. Real team and venue names
are used because the exercise's questions need them, but no real artist is shown
as having played a date they did not play.

**The pipeline is configured in the repo, and CI is the merge gate.**
`.claude/project.json` binds the Linear team and the base branch; a single GitHub
Actions job (`uv sync --frozen`, ruff format, ruff check, pytest) runs on every
pull request. The repository is private on the free plan, where branch protection
and auto-merge are both paid, so the merge-wait script merges each PR itself once
that one check is green — without any check it would never merge and every lane
would time out. Rejected: no CI (nothing ever lands unattended), and a hosted
runner matrix across Python versions (the app ships in one container on 3.12).

**No lane tooling.** There is no database server, no ports to allocate and no
long-running service, so a ticket runs in a plain git worktree. The only thing a
worktree needs that git will not give it is `.env`, which is ignored, so
`.worktreeinclude` copies it in — otherwise a lane has no API key and no pinned
`NLQ_TODAY`. Rejected: per-lane databases (nothing to isolate; the SQLite file is
generated per worktree anyway).

**Parity runs offline, against the canvas committed in the repo.** Because
`design-plan/BSE Insights.dc.html` ships alongside the app, `parity-checker` can
compare layout, tokens, typography and chrome copy without calling out to Claude
Design. Where the canvas and `docs/design-brief.md` disagree on styling, the
canvas wins. What parity does and does not compare is set out under "The design
canvas is a style reference, not data" in the Interface section below.

## Model

**Anthropic API, model chosen by measurement.** The accuracy evaluation runs the
same question set against Claude Sonnet 5 and Haiku 4.5 and reports accuracy,
latency and cost per question. Decision rule, fixed before seeing results: use the
cheapest model that comes within one question of the best score and gets every
unsafe and unanswerable case right. Model names live in `.env`, so the choice is
one variable, not a rewrite.

**No frontier model in the sweep.** Opus was in the original plan as a ceiling —
if it missed a question too, the fault would be the prompt rather than the model.
It is not worth buying. This is not a reasoning problem: a question is translated
into SQL against seven tables whose schema and business definitions are both in
the prompt already, and the hard part is knowing that "revenue" excludes fees and
that "last month" means purchase date, which `dictionary.yaml` states outright
rather than leaving to be inferred. Depth of reasoning is not the constraint;
whether the model reads the dictionary it was given is. A question both Sonnet and
Haiku get wrong points at the prompt or the dictionary on its own — the generated
SQL is right there to read — so a third sweep would cost roughly half the
evaluation's total spend to confirm what the failure already shows. Rejected:
sweeping all three (about $2 a run against $0.75, and Opus is over half of it),
and running Opus only on the questions the other two miss (the same conclusion,
still paid for).

**The evaluation is built offline and only then run for real.** A full two-model
sweep costs under $1, so the harness is not worth much protection: two mechanisms,
both enforced in `eval/run.py` rather than left to discipline. `--fake` drives the
entire pipeline through the fake client, so the harness is debugged for nothing
and a live run is the last step instead of the loop; `--max-spend` (default $3)
stops the run the moment the running total would cross it, so a runaway loop is
stopped by the runner and not by someone watching it. `--smoke` runs four
questions spanning the outcome types, which is where a broken prompt reveals
itself before the full set is paid for. Rejected: a disk cache of model responses
keyed on the request (a replayed response has no latency, and the decision rule
reads median latency, so a cached run would corrupt the number it was
protecting); pricing the sweep with `count_tokens` before the first call (a gate
that fires on every run of a sub-dollar sweep is a prompt that always gets
answered yes); and a timing table for the reference queries (aggregates over the
whole ticket table already return in under a second, and the golden test
executes every one).

**An empty result is a scored outcome in the evaluation.** The brief names the
empty result set as a case to handle gracefully, so the golden set carries a
question that legitimately has no rows behind it and the scorer expects `empty`
for it, alongside the answered, unanswerable and blocked cases.

**The Batch API is not used, despite being half price.** The decision rule reads
median latency per model, and batch timings do not measure the interactive path
a user waits on. Written down because it looks like an obvious saving to anyone
who meets this code later.

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

**The row cap is applied as `LIMIT max_rows + 1`.** Asking for one row more than
the interface will ever show is how truncation is detected: if the extra row comes
back, the result was cut off and the answer says so. Rejected: a second `COUNT(*)`
query to learn the true size (two round trips, and the count can disagree with the
rows under concurrent writes), and trusting the model to add its own `LIMIT`.

**The model's SQL text is preserved when a `LIMIT` is only appended.** The interface
shows that text, and re-rendering the statement through sqlglot reformats
whitespace, casing and aliases the model chose deliberately. Only the one case that
genuinely rewrites the statement - lowering a `LIMIT` that exceeds the cap - goes
back through sqlglot's renderer. The appended clause goes on its own line: inline,
a statement ending in a `--` comment would swallow it and run unbounded.

**The query deadline is a progress handler, not a statement timeout.** SQLite has
no statement timeout: `sqlite3_busy_timeout` only covers lock contention, and a
runaway recursive CTE holds no lock. `connection.set_progress_handler` runs a
callback every thousand VM instructions, and returning non-zero interrupts the
query from inside SQLite, which surfaces as "interrupted" and becomes a
`QueryTimeout`. Rejected: running the query on a worker thread and abandoning it
(the thread keeps burning CPU), and a `SIGALRM` alarm (signals only work on the
main thread, and the API serves on worker threads).

**The table allowlist is checked per scope, not per statement.** A CTE name looks
like a table to the parser, so CTE references are exempt - but only where that CTE
is actually in scope. Subtracting every CTE name found anywhere in the tree let
`SELECT ... FROM sqlite_master WHERE 1 IN (WITH sqlite_master AS (...) SELECT ...)`
exempt an outer read of a table the allowlist never permitted, because SQLite
resolves the inner `WITH` only inside the subquery. Scopes come from sqlglot's
`traverse_scope`, and if it cannot resolve them nothing is exempted, so the failure
mode is refusing a valid query rather than allowing an invalid one.

**The result is bounded in bytes as well as rows and time.** The row cap says how
many rows come back, not how large one row is: `SELECT hex(zeroblob(20000000))`
returns a handful of rows well inside the deadline and still costs gigabytes of
memory, and the progress handler cannot help because few instructions allocate
enormous cells. Rows are read one at a time against an 8MB budget and the query
fails once it is spent. Rejected: trusting the row cap alone (one question can end
the process), and a `LENGTH()` pre-check (a second round trip that the model can
write around).

**An unknown table is repairable, a write is not.** A parse error or a table the
schema does not have means the model guessed; the error goes back to it and the
repair loop tries again. Anything write-shaped is refused outright and never
retried, because a retry of a `DROP` is still a `DROP`. The table allowlist is
built by reading the `CREATE TABLE` names out of `schema.sql` at import rather
than being listed in the guard, so the two cannot drift apart.

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

**Reviewers run it locally**, with `docker run` and their own key, documented in
the README. Hosting it was the original plan — a public link, the key held
server-side under a spend cap and a per-visitor rate limit — and it is cancelled:
it costs real money to leave running, and an exposed key is a liability the
exercise does not need. The spend guard in the API stays, because it is worth
showing either way.

**BSE branding, on the company's own instruction.** The exercise is meant to mimic
the internal tools this role would build, so the app is branded as one: the product
is **BSE Insights**, and the real BSE, Nets, Liberty and Barclays Center marks ship
in `web/public/brand/`, supplied by the candidate rather than scraped. A small
`Demo · synthetic data` pill in the footer keeps the demo honest without making it
look like a mock-up.

**The design canvas is a style reference, not data.** Everything in
`design-plan/BSE Insights.dc.html` that looks like data is illustrative: event
names, categories, numbers, column names and SQL text. The running app always
shows the real dataset, and parity is judged on layout, tokens, typography and
component presence, never on data content. The one content change is the fourth
example chip: the canvas put the Liberty mark on an opponent question, so that chip
becomes a Liberty question in the same position.

**The interface is dark because the assets require it.** The BSE and Nets marks are
solid white artwork, so they are invisible on light surfaces. The accent palette is
taken from the logos themselves — Barclays cyan `#00AEEF` for actions, Liberty
seafoam `#87D5B5` for data — so the UI and the brand share one set of colours
instead of an invented one. Measurements and per-logo usage rules are in
`docs/design-brief.md`.
