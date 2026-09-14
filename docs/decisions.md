# Decisions

The choices a new engineer would ask about, and why. One entry each: the decision,
*why*, and what was *rejected*. Add an entry whenever you make a new call.

## Agent

- **A fixed pipeline with one bounded repair loop:** context → SQL → guard → execute → answer.
  *Why:* each stage tests alone, cost and latency are bounded, and the schema fits the prompt.
  *Rejected:* a tool-using agent with `list_tables`/`run_sql` (earns its keep only on a huge schema).
- **Ambiguity is resolved, not escalated.** The model picks a reading and returns it as assumptions.
  *Why:* one question in, one answer out; there is no conversation to ask in.
  *Rejected:* a clarifying-question turn.
- **Blocked means refused before anything ran; unanswerable means the data cannot say.**
  *Why:* they call for different next steps, so they look different on screen.
  *Rejected:* one "declined" status.
- **The answer is a second call that sees only the returned rows, at most 50.**
  *Why:* it cannot invent data it never saw; an empty result is reported by code, not the model.
  *Rejected:* one call that writes SQL and answer together; sending all 500 rows.
- **Suggestions and totals come from code, never the model.**
  *Why:* a suggestion chip is asked literally, so it must have a known plan; models misadd.
  *Rejected:* model-written rewrites of an empty question; asking the writer to sum a column.
- **A count over one team's or venue's events within a month returns one row per event.**
  *Why:* a 1×1 table repeats the sentence; the rows show where the number came from (BSE-17).
  *Rejected:* re-querying a scalar with `GROUP BY` (the SQL tab would disagree with the rows).
- **Multi-row answers use compact money and name at most 5 rows; a single row stays exact.**
  *Why:* the table below carries exact values; long sentences wrap past two lines (BSE-19).
  *Rejected:* naming every row; a takeaway-only sentence.
- **`ask()` never raises, and every outcome is HTTP 200 with a status.**
  *Why:* the UI, CLI and evaluation render one shape; a malformed question is a 422.
  *Rejected:* mapping statuses to HTTP codes (a blocked question is an answer, not a 403).
- **"Last season" and "this season" are worked out per team, from the data and today.**
  *Why:* Nets and Liberty seasons have different labels and calendars (BSE-28).
  *Rejected:* one NBA-only rule; a combined total with no single season to name.
- **Today is always the real date; tests pass `today=` by argument.**
  *Why:* the app answers against the day an analyst would use; nothing drifts stale.
  *Rejected:* an `NLQ_TODAY` override (a pinned demo goes stale and disagrees with its seed).
- **Injection is handled in the prompt: a message is one request, and any write declines all of it.**
  *Why:* the guard and read-only connection already make writes impossible (BSE-21).
  *Rejected:* an input sanitizer or injection classifier (a second model and a denylist).

## Safety

- **Two layers: a SQL guard in front of a read-only connection (`mode=ro`, `PRAGMA query_only`).**
  *Why:* a statement that fools the guard still cannot write; the prompt is not a control.
  *Rejected:* trusting the prompt; the guard alone.
- **An unknown table or parse error is repaired; anything write-shaped is refused, never retried.**
  *Why:* a guessed name is fixable, and a retry of a `DROP` is still a `DROP`.
  *Rejected:* one retry path for every rejection.
- **Row cap as `LIMIT max_rows + 1`, a progress-handler deadline, and an 8 MB result budget.**
  *Why:* the extra row detects truncation; SQLite has no statement timeout; rows can be huge.
  *Rejected:* a `COUNT(*)` pre-query; a worker thread or `SIGALRM` timeout.
- **The table allowlist is checked per scope; only a CTE in its own scope is exempt.**
  *Why:* a shadowing CTE or shared alias otherwise smuggled `sqlite_master` past it (BSE-23).
  *Rejected:* subtracting every CTE name found anywhere in the tree.
- **The API refuses an unknown `Host` (`NLQ_ALLOWED_HOSTS`).**
  *Why:* with no auth, a DNS-rebinding page could otherwise spend the user's key.
  *Rejected:* CORS rules (rebinding makes the request same-origin).
- **Error messages are fixed sentences; detail goes to the log, and the UI never renders `message`.**
  *Why:* no path or SDK text can reach a screen.
  *Rejected:* a response-scrubbing middleware (it has to guess what a path looks like).
- **No Swagger UI or ReDoc; `/openapi.json` stays.**
  *Why:* both pages load a CDN script onto the app's origin, where it could spend the key.
  *Rejected:* self-hosting the Swagger assets (a dependency for a page nobody needs).
- **No auth, rate limit or spend guard in the app.**
  *Why:* one user runs it with their own key; a console spend cap is the outer layer.
  *Rejected:* a per-minute limit and daily budget file (more code than the risk).

## Model and evaluation

- **The model is chosen by measurement, with the rule fixed before the run.**
  *Why:* cheapest model within one question of the best that gets every refusal right.
  *Rejected:* picking by reputation. Names live in `.env`, so a switch is one variable.
- **Claude Sonnet 5 for both calls.** 20/20 against Haiku 4.5's 16/20 (`docs/eval-results.md`).
  *Why:* Haiku is four behind, so the rule excludes it; a wrong number costs more than a cent.
  *Rejected:* switching on a tied 19-question pass the same day (one pass is noisy for Haiku).
- **Only Sonnet and Haiku are swept, synchronously, once each.**
  *Why:* this is a reading task, not a reasoning one; the rule reads interactive median latency.
  *Rejected:* Opus as a ceiling (half the spend); the Batch API; repeated runs for variance.
- **Prompt caching is measured and declined.**
  *Why:* it saves about 20 cents a sweep but makes cost per question depend on run order.
  *Rejected:* caching with a cold-cache flag for the evaluation; the one-hour TTL.
- **No temperature, thinking or effort parameters.**
  *Why:* Sonnet 5 rejects non-default sampling and Haiku 4.5 rejects `effort`; one code path runs on both.
  *Rejected:* `temperature=0` via `extra_body` (a 400 on the default model).
- **Structured output via `messages.create` plus local validation.**
  *Why:* a plan that fails validation keeps its usage, so every billed call is priced.
  *Rejected:* `messages.parse` (it raises before the usage is readable).
- **Worked examples are conversation turns, with `{today}` filled in at build time.**
  *Why:* the model sees the exact output shape; the system prompt stays a stable snapshot.
  *Rejected:* pasting examples into the system prompt; literal dates.
- **Assumption limits are asked for, not enforced: a fourth is dropped, a long one kept whole.**
  *Why:* structured output cannot enforce `maxLength`, and a correct query failed on a 130-character assumption.
  *Rejected:* rejecting the plan (2 of 18 live questions errored); truncating (loses the reading it states).
- **One SDK retry and a 60-second timeout; every SDK failure maps to one named error code.**
  *Why:* a user is waiting, and the repair loop is the retry that matters.
  *Rejected:* the SDK default of two retries with backoff.
- **Cost is priced by the configured model name; an unknown name is priced at Opus rates.**
  *Why:* a misconfiguration overstates spend instead of hiding it.
  *Rejected:* pricing by the dated ID the API echoes back.
- **The golden set is 20 questions covering every status: empty, unanswerable, writes, injections.**
  *Why:* every status is scored; more rows of the same shape raise cost without moving the decision.
  *Rejected:* dozens of variants; a separate repair-rate column.
- **Evaluation misses fix the prompt, not the model.** Two questions failing on both models is a prompt defect.
  *Why:* the first sweep exposed a copied `LIMIT 5` and an undefined "last season"; the first injection run
  answered a smuggled `DROP` question silently. Each became one prompt rule. *Rejected:* chasing Haiku's misses.
- **The direct Anthropic API, not Bedrock.**
  *Why:* one less account for a new user; Bedrock is a client swap.
  *Rejected:* Bedrock.

## Data

- **A purpose-built synthetic ticketing dataset.**
  *Why:* the example questions are about Nets home games and Barclays Center.
  *Rejected:* Chinook (unrelated business); a real ticketing dataset (none public at this grain).
- **SQLite.**
  *Why:* ships with Python, one portable file, and a real read-only mode.
  *Rejected:* DuckDB (better analytics SQL, another dependency, no safety gain); Postgres (a server).
- **One row per seat in `tickets`.**
  *Why:* "how many tickets" is a plain `COUNT(*)`, the shape models get right most often.
  *Rejected:* order lines with a quantity (`SUM(quantity)` invites errors).
- **Realism is measured: each category's tickets, sell-through, price and gate sit in a tested band.**
  *Why:* anyone at BSE spots a wrong Nets attendance before reading code.
  *Rejected:* jittered capacity (noise in every asserted range).
- **Where the bands disagreed, tickets sold won and sell-through was recomputed.**
  *Why:* tickets sold is the figure people at BSE recognize on sight.
  *Rejected:* widening capacity per event to keep both.
- **Season packages are a flag on the order, and `is_season_member` marks exactly their holders.**
  *Why:* package questions become answerable in SQL; the membership share follows (~1.1%).
  *Rejected:* inferring packages from order size; an independent 8% member flag.
- **Barclays Center home games only.**
  *Why:* BSE sells tickets only to home games; the dictionary and drawer say so.
  *Rejected:* away games; matching the league's game counts.
- **Generated, not committed, and deterministic for a date.**
  *Why:* "last month" always has data, and two machines get the same database.
  *Rejected:* committing a 644 MB file.
- **`--scale` shrinks seats and customers, never the calendar.**
  *Why:* per-customer behavior and per-year counts stay true in small test fixtures.
  *Rejected:* shrinking the calendar.
- **Real team and venue names; fictional performers.**
  *Why:* the questions need the teams, and no real artist should appear to play a date they did not.
  *Rejected:* real artist names.
- **US English: the operator's sides are teams everywhere, including `teams.is_home_team`.**
  "Club" survives only as a seat tier, a real Barclays seating level. A database seeded before
  the rename must be reseeded (delete `data/tickets.db`, then `npm run dev`).
  *Why:* BSE is American, and the model echoes the prompt's words in its answers.
  *Rejected:* keeping the old column name (the model reads column names too); a migration for a
  synthetic, regenerated file. The accuracy report predates the rename; eight questions were
  re-asked in the browser instead.

## Interface

- **React, Vite, TypeScript and Tailwind, served by FastAPI from one address.**
  *Why:* the design needs a custom UI, and the agent core never knows who calls it.
  *Rejected:* Streamlit (looks like every Streamlit app); plain HTML (state gets messy).
- **The UI is dark because the brand assets require it.**
  *Why:* the BSE and Nets marks are solid white; accents come from the logos.
  *Rejected:* a light theme.
- **The committed canvas is the style reference; its data is illustrative.**
  *Why:* parity runs offline against the file and never compares data.
  *Rejected:* matching the canvas's sample numbers.
- **Two layouts, not four.**
  *Why:* it is reviewed on a laptop; one narrow layout proves it works on a phone.
  *Rejected:* 1024 and 768 layouts and an icon rail (hours of CSS nobody will see).
- **The footer closes the content column, and the setup screen shows the `.env` line.** Below 1024 the example questions stack as rows (BSE-34, from the updated canvas).
  *Why:* a full-width footer under the rail read as detached; a phone row of cramped chips hid the questions; the `.env` line is what a new user copies.
  *Rejected:* a footer that moves only when history exists (two placements to test for one look); a separate 768 layout (two layouts, not four).
- **One chart type: horizontal bars, offered only for one label and one number over 2–25 rows.**
  *Why:* every chart the agent offers is category against number; a line would imply a trend.
  *Rejected:* a chart-type picker; asking the model to choose.
- **The chart is inline SVG; Download SVG saves that element.**
  *Why:* the file is the chart as drawn, with no canvas, font embedding or dependency.
  *Rejected:* PNG through a canvas; `html-to-image`; a chart library.
- **Export CSV writes raw values in the browser and defuses formula cells.**
  *Why:* a spreadsheet can do arithmetic, and customer text like `=HYPERLINK(...)` must not run.
  *Rejected:* formatted values; a server export endpoint; XLSX.
- **No simulated progress while a question runs.**
  *Why:* the API is one call, so step times are only known when it returns.
  *Rejected:* advancing steps on a timer (shows times nothing measured).
- **The drawer reads its own short `definitions`, not the prompt's business rules.**
  *Why:* people need one sentence per term; editing the prompt's rules would move accuracy.
  *Rejected:* shortening the rules for both; drawer search and row counts (six tables fit one screen).

## Running and shipping

- **The local run is the primary path, and `npm run dev` is the one command.**
  *Why:* it installs, seeds on first run and opens the dev UI on :4000 with the API on :8000.
  *Rejected:* a production build on :8000 as the default (the build takes a minute on every change).
- **The README names one way to run the app: `npm run dev`.** Docker, the CLI and the test
  commands stay in `CLAUDE.md`; the container and the CLI still work.
  *Why:* the app is meant to be met through its web interface, and every alternative on the
  page is a choice a new user has to make before seeing it.
  *Rejected:* an "Other ways to run" section and a "Tests" section (they read as options, and
  an engineer who wants them finds them in `CLAUDE.md`); the manual run block (duplicated `CLAUDE.md`).
- **The README is for a first-time reader; detail lives in docs.**
  *Why:* a new reader should grasp and run the app in a few minutes, in plain English.
  *Rejected:* one README serving both readers and contributors (latency, fake modes and internal contracts buried the point).
- **The README has one section per question a new reader asks**: setup, how the agent
  works and fails, the dataset and schema, the model choice, tradeoffs, more time, and
  the AI tools used, under headings that say so.
  *Why:* a reader looks for each of those by name; the schema and the AI citation were
  only reachable through a link or a heading that named neither.
  *Rejected:* linking to `docs/data.md` for the schema (the schema belongs where the data
  is introduced); dropping the AI citation (every commit names the co-author, so the README
  should say so too).
- **The `npm run dev` launcher is plain Node (`scripts/dev.mjs`), not bash.** It runs the same
  steps on macOS, Linux and Windows and stops the API with a process group or `taskkill /T`.
  *Why:* Node is already required, and Windows has no bash, so a `.sh` launcher failed before installing anything.
  *Rejected:* WSL or Git Bash instructions (a second setup path); a launcher dependency such as
  `concurrently` (Node's standard library covers it). CI runs the Python and web suites on Ubuntu and Windows.
- **`npm run dev` names a missing uv or Node, or an old Node, and stops; it never installs them.**
  *Why:* one printed line makes the fix obvious without running a remote installer on someone else's machine.
  *Rejected:* installing uv automatically.
- **The app runs only against the real model; a missing key is a setup screen.** `npm run dev` and `scripts/smoke.sh` stop with one line; the interface shows "API key required" from `/api/health`. The tests' scripted client and `eval --fake` stay, since neither reaches a user.
  *Why:* a made-up answer shown to a new user reads as a wrong answer from the real agent.
  *Rejected:* a fake agent behind a flag (reachable by skipping one setup step); mocking `/api/ask` in browser checks (that tests the mock, so they use the real key, capped at three questions).
- **Quickstart seeds at `--scale 0.2`; full scale stays the default.**
  *Why:* a million tickets seed in seconds and answer every example question.
  *Rejected:* a smaller default (every documented figure would change).
- **The container seeds at start, runs as a non-root user, and has no other hardening.**
  *Why:* data stays relative to today and out of the image; `.dockerignore` keeps `.env*` out.
  *Rejected:* baking the database into the image (stale dates, huge image).
- **Tickets live in Linear; CI is the merge gate.**
  *Why:* each ticket carries its acceptance criteria and was built and reviewed on its own.
  *Rejected:* a backlog file in the repo (it drifted from the tracker).
- **A total row names what it totals.** The prompt asks a total row to lead with each value
  the question filters on (year, season, team, category); the scorer ignores extra leading
  columns that hold one value in every row; a lone column is left-aligned.
  *Why:* a lone number beside a blank column reads as a broken table.
  *Rejected:* a UI-only fix (the table can't know the filter value); label columns in every
  golden reference (they would pin the model's alias and type choices). The accuracy report
  predates this rule; it was spot-checked, not re-run.
