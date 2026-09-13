# CLAUDE.md — build conventions for this repo

Rules and commands for agents working on BSE Insights, a natural language query
agent over a synthetic ticketing database, built for a hiring exercise. It is judged
on agent design, SQL accuracy, code quality, error handling, docs and the walkthrough.

**Read `docs/decisions.md` before changing anything**, and add an entry for every new
call. Then read what the work touches: `docs/data.md` (dataset and tested ranges),
`docs/design.md` (brand, tokens, screens, API shape), `docs/security.md` (boundaries).

## Commands

| Task | Command |
|---|---|
| Run the app: install, seed once, API :8000, dev UI :4000 | `npm run dev` |
| Install | `uv sync` · `npm ci` (root; an npm workspace) |
| Seed the database | `uv run python -m nlq.db.seed` (`--scale 0.2` for a fifth) |
| Python tests, lint | `uv run pytest -q` · `uv run ruff check src tests` |
| Web lint, typecheck, tests | `npm run -w web lint` · `npm run -w web typecheck` · `npm run -w web test` |
| Ask from the terminal | `uv run python -m nlq.ask "How many tickets did we sell last month?"` |
| Run the API alone | `uv run uvicorn nlq.api:app --reload` |
| Web dev server alone (:4000, proxies `/api` to :8000) | `npm run -w web dev` |
| Build the UI into `src/nlq/static` | `npm run -w web build` |
| Accuracy evaluation (writes `docs/eval-results.md`; never hand-edit it) | `uv run python -m eval.run` (`--fake` for no key) |
| Smoke test of the local path | `scripts/smoke.sh` |
| Container | `docker build -t bse-insights .` · `docker run --env-file .env -p 127.0.0.1:8000:8000 bse-insights` |

## Shape

```
src/nlq/
  config.py      paths and settings from the environment
  db/            schema.sql · dictionary.yaml · seed.py · connection.py (read-only)
  agent/         context.py · examples.yaml · llm.py · sql_guard.py · executor.py · answer.py
                 agent.py · models.py · errors.py
  examples.py    example questions served to the UI
  pricing.py     dollars per million tokens
  ask.py         CLI: one question in, AskResult JSON out
  api.py         FastAPI: /api/ask, /api/schema, /api/examples, /api/health, the built UI
web/             React + Vite + TypeScript + Tailwind, built into src/nlq/static
eval/            golden.yaml · run.py · score.py · report.py · fake_client.py
scripts/         dev.sh · smoke.sh
```

The agent core never imports the API or the UI. Everything goes through
`Agent.ask(question) -> AskResult`.

## Rules

- Secrets come from the environment only. Never write a key into a file or a command.
- The query path uses a read-only SQLite connection; the SQL guard is the second layer.
- Every change ships with tests. Tests never call the Anthropic API; use the fake client.
- No new dependency without a `docs/decisions.md` entry saying why.
- Functions under ~30 lines, named the way you would say them out loud. Conventional Commits.

## Project

- **Tracker:** Linear team `BSE`, project `BSE NLQ`. Pipeline settings: `.claude/project.json`; CI is the merge gate.
- **Lanes:** no lane tooling. A ticket runs in a plain git worktree; `.worktreeinclude` copies `.env`.
- **Verification:** `.claude/agents/browser-verifier.md` drives the ask flow;
  `.claude/agents/parity-checker.md` compares a screen with the canvas.
- **Brand assets:** `web/public/brand/`; usage rules in `docs/design.md`.
