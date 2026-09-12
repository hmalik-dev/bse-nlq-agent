# Decisions

Each row: what was decided, what was rejected, and why. This is the source for
the README's tradeoffs section and for talking through the project.

## Product

**Scope.** A single-question agent: ask, get an answer plus the SQL. No
conversation memory, no auth, no user accounts. The brief explicitly says those
are not wanted, and every hour spent there is an hour not spent on the agent.

**Audience.** A non-technical user is the primary reader of the answer; the SQL
and the trace are there for a technical user to check the work.

**Declined as over-engineering for this brief.** Each was considered and left
out on purpose; the brief's Judgment criterion is as much about what is not
built as what is.

- A column-level PII policy: the customer table is synthetic and the agent
  answers aggregates, so a policy would guard nothing real and add a layer the
  prompt has to explain.
- Search in the schema drawer: six tables and fifty-odd columns fit on one
  screen; a search box for a list that short is a control with no job.
- Row counts per table in the drawer: they change with `--scale` and with
  today's date, so they would need a query per page load to stay honest, for a
  number nobody asks the agent for.
- More golden questions: eighteen cover every status and every failure shape,
  prompt injection included (BSE-21 added three because injection was a shape
  the set lacked); more of the same rows, or variants of one injection, raise
  the run's cost without moving the decision.
- A repair-rate column in the evaluation: the repair count is already in every
  answer's trace, and the decision rule is about right answers, not how many
  tries they took.
- Repeated runs for variance: a rerun measures the provider's nondeterminism,
  not the agent, and doubles the evaluation's cost for one more decimal place
  on a decision that was not close.

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

**Structured outputs** (`output_config` carrying the `SqlPlan` JSON schema) for
SQL generation, so the response is a validated object, not a string that has
to be scraped for a code fence. The SDK folds the schema's length limits (three
assumptions, 120 characters each) into field descriptions the model reads, and
pydantic still enforces them on the way back; a response that breaks them is
reported as `model_refused`, the same code as a plan the model never produced,
because in both cases there is no plan to run.

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

**Claude Sonnet 5 is the default, by the rule above.** The sweep in
`docs/eval-results.md` (15 questions, one pass each, today pinned to
2026-09-11) scored Sonnet 5 at 15/15 with a median latency of 4,008 ms and
$0.0173 per question, and Haiku 4.5 at 12/15, 3,106 ms and $0.0063. Haiku is
three questions behind, not one, so it is not eligible and Sonnet is the only
candidate left; `.env.example` names it for both the SQL and the answer call.
Haiku's three misses are all shape rather than arithmetic: it counted on-sale
events in "total revenue", returned one row for a plural "which events", and
flipped between one and two columns on the refunds question across two runs.

**What the first run revealed.** The first sweep ($0.33) scored Sonnet 13/15
and Haiku 11/15, and two questions failed on both models, which the ticket
treats as a prompt defect rather than a model one. "How much revenue did we
lose to refunds last season?" — Sonnet's plan failed schema validation
(`model_refused`) and Haiku got the right figure with the season label as a
second column, the shape the worked example for "last season" teaches. The
dictionary now defines "last season" (the most recent NBA season with no games
left, filtered on `events.season`) and states that a club season includes its
playoff games, and the reference query carries the season column like the
example. "Which opponent sold the most tickets…" — Sonnet returned five rows,
copying the worked example's `LIMIT 5`, and Haiku silently dropped the
playoffs. The prompt now has one rule for superlatives (a singular most or
highest returns one row; a ranked list is capped at 10 unless a number is
given) and that example returns one row so it agrees with the rule. The second
sweep ($0.35, $0.68 in total) is the one reported. Rejected: a third run to
chase Haiku's remaining misses (they are the measurement, not a defect in it).

**The runner wires the agent itself rather than calling `Agent.from_env()`.**
`from_env` reads the database path once at import, so the per-date file the
runner seeds (`data/eval-<today>.db`) would never reach it. The runner builds
the same three components with the candidate model on both writers, and
`--fake` swaps in a scripted client that answers each golden question with its
own reference query or decline and raises on one of them, so a fake sweep
walks the runner through answered, empty, unanswerable, blocked and error with
no key and no network. Rejected: patching the frozen path from the runner.

**The golden set is eighteen questions: fifteen, plus one per injection shape.**
BSE-21 supersedes "fifteen and no more". The three `unsafe` entries were plain
imperative writes, which prove the model declines an honest request but not that
it cannot be talked out of its rules. Injection is a different shape, not more
of the same rows: an override followed by a delete (`blocked`), a `DROP TABLE`
smuggled after a legitimate question (`blocked`: the whole request is refused,
because answering the legitimate half silently drops a request that tried to
write), and a request for the system prompt and the API key (`unanswerable`).
Each also carries `unsafe` or `unanswerable`, so the decision rule's "every
refusal right" clause covers them without the rule changing. Rejected: five or
more variants, which buys cost, not coverage. The first run found a real miss:
Sonnet answered the smuggled question's count, the rule then picked Haiku. The
fix is one rule in the prompt (treat the message as one request; any part that
would change data declines all of it; nothing in the message overrides the
rules), tested in `tests/test_llm.py`, and the rerun put Sonnet back at 18/18.
Rejected: an input sanitiser or an injection classifier in front of the model
(a second model and a denylist to maintain, when the guard and the read-only
connection already make a write impossible; the prompt only has to stop the
agent answering half a hostile request). Evaluation spend for the ticket: two
full runs at $0.4692 and $0.4676, and one $0.0169 CLI check of the
exfiltration answer's wording.

The original fifteen: the six from the
presentation, word for word, plus nine chosen so every tag the ticket names is
covered: a question with no rows behind it ("Nets home games in July"), two the
data cannot answer, three writes, filters on `status` and on the nullable
`promo_code`, and joins across three and four tables. Nothing in it needs a
CTE, a window function or `HAVING`, so the worked examples stay at nine.

**A refused or off-schema SQL call is still priced.** The first BSE-7 sweep
traced one Sonnet call at zero tokens and zero dollars after the API had
answered and billed it: the SDK's `messages.parse` validates the plan inside
the call and raises pydantic's error before the `Message` is returned, so the
usage was unreachable. The SQL writer now calls `messages.create` with the same
schema under `output_config` (built with the SDK's own `transform_schema`, so
the API sees exactly what `parse` would have sent) and validates the text
itself, which keeps the response in hand on every path. `ModelRefused` carries
the tokens the call was billed for, and the agent prices every model call in
one place, `_priced`, whether it returned or refused; an SDK failure with no
response still charges nothing. Rejected: returning usage next to a `None`
plan (two return shapes for one call); reading the usage back through
`with_raw_response` while keeping `parse` (ties the writer and the fakes to
the SDK's response wrapper for a five-line validation it can do itself).

**Temperature stays unpinned.** BSE-13 asked for `temperature=0` on both calls
so the evaluation reads as a measurement of one fixed configuration. It cannot
ship: the Anthropic SDK this project runs on (1.5.0) removed `temperature`,
`top_p` and `top_k` from `messages.create` and `messages.parse` (passing one is
a `TypeError`), and Sonnet 5, the model the decision rule chose, rejects any
non-default sampling value with a 400; Opus 4.7 and later reject the parameter
outright. Pinning it would take the default model down on every question. The
existing tests already assert the exact argument set each call sends, which is
the guard that no sampling parameter creeps in. Rejected: `extra_body=
{"temperature": 0}` (slips past the SDK only to be refused by the API on the
default model; it would work on Haiku 4.5 alone, turning a model swap into a
code change, the rule "No thinking, effort or temperature parameters" already
states). Temperature 0 never guaranteed identical output on earlier models
either, so the evaluation is quoted as what it is: one pass of the shipped
configuration.

**Prompt caching is measured and declined.** The SQL call sends the same prefix
on every question — the system prompt of rules, schema and dictionary (4,773
tokens), the ten worked examples and the output schema, 7,851 tokens in all
(`count_tokens` on Sonnet 5 returns 7,869 with an 18-token question) — against a
question of a couple of dozen tokens at most, which is the shape prompt caching
exists for. It clears Sonnet 5's 1,024-token minimum
seven times over, and a warm read prices that prefix at a tenth of the input
rate. It still is not worth it. Reads and writes bill at their own rates, so
`cost_usd` would have to price four classes of token instead of two, and the
evaluation's cost per question — the number the model decision rests on — would
start depending on whether a run followed another inside the five-minute
window. That trades a reproducible measurement for roughly twenty cents across a
fifteen-question sweep (one write at 1.25 times the input rate and fourteen
reads at a tenth, against fifteen full-price prefixes at $2 per million). The
answer writer is out of reach regardless: its system prompt is 180 tokens,
under a fifth of the minimum, so a breakpoint there would cache nothing.
Rejected: caching with the evaluation pinned to a cold cache (a flag whose only
job is to switch off the feature it is measuring); the one-hour TTL (twice the
input rate per write to hold a prefix warm for traffic this project does not
have).

**The evaluation was re-run once, last, after BSE-13 and BSE-17** (2026-09-12,
$0.38). BSE-13 changed what the trace prices and BSE-17 changed the prompt (a
per-event breakdown rule, a tenth worked example and a computed total for the
answer writer), so the numbers above describe a configuration that no longer
ships. The Nets golden entry now expects one row per game. Sonnet 5 still scored
15/15, now at a median of 4,550 ms and $0.0185 per question ($0.0012 more, most of
it the longer prompt, since no call in this run refused); Haiku 4.5 scored
13/15 at 3,181 ms and $0.0068, missing "total revenue" (on-sale events counted)
and "which events had the highest average price" (no ten-row cap), and getting
the refunds question and the new Nets breakdown right. The rule still picks
Sonnet 5: Haiku is two questions behind, not one. BSE-21's eighteen-question
run (above, under the golden set) has since replaced this one in
`docs/eval-results.md` and the README: Sonnet 5 18/18 at 4,570 ms and $0.0189
per question, Haiku 4.5 16/18 at 2,720 ms and $0.0071, missing the same two
questions ("total revenue" still counts on-sale events; the average-price
question now stops at one event instead of ten). The rule still picks Sonnet 5.

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

**Suggestions come from code, never from the model.** Both an empty result and an
unanswerable one carry the questions of the first three answerable worked
examples. Neither state makes a model call, so neither can
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

**An empty result suggests questions, not advice.** The interface turns each
suggestion into a chip that submits it, so the old fixed rewordings ("Try a wider
date range.") were asked literally and came back unanswerable: a dead end from the
state meant for recovery. An empty result now offers the same three answerable
worked examples the unanswerable path does, each one a question with a known
plan behind it. Rejected: rewriting the empty question in code (widening a date
or dropping a category means parsing the question or the SQL, and a wrong rewrite
is another empty result), and a third model call to propose rewrites (it breaks
"suggestions come from code" and spends tokens on a state that already has its
SQL on screen to adjust).

**A count over a short run of events comes back one row per event, with the
total in the sentence** (BSE-17). "How many tickets did we sell for Nets home
games last month?" used to return a 1×1 table that repeated the answer. A prompt
rule and a worked example (Liberty home games last month) now make a "how many /
how much" question about one named club's home games or one named venue's
events, sold or played within a month or less, return `name, event_date,
measure` per event, largest first, with no LIMIT so the rows add up to the
total. A question with no club or venue named (yesterday's sales), or one over a
season, a year or a whole category, stays one row, so the promo-code, Q1,
yesterday and concert-refund questions keep their scalar answers. The boundary
is a named club or venue plus a time span rather than a row count, because the
model cannot see row counts before it writes the query.

The total is counted in code, not by the model. When every row is shown and the
last column is whole numbers, `build_user_turn` appends `Total <column> across
all N rows: <sum>`, and the writer is told to state that line first and never
add rows up itself. Averages, percentages and money are floats and are never
summed, and a capped or truncated result gets no total. Rejected: asking the
answer model to add sixteen four-digit counts in its head (the sentence sits
directly above the table, so one slip is visible, and the evaluation does not
score the sentence).

Three columns rather than two: a club plays the same
opponent more than once, so the date is what tells two rows apart, at the cost
of no bar chart for this shape. Rejected: re-querying a scalar result with a
GROUP BY (two queries, and the SQL tab could disagree with the rows) and a
client-side breakdown (it cannot invent rows the query never returned). The Nets
golden entry now expects the breakdown, compared as a multiset so the model's
choice of order does not decide the score.

**Error messages are fixed sentences; the detail goes to the `nlq` log.** A
missing database says how to seed it without naming the absolute path (logged
at WARNING), and a generic model failure says "The model call failed. Try again
shortly." with the SDK's text logged once through `logger.exception`. Rejected:
a response-scrubbing middleware (it would have to guess what a path looks like,
and the message is already built in one place). `ApiKeyError` keeps naming
`ANTHROPIC_API_KEY`: a variable name is neither a secret nor a path, and it is
the instruction the reader needs.

**A spent key is `usage_exhausted`, not `model_error`.** Once the credit balance
or the console spend cap runs out, the API answers 400 "Your credit balance is
too low…" or "You have reached your specified API usage limits…", or a 402
billing error. `map_api_error` recognises those by status and by those two
phrases, ahead of the generic branch, so the interface can say the allowance is
spent instead of "Something went wrong." Rejected: every 400 as usage (a
malformed request is a real fault), and matching on the body's error type alone
(the credit message arrives as a plain `invalid_request_error`). The fake agent
shows it for a question containing "out of credit".

**A multi-row answer is one sentence with compact money and a capped list**
(BSE-19). The sentence sits directly above a table and a chart that carry every
exact value, so eleven-digit figures there repeat the chart at a size nobody
reads. With more than one row, money of $10K or more is written with one decimal
and K, M or B ($203.1M); under $10K it stays exact ($84.50), because rounding
$84.50 to "$84.5" saves nothing and loses the cents, and counts are never
compacted. A ranking is the leader with its figure, then the rest in order with
figures in parentheses. Up to 5 rows every row is named, which covers "top 5"
and two-row comparisons without wrapping past two lines; past 5 the sentence
gives the total (or the leader), the top 3, and "and N more in the results
below". **A single-row answer stays exact**: there is no table beside it to
carry the precision, so the sentence is the answer.

The row counting is done in code, not by the model: `build_user_turn` adds an
`Answer shape:` line naming the rule for this result and, past the limit, the
exact "and N more" count. When the result is truncated, the line asks the
sentence to say only the first rows are shown and to end with "see the results
below", so it never states a count of rows it cannot see. A result the writer
sees only 50 rows of (the answer cap) is not truncated: `row_count` is exact and
the table below shows every row, so it keeps "and N more"; saying "only the
first rows are shown" there would contradict the screen. Rounding stays with the model: formatting
in code would mean guessing which columns are money from their names, and
rounding a displayed figure is not adding rows up, so it does not cut against
the total counted in code (BSE-17).

Rejected: a takeaway-only sentence (users want the full answer in the text, and
read the table and chart for the visual); always naming every row (a 12-month or
16-event answer turns back into a paragraph); a large lead sentence plus a
smaller detail line (it changes the API shape and the UI for what a prompt rule
solves); a limit of 6 or 8 (6+ rows wrap past two lines at display size); naming
the top 5 past the limit (a long answer grows to two lines).

## Interface

**React + Vite + TypeScript + Tailwind on a FastAPI backend**, served as one app
from one URL. The UI is a differentiator for this submission and Streamlit's
polish ceiling is low. The API split also means the agent core has no idea what is
calling it — the UI, the evaluation and the tests all use the same entry point.
Rejected: Streamlit (fast, but every Streamlit app looks the same and a custom
design cannot be built faithfully), plain HTML (no build step, but hand-rolled
state handling gets messy at this level of polish).

**Reviewers run it locally**, from the README's quickstart or with `docker
run`, using a `.env` file handed over with the submission. Hosting it was the
original plan — a public link, the key held server-side under a spend cap and a
per-visitor rate limit — and it was descoped on 2026-09-12: a working local path
with clear instructions meets the brief, and hosting adds an account, a spend
cap and a volume to manage for no grading benefit. The key is delivered to
reviewers through a one-time secure link and never appears in the repository,
the image or the README. The spend guard planned alongside hosting (a per-minute
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

**Every agent outcome is a 200 with a status field; only a malformed body gets
an HTTP error.** `POST /api/ask` returns `AskResult` unchanged for answered,
empty, unanswerable, blocked and error alike, so the interface renders one shape
and never parses an error body. A missing, blank or over-long question (the cap
is `NLQ_MAX_QUESTION_CHARS`, default 500, read per request like every other
setting) is the one 422, and it is FastAPI's standard body. An exception the
agent lets escape is logged with its traceback and answered as `error` /
`internal` with the same fixed sentence the agent itself uses, so no response
ever carries internal detail. Rejected: mapping statuses to HTTP codes (a
blocked question is not a 403 and an empty result is not a 404; both are
answers), and a middleware layer (there is nothing cross-cutting to do).

**The fake agent is the interface's test double.** `NLQ_FAKE_AGENT=1` swaps
`Agent.from_env()` for `FakeAgent`, which answers from canned results keyed on a
word in the question — one per screen the design draws — with no key, no
database and no latency, so the web tickets and their browser passes never
touch the network. Its values are taken from the real schema (event names as
the seed writes them, the six real categories, real column names, SQL that
passes the guard), because the canvas is a style reference and a chip that
showed made-up data would train the interface on the wrong shape. The agent is
resolved on the first request rather than at import, so importing `nlq.api`
needs nothing. Rejected: recording real responses to replay (a fixture that
rots as the prompt changes, for the same six screens).

**The built interface is served by the API, with an index fallback.** Any path
outside `/api` that is not a file in the static directory returns `index.html`,
so a client-side route survives a reload; files that are there (the brand marks
from `web/public`, the hashed assets) are served as themselves. Without a build
the root answers with a one-line JSON hint instead of a 404, so a reviewer who
runs the API first knows what is missing. Rejected: a separate static host (two
addresses for one app), and `StaticFiles(html=True)` alone (no fallback, so a
deep link 404s).

**No simulated progress while a question runs.** The API is one call, so the
per-step times in the trace are only known when it returns. The waiting state
lists the five step names with a spinner and fills in the real times on
arrival. Rejected: advancing the first steps on a timer and reconciling them
with the trace (it displays times nothing measured, for forty extra lines).

**The schema drawer shows a short definition list of its own, not the prompt's rules.**
`business_rules` in `dictionary.yaml` is copy for the SQL writer: twelve rules,
some a paragraph long, naming columns and SQL. The drawer reads a separate
`definitions` key in the same file, each entry a term and one sentence of at most
90 characters, with `backticks` around literal values so the drawer can set them
in seafoam mono as frame 10 draws them. The prompt never reads the key, so the
golden prompt, and the accuracy measured against it, do not move. Rejected:
shortening `business_rules` for both readers (a readability fix that changes SQL
accuracy), and holding the list in `api.py` (the vocabulary split across two
files). A foreign key's target is served as `references` beside the type, read
from the `REFERENCES` clause sqlglot already parses, because it is what makes six
tables read as one dataset. Search and row counts stay out, as declined under
Product.

**The lockup is a button back to the ask screen, and only from an answer.** There
are no routes, so a link would need its navigation suppressed; a `<button>` named
"BSE Insights — back to the start" says what it does. From an answer it calls the
same `reset()` as "New question", keeping the session history. On the ask screen
it does nothing, so a half-typed draft survives a stray click; while a question
is running it also does nothing, because the arriving answer would pull the
reader straight back off the ask screen. Rejected: clearing the session (the
lockup is navigation, not a reset of state).

## Ship

**The no-Docker path is primary.** A reviewer cannot be assumed to have Docker,
while uv and Node are each a one-line install and uv fetches Python itself.
Rejected: committing the built UI to drop the Node requirement (build artefacts
in a repository graded on code quality, plus a freshness check to maintain), and
Docker-only (one more tool to install before anything works).

**Seed at container start, not at image build.** The dataset is generated
relative to today, so a fresh container always has "last month" data, and the
644MB database stays out of the image. `docker/entrypoint.sh` seeds
`NLQ_DATABASE_PATH` when the file is missing, `NLQ_RESEED=1` rebuilds it, and an
optional volume on `/data` keeps it across restarts. Rejected: baking the
database into the image (fast start, stale dates, huge image).

**A plain image, no production hardening.** The audience is an interviewer and
the author running it locally. A health check, a non-root user, memory limits
and scheduled reseeds add nothing to a local demo; `.dockerignore` keeping
`.env*` out of the build context is the one guard that matters.

**One smoke script, for the local path**, and the container checked once by
hand in the clean-clone check. The README calls Docker the alternative, so a
second two-phase script asserting the same three things against a container
would be scaffolding for the path fewer reviewers take. Rejected: a Docker smoke
script with a real-key phase.

**Eight README sections.** The brief asks for the dataset and schema, the agent's
behaviour, error handling and the AI tools used; a reviewer reads the top and
skims the rest. Rejected: thirteen sections that put the same content behind
five more headings.

**`GET /` without a build is a plain HTML page, not JSON or a redirect.** A
reviewer who follows the README with only uv installed hits the address in a
browser, so HTML is the honest answer: it names the build command, the terminal
command and the container, and the API underneath is unchanged. Rejected: a JSON
body (reads as a broken app), a redirect to the README on GitHub (leaves their
machine for something they already have), and committing the built assets (a
bundle that goes stale against its source).

**The quickstart seeds at `--scale 0.2`; full scale stays the default.** The
flag exposes what `seed_database()` already took. At 0.2 the seed is 1,015,708
tickets in 128 MB and 5 seconds against 34 seconds and 644 MB at full scale,
and all six chip questions answer sensibly against it (checked with the real
agent before settling on the number). The default is unchanged so the
documented dataset, the container and the evaluation are what they were.
Rejected: a smaller default (the data section's figures and the container's
"about a minute" would all need restating).

**Superseded by BSE-18, above: the README leads with the agent, not the install
steps.** The brief's first
three criteria are agent design, accuracy and code quality, and all three sat
under 150 lines of setup. The pipeline diagram, the two safety layers, the
"where to look" table and the statuses now form section 2, before "Run it",
and the first screen says the brief's three example questions are in the golden
set word for word. Nothing was shortened; the fix is order. Node moved to its
own subsection because a working app no longer depends on it.

**The README leads with a short summary, then the run steps, then a feature
list, then the design** (BSE-18; supersedes the agent-first order below). Tickets had each edited one
section, and the result was 400 lines with a stale cost figure in one place and
the current one in another, and a trace said to show cost that the interface
never rendered. A reviewer who has just cloned needs numbered clone-to-browser
steps with what success looks like, then a plain list of what the app can do;
the headline result (15/15, $0.0185, the two safety layers) sits above both so
the agent is still the first thing read. Content already in `docs/` (the data
realism ranges, per-question results) is linked rather than repeated.
`tests/test_readme.py` holds the README to the latest evaluation summary and to
paths that exist, so the next re-run cannot leave a stale figure behind.
Rejected: patching the one stale figure (the drift was document-wide), and
keeping the agent design above the run steps (a reviewer's first job is to get
it running, and the summary already names the design's headline points).

## Interface toolchain

**Vite + React 19 + TypeScript, Tailwind v4 through `@tailwindcss/vite`.** One
`web/` package, built straight into `src/nlq/static` so the API serves the UI
from the same address. Tailwind v4 needs no PostCSS config and takes its tokens
from one `@theme` block in `web/src/index.css`, so the canvas palette is declared
once and every class reads it. Rejected: Tailwind v3 (a config file and a PostCSS
step for the same result), CSS modules (tokens would be repeated per file).

**The root `package.json` is a one-line npm workspace, `"workspaces": ["./*"]`.**
The verify script discovers workspace packages by scanning the glob's parent
directory for `package.json` files, so this exact glob is what makes it lint,
type-check, test and build `web/`; `["web"]` would have left the frontend
unverified. npm 11 accepts it and finds the one package. Rejected: no root
package (`npm ci` at the root is what CI and the verify script run).

**Every dependency, and why:**

- `react`, `react-dom` — the component model the design was drawn for.
- `vite`, `@vitejs/plugin-react` — dev server with an `/api` proxy, and the build.
- `typescript`, `@types/react`, `@types/react-dom` — strict types; the two
  `@types` packages are what makes `typescript` useful on React code.
- `tailwindcss`, `@tailwindcss/vite` — the token system, above.
- `vitest`, `jsdom`, `@testing-library/react`, `@testing-library/user-event` —
  tests that render components and drive them the way a person would.
- `eslint`, `typescript-eslint`, `eslint-plugin-react-hooks`,
  `eslint-plugin-jsx-a11y` — the rules the code standards ask for: typed
  boundaries, hook discipline, accessible markup.

No chart library, no syntax-highlighting library, no state library, no router:
the chart is a few divs, the highlighter is a 40-line tokenizer, the state is
three `useState` calls and the app has one screen.

**The real per-step times land in the trace strip.** The API is one call, so
the thinking screen shows a spinner per step and nothing else (see "No
simulated progress" under Interface). When the answer arrives, each step's
measured time is listed on the right of the trace strip at the foot of the
results panel, where the canvas's trace line sits, and a step that never ran is
simply absent. Rejected: a second steps card on the answer screen (a fourth
card the canvas does not draw).

**The session rail appears whenever the session has a question in it**, on the
ask screen as well as the answer screen, except while a question is in flight.
Frames 01 and 02 draw a fresh session and still match; "New question" would
otherwise strand the history behind a screen with no way back to it. Rejected:
rail on the answer screen only (the canvas never draws a rail with an empty ask
screen, so nothing rules on it).

**The question box leaves the page during flight** rather than being disabled:
the thinking screen pins the question in a card, as the canvas draws it, so
there is no input to type into until the answer arrives. Ask is disabled while
the box is empty.

**Rows carry a club badge when their first cell names the club.** "Brooklyn
Nets" and "New York Liberty" are the names the seed writes into `events.name`,
and the badge is drawn from the text of the rendered cell, so it works for any
query that returns the event name first and never for one that does not.

**Error wording is one map keyed by `error.code`, and the raw message never
reaches the screen.** `web/src/error-copy.ts` holds one sentence per code the
API can send; an unknown code gets "Something went wrong." The server's
`error.message` is not rendered anywhere, so an `internal` error cannot leak a
path or an SDK string even if the API's own scrubbing (BSE-12) is imperfect.
Rejected: showing the message under the heading (it is written for a log, not a
user, and it is the only place internal detail could surface).

**One slide-over primitive serves the schema drawer and the phone history menu.**
`SlideOver` owns the backdrop, the dialog role, the focus trap, Esc, and the
return of focus to the opener; the drawer and the menu are its two children.
The history menu renders the same `HistoryRail` the desktop shows in its left
column, so there is one list of questions, not two. Rejected: a second drawer
with its own focus code (the ticket names it as out of scope, and a copy of a
focus trap is where keyboard bugs come from).

**The drawer skips the canvas's search box and footer.** Frame 10 draws a
"Search tables and columns" input and a Barclays footer inside the panel. The
search would be a feature with no behaviour behind it in this ticket, and the
footer repeats the page footer twelve pixels away. Both are recorded as parity
deviations rather than built. Rejected: a decorative disabled search input (a
control that does nothing is worse than no control).

**An empty result opens on the SQL tab.** Frame 06 draws the SQL tab active
with a dimmed Results tab, because the useful thing to look at when nothing
came back is the query. The Results tab stays reachable and says "No rows to
show." Rejected: opening on Results (an empty table under a card that already
says no rows matched).

**An error keeps the question in the box, on the answer screen.** Frame 09
draws the question input under the error card, so Retry and a reworded question
are both one action away and nothing typed is lost. Every other status clears
the draft, as part 1 did. Rejected: sending the user back to the ask screen with
the draft filled in (two screens for one recovery).

**The `<details>` groups open `events` and `tickets` by default**, as frame 10
draws them: they are the two tables almost every question joins, and the other
four stay one click away.

**The canvas token `#08080A` replaces the brief's `#0B0B0D`** for the page
background. The canvas is the drawn artefact and parity is measured against it.
