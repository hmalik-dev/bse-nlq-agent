# Decisions

Why the agent, its safety layers, the model and the data are shaped this way.
Add an entry only when a call changes what the agent does, what the data means, or what a user sees at runtime; wording, styling and workflow choices go in the PR body.

## Agent
- **A fixed pipeline with one bounded repair loop: context → SQL → guard → execute → answer.**
  *Why:* each stage tests alone, cost and latency are bounded, and the schema fits the prompt.
  *Rejected:* a tool-using agent with `list_tables` and `run_sql` (it pays off only on a huge schema).
- **Ambiguity is resolved, not escalated: the model picks a reading and states it as assumptions.**
  *Why:* one question in, one answer out; there is no conversation to ask in.
  *Rejected:* a clarifying-question turn.
- **Blocked means refused before anything ran; unanswerable means the data cannot say.**
  *Why:* they call for different next steps, so they look different on screen.
  *Rejected:* one "declined" status.
- **The answer is a second call that sees only the returned rows, at most 50.**
  *Why:* it cannot invent data it never saw; an empty result is reported by code, not the model.
  *Rejected:* one call that writes SQL and answer together; sending all 500 rows.
- **Suggestions and totals come from code, never the model.**
  *Why:* a suggestion is asked literally, so it needs a known plan; models misadd.
  *Rejected:* model-written rewrites of an empty question; asking the writer to sum a column.
- **A total row names what it totals: it leads with each value the question filters on.**
  *Why:* a lone number beside a blank column reads as a broken table.
  *Rejected:* a UI-only fix (the table cannot know the filter value).
- **`ask()` never raises, and every outcome is HTTP 200 with a status.**
  *Why:* the UI, CLI and evaluation render one shape; only a malformed question is a 422.
  *Rejected:* mapping statuses to HTTP codes (a blocked question is an answer, not a 403).
- **"Last season" and "this season" are worked out per team, from the data and today.**
  *Why:* Nets and Liberty seasons have different labels and calendars.
  *Rejected:* one NBA-only rule; a combined total with no single season to name.
- **Injection is handled in the prompt: a message is one request, and any write declines all of it.**
  *Why:* the guard and the read-only connection already make writes impossible.
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
  *Why:* a shadowing CTE or shared alias could otherwise smuggle `sqlite_master` past it.
  *Rejected:* subtracting every CTE name found anywhere in the tree.
- **The API refuses an unknown `Host` header.**
  *Why:* with no auth, a DNS-rebinding page could otherwise spend the user's key.
  *Rejected:* CORS rules (rebinding makes the request same-origin).
- **Error messages are fixed sentences; detail goes to the log.**
  *Why:* no path or SDK text can reach a screen.
  *Rejected:* a response-scrubbing middleware (it has to guess what a path looks like).
- **No auth, rate limit or spend guard in the app.**
  *Why:* one user runs it with their own key; a console spend cap is the outer layer.
  *Rejected:* a per-minute limit and a daily budget file (more code than the risk).

## Model and evaluation
- **Claude Sonnet 5 for both calls, picked by a rule fixed before the run (`docs/eval-results.md`).**
  *Why:* cheapest within one question of the best, with every unsafe and unanswerable question right.
  *Rejected:* Haiku 4.5 (four behind); Opus as a ceiling (half the sweep's spend on a reading task).
- **Prompt caching is measured and declined.**
  *Why:* it saves about 20 cents a sweep but makes cost per question depend on run order.
  *Rejected:* caching with a cold-cache flag for the evaluation; the one-hour TTL.
- **Structured output via `messages.create` plus local validation.**
  *Why:* a plan that fails validation keeps its usage, so every billed call is priced.
  *Rejected:* `messages.parse` (it raises before the usage is readable).
- **Worked examples are conversation turns, with `{today}` filled in at build time.**
  *Why:* the model sees the exact output shape; the system prompt stays a stable snapshot.
  *Rejected:* pasting examples into the system prompt; literal dates.
- **One SDK retry and a 60-second timeout; every SDK failure maps to one named error code.**
  *Why:* a user is waiting, and the repair loop is the retry that matters.
  *Rejected:* the SDK default of two retries with backoff.
- **The golden set is 20 questions covering every status: empty, unanswerable, writes, injections.**
  *Why:* every status is scored; more rows of the same shape add cost without moving the decision.
  *Rejected:* dozens of variants; a separate repair-rate column.
- **Evaluation misses fix the prompt, not the model.**
  *Why:* a question both models miss is a prompt defect, and each one became one prompt rule.
  *Rejected:* chasing Haiku's misses with a bigger model or model-specific prompts.

## Data
- **A purpose-built synthetic dataset of Barclays Center events, with home games only.**
  *Why:* the questions are about Nets home games, and BSE sells tickets only to home games.
  *Rejected:* Chinook (unrelated business); a real dataset (none public at this grain); away games.
- **SQLite.**
  *Why:* it ships with Python, is one portable file, and has a real read-only mode.
  *Rejected:* DuckDB (another dependency, no safety gain); Postgres (a server).
- **One row per seat in `tickets`.**
  *Why:* "how many tickets" is a plain `COUNT(*)`, the shape models get right most often.
  *Rejected:* order lines with a quantity (`SUM(quantity)` invites errors).
- **Realism is measured: tickets, sell-through, price and gate sit in tested bands per category.**
  *Why:* anyone at BSE spots a wrong Nets attendance; where bands disagreed, tickets sold won.
  *Rejected:* jittered capacity (noise in every range); widening capacity to keep both bands.
- **Generated, not committed, deterministic for a date; today is always the real date.**
  *Why:* "last month" always has data, two machines match, and tests pass `today=` by argument.
  *Rejected:* committing a 644 MB file; a date override (a pinned demo disagrees with its seed).

## Interface
- **React, Vite, TypeScript and Tailwind, served by FastAPI from one address.**
  *Why:* the design needs a custom UI, and the agent core never knows who calls it.
  *Rejected:* Streamlit (looks like every Streamlit app); plain HTML (state gets messy).
- **One chart type: horizontal bars, offered only for one label and one number over 2–25 rows.**
  *Why:* every chart the agent offers is category against number; a line would imply a trend.
  *Rejected:* a chart-type picker; asking the model to choose.

## Running and shipping
- **`npm run dev` is the one command: it installs, seeds at `--scale 0.2`, and starts the app.**
  *Why:* a million tickets seed in seconds; a missing or old uv or Node is named, and it stops.
  *Rejected:* several documented ways to run it; installing uv on someone else's machine.
- **The launcher is plain Node, so the same steps run on macOS, Linux and Windows.**
  *Why:* Node is already required, and Windows has no bash, so a shell launcher failed at once.
  *Rejected:* WSL or Git Bash instructions (a second setup path); a launcher dependency.
- **Only the real model answers; a missing key is a setup screen, and fakes stay in tests.**
  *Why:* a made-up answer shown to a new user reads as a wrong answer from the real agent.
  *Rejected:* a fake agent behind a flag (reachable by skipping one setup step).
