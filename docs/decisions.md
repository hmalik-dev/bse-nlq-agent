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
measured at full scale on 2026-09-12, 5,082,400 ticket rows and 1,717,269 orders,
644MB on disk and a 34-second seed. Aggregates over the whole ticket table still
return in under a second, and the container seeds at startup rather than baking
that file into the image. Rejected:
an order-line table with a quantity column, which needs `SUM(quantity)` and invites
off-by-one errors in generated SQL.

**The window is whole calendar years** — the last two plus the year in progress,
and events on sale up to 120 days out. A question about "2024" needs a full year
behind it, not the tail of one season. A test enforces that every recent year has
club home games and non-sport events in it. This means the NBA season before the
window also contributes its January-to-April home games.

**Which NBA seasons exist is decided by the horizon, not by the season in
progress.** The obvious rule — generate up to the season that has tipped off, so
`today.month >= 9` — disagrees with the 120-day on-sale horizon for the ten weeks
from 24 June, when the horizon already reaches the 22 October opener. A seed pinned
to `NLQ_TODAY=2026-07-01` had no Nets games on sale at all, which is both wrong and
the single worst question for this dataset to fail. The bound is now "whichever
season has opened by the horizon", matching what the WNBA and non-sport generators
already did.

**Scope: Barclays Center, the Brooklyn Nets and the New York Liberty**, matching
BSE's actual portfolio. The invented second and third venues are gone. `venues`
stays as a one-row table, because a real ticketing system has one and "at Barclays
Center" should still resolve through a join.

**Seating capacity moves onto the event**, not the venue, and it is exact rather
than jittered: 17,732 for basketball, 19,000 for an end-stage concert or a fight,
8,000 for a curtained house. Per-event capacity is what a real ticketing manifest
looks like, it makes sell-through a question the agent can answer, and exact numbers
make that answer reproducible. Rejected: jittering each event's capacity — more
realistic, but it puts noise into every range the tests assert.

**Realism is a measured target, not a vibe.** Generated figures have to land inside
published real-world ranges, and a test asserts four of them per category: tickets
sold, sell-through, average price and gate. The first pass got Nets attendance 30%
low and priced Liberty like an NBA game, which is exactly the kind of error a
reviewer would spot.

**Where the target table contradicted itself, tickets sold won.** Sell-through is
defined as tickets sold ÷ `seating_capacity`, so the two columns are one fact, and
the drafted pairs did not agree once capacity became exact — 80–92% sell-through for
a concert means 15,200–17,480 tickets against a 19,000 house, far above the same
row's 10,500–13,500. Tickets sold is the column a BSE reviewer recognises on sight,
so the sell-through band was recomputed from it (concerts 55–71%, boxing 47–69%).
Rejected: keeping both bands and widening capacity per event, which would have made
sell-through unreproducible to save a number nobody reads first.

**Season packages are a flag on the order, not an inference.**
`orders.is_season_package = 1` marks one pre-season purchase holding 1–4 seats in
one tier and section at every regular-season home game of a club season. A third of
the Nets house and a quarter of the Liberty house sells this way, which is 28–38% of
each club's sold regular-season tickets — the Liberty share of the *house* is lower
only because their sell-through is, and the share of *sold* seats is what the test
asserts. It puts a real spike in the purchase-date distribution and makes "tickets
sold last month" a more interesting question than a flat random spread would.
Rejected: inferring packages from order size, which makes the question unanswerable
in SQL and the test approximate.

**`is_season_member` marks exactly the package holders**, about 1.1% of customers.
The brief sketch said 8%, but the arithmetic does not allow it: a third of a 17,732
house at 2.35 seats an account is roughly 2,500 Nets accounts, and no allocation of
5,900 seats reaches 32,000 people. A flag that does not correspond to a package
would make every season-member question wrong, so the flag follows the packages and
the share is whatever that comes to. Rejected: an independent 8% coin flip.

**400,000 customers, with a 3% block placing a quarter of the single-game orders.**
The first pass had 30,000 buyers holding 1.1M orders — 36 purchases each, which no
ticketing database looks like. The median buyer now places 3 orders and the 90th
percentile places 6, while season members and resellers appear often, and a test
asserts that shape rather than the customer count alone.

**`scale` shrinks seats per event and the customer base together**, never the
calendar. Per-customer behaviour then stays realistic in the fixture — the median
buyer places 3 orders at scale 0.02 exactly as at scale 1 — and the per-year event
counts can still be asserted. Rejected: shrinking the calendar, which would break
every per-year assertion.

**A calendar year holds 125–150 events, not 150–170.** The earlier figure did not
add up from its own table (41 + 4 + 22 + 30 + 21 + 12 + 4 = 134), and a calendar year
is not a season: it straddles two NBA regular seasons plus a playoff run, so it
carries about 41 Nets home games rather than 41 per season landing neatly in one
year. Barclays' "200+ events a year" marketing figure counts private hires and
college games this dataset does not model.

**Rows are written per event, not accumulated.** Building the whole dataset in
lists first measured 834MB peak RSS at 2.6M tickets, so 5M would have needed about
1.6GB. Inserting each event's orders and tickets as they are generated holds peak
RSS at 52MB for the full 5M-row seed. The full specification, including what is
deliberately not modelled, is in `docs/data-spec.md`.

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
sweep costs under $1, so the harness gets one protection, enforced in
`eval/run.py`: `--fake` drives the entire pipeline through the fake client, so
the harness is debugged for nothing and the live run is the last step instead
of the loop. Rejected, because each would cost more to build than the sweep it
protects: a disk cache of model responses (a replayed response has no latency,
and the decision rule reads median latency, so a cached run would corrupt the
number it was protecting); pricing the sweep with `count_tokens` before the
first call (a gate that fires on every run of a sub-dollar sweep is a prompt
that always gets answered yes); a spend ceiling (thirty sequential questions
with a repair loop bounded at three calls cannot run away); a smoke subset
(`--only` already runs one question); and a timing table for the reference
queries (aggregates over the whole ticket table already return in under a
second, and the golden test executes every one).

**An empty result is a scored outcome in the evaluation.** The brief names the
empty result set as a case to handle gracefully, so the golden set carries a
question that legitimately has no rows behind it and the scorer expects `empty`
for it, alongside the answered, unanswerable and blocked cases.

**The Batch API is not used, despite being half price.** The decision rule reads
median latency per model, and batch timings do not measure the interactive path
a user waits on. Written down because it looks like an obvious saving to anyone
who meets this code later.

**Structured outputs** (`messages.parse`) for SQL generation, so the response is a
validated object, not a string that has to be scraped for a code fence. The
SDK folds the schema's length limits (three assumptions, 120 characters each)
into field descriptions the model reads, and pydantic still enforces them on
the way back; a response that breaks them is reported as `model_refused`, the
same code as a plan the model never produced, because in both cases there is
no plan to run.

**No thinking, effort or temperature parameters.** The SQL call sends the model
name, a token cap, the system prompt, the messages and the output schema, and
nothing else, so one code path runs unchanged on Opus 5, Sonnet 5 and Haiku 4.5
(Haiku 4.5 rejects `effort`). The evaluation compares models, and a parameter
one of them refuses would turn a model swap into a code change. Rejected:
extended thinking (the schema and the dictionary are in the prompt, so this is
a reading task, not a reasoning one; see "No frontier model in the sweep").

**Worked examples ride along as conversation turns, not as prompt text.** The
nine examples in `src/nlq/agent/examples.yaml` become alternating user and
assistant messages ahead of the real question, with each assistant turn being
the `SqlPlan` JSON the model is asked to produce. The model sees the exact
output shape nine times before it writes one, the system prompt stays a stable
snapshot (`tests/golden/sql_prompt.txt`), and every example is proven against
the schema by a test that runs its SQL through the guard and the executor.
Dates inside the example SQL are written against a literal today so the model
sees how to plug in the date the prompt supplies. Rejected: pasting examples
into the system prompt as text (the SDK cannot validate them there, and every
wording tweak would churn the golden file).

**One model call, one retry, sixty seconds.** The client is built with
`max_retries=1` and `timeout=NLQ_LLM_TIMEOUT_S` (default 60), and every SDK
failure is mapped in one function to a named error the interface can show
plainly: a bad or missing key, a rate limit, a timeout or connection failure, a
refusal, and everything else. The mapping lives in `llm.py` so the answer writer
reuses it rather than growing a second set of codes. Rejected: the SDK's default
two retries with backoff (a user is waiting on this call, and the repair loop is
already the retry that matters).

**Model names and the API key are read from the environment at call time**, not
frozen at import, through `config.sql_model()`, `config.answer_model()` and
`config.anthropic_api_key()`. That is how the executor already reads its bounds,
and it lets a test or the evaluation change the model with one environment
variable. `python-dotenv` reads the project-root `.env` once at import with
`override=False`, so `uv run uvicorn` and the CLI pick the key up from the file
while a variable already set in the shell still wins. It is the one dependency
added for this, because the alternative is telling every reviewer to export
four variables by hand before the first question.

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

**The answer writer sees at most 50 rows.** The interface can show 500, but a
two-sentence answer never needs them: the model is told how many rows there are
and whether the query itself was truncated, and describes the first 50. Sending
all 500 costs prompt tokens on every answered question for no better sentence.
Rejected: sending everything (the default row cap is 500 rows of up to 8MB).

**Blocked means "refused before anything ran"; unanswerable means "the data
cannot say".** A request the model declines as destructive, or SQL the guard
finds write-shaped, is `blocked`: the answer is one fixed sentence saying so and
that the connection is read-only, and the rejected statement is shown when there
is one. A question the data cannot answer is `unanswerable`, and the model's own
sentence explaining why is the answer. The two look different on screen because
they call for different next steps: rephrase, versus stop.

**Suggestions come from code, never from the model.** An empty result carries two
fixed rewordings; an unanswerable one carries the questions of the first three
answerable worked examples. Neither state makes a model call, so neither can
invent a question the data does not support.

**A bar chart is offered only when the shape is unambiguous**: exactly two
columns, text in the first, numbers (or NULL) in the second, and between 2 and 25
rows. Anything else is a table. Rejected: asking the model to pick a chart (a
third call for a hint the columns already give away).

**One step per name in the trace, even after a repair.** The interface draws five
fixed steps, so a repair adds its time to `Writing SQL` and `Checking safety`
rather than appending a sixth and seventh row; `repairs` says how many times
that happened. A step that never ran is omitted, and one that started and failed
is kept with its time, because it did run.

**Cost is priced by the model that was asked for, not the one the API echoes
back.** The price table is keyed by the names in `.env`, and an unknown name is
priced at Opus rates so a misconfiguration overstates rather than hides spend.
Because the configured name is what gets priced, a run through the fake client
still reports what those calls *would* have cost at the configured model's rates,
which is the number the offline evaluation wants to see; a configured name
containing "fake" is the way to price a run at zero. Rejected: pricing by the
name the API echoes back (a dated ID such as `claude-haiku-4-5-20251001` would
silently fall to Opus rates). There is no spend guard reading these numbers; the
evaluation sums them and that is all.

**`ask()` never raises.** A typed `NlqError` becomes an `error` result with its
code; anything else becomes `internal` with a fixed message and one ERROR log
line carrying the traceback. The API and the CLI can then treat the result as
the whole contract.

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
exercise does not need. The spend guard planned alongside it (a per-minute
question limit and a daily dollar budget in a usage file) goes with it: the
reviewer runs the app with their own key on their own machine, the repair limit
and the row cap already bound what one question can cost, and a spend cap on the
key in the Anthropic console is the right outer layer. A locked, atomically
written, date-rolling usage file to protect a local demo is more code than the
risk it covers. Rejected: keeping it because it is worth showing (the brief asks
for an agent, not a billing system).

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

**Two layouts, not four.** The canvas draws the ask and answer screens at 1440,
1024, 768 and 390 wide. The app builds the 1440 layout and one narrow layout
below 1024: single column, the history rail behind a header button, the drawer
full width, tables scrolling inside their own container. A take-home is reviewed
on a laptop; one narrow layout proves the page does not break on a phone.
Frames 12 to 17 stay in the canvas as a reference. Rejected: a tablet layout and
an icon-collapsed rail with tooltips (hours of CSS nobody grading this will
resize a window to see).

**No simulated progress while a question runs.** The API is one call, so the
per-step times in the trace are only known when it returns. The waiting state
lists the five step names with a spinner and fills in the real times on
arrival. Rejected: advancing the first steps on a timer and reconciling them
with the trace (it displays times nothing measured, for forty extra lines).

## Ship

**One smoke script, for the local path**, and the container checked once by
hand in the clean-clone check. The README calls Docker the alternative, so a
second two-phase script asserting the same three things against a container
would be scaffolding for the path fewer reviewers take. Rejected: a Docker smoke
script with a real-key phase.

**Eight README sections.** The brief asks for the dataset and schema, the agent's
behaviour, error handling and the AI tools used; a reviewer reads the top and
skims the rest. Rejected: thirteen sections that put the same content behind
five more headings.
