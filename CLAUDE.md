# CLAUDE.md — build conventions for this repo

Natural language query agent over a synthetic sports and entertainment ticketing
database. Built for a hiring exercise; it is judged on agent design, SQL accuracy,
code quality, error handling, documentation and the ability to talk through it.

**Read `docs/decisions.md` before changing anything.** It records what was chosen
and why; add to it whenever you make a new call. Then, for the work at hand:

| Doc | Read it for |
|---|---|
| `docs/decisions.md` | every decision made so far, and why the rejected option lost |
| `docs/data-spec.md` | what the generated data must look like, and the ranges tests assert |
| `docs/design-brief.md` | brand assets, tokens, screens and states, the API response shape |
| `docs/backlog.md` | which Linear tickets exist and what order they run in |

## Commands

| Task | Command |
|---|---|
| Install | `uv sync` |
| Seed the database | `uv run python -m nlq.db.seed` |
| Tests | `uv run pytest -q` |
| Lint | `uv run ruff check src tests` |
| Ask from the terminal | `uv run python -m nlq.ask "How many tickets did we sell last month?"` |
| Run the API | `uv run uvicorn nlq.api:app --reload` |
| Accuracy evaluation | `uv run python -m eval.run` |
| Install the web toolchain | `npm ci` (at the root; it is an npm workspace) |
| Web dev server, proxying `/api` to port 8000 | `npm run -w web dev` |
| Web lint, typecheck, tests | `npm run -w web lint`, `typecheck`, `test` |
| Build the UI into `src/nlq/static` | `npm run -w web build` |

## Shape

```
src/nlq/
  config.py      paths, NLQ_TODAY, model names from env
  db/            schema.sql · dictionary.yaml · seed.py · connection.py (read-only)
  agent/         context.py · llm.py · sql_guard.py · executor.py · answer.py · agent.py
  pricing.py     dollars per million tokens; cost_usd() for the trace and the evaluation
  ask.py         CLI: one question in, AskResult JSON out
  api.py         FastAPI: POST /api/ask, GET /api/schema, GET /api/examples
web/             React + Vite + TypeScript + Tailwind, built into src/nlq/static
eval/            golden.yaml · run.py
tests/
```

The agent core never imports the API or the UI. Everything (UI, evaluation, tests)
goes through `Agent.ask(question) -> AskResult`.

## Rules

- Secrets come from the environment only. Never write a key into a file or a command.
- The query path uses a read-only SQLite connection. The SQL guard is the second
  line of defence, not the only one.
- Every change ships with tests in the same commit. Tests never call the Anthropic
  API — use the fake client.
- No new dependency without a line in `docs/decisions.md` saying why.
- Keep functions under ~30 lines and name things the way an interviewer would
  expect to hear them described out loud. This code gets presented, not just read.
- Conventional Commits, one commit per milestone.

## Project

- **Tracker**: Linear team `BSE`, project `BSE NLQ`. Ready = Todo/Backlog. The
  tickets themselves are the source; `docs/backlog.md` maps them and their order.
- **Pipeline settings**: `.claude/project.json` — base branch, tracker states,
  lane settings, verify patterns. CI (`.github/workflows/ci.yml`) is the merge gate.
- **Verification agents**: `.claude/agents/browser-verifier.md` drives the ask
  flow in a browser; `.claude/agents/parity-checker.md` compares a screen against
  its frame in the design canvas.
- **Lanes**: no lane tooling. There is no database server and no long-running
  service, so a ticket runs in a plain git worktree: `uv sync`, then the commands
  above.
- **Stack**: Python 3.12 managed by uv, FastAPI, SQLite. `web/` is Vite + React +
  TypeScript + Tailwind, built into the package's static directory.
- **Verification surface**: the ask flow end to end in a browser — question to
  answer, the SQL tab, the schema drawer, and the blocked and unanswerable states.
- **Brand assets**: `web/public/brand/`. The BSE and Nets marks are solid white, so
  they only work on dark surfaces. Usage rules are in `docs/design-brief.md`.
