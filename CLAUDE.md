# CLAUDE.md — build conventions for this repo

Natural language query agent over a synthetic sports and entertainment ticketing
database. Built for a hiring exercise; it is judged on agent design, SQL accuracy,
code quality, error handling, documentation and the ability to talk through it.

**Read `docs/decisions.md` before changing anything.** It records what was chosen
and why. Add a row there whenever you make a new call. UI work also reads
`docs/design-brief.md`.

## Commands

| Task | Command |
|---|---|
| Install | `uv sync` |
| Seed the database | `uv run python -m nlq.db.seed` |
| Tests | `uv run pytest -q` |
| Lint | `uv run ruff check src tests` |
| Run the API | `uv run uvicorn nlq.api:app --reload` |
| Accuracy evaluation | `uv run python -m eval.run` |

## Shape

```
src/nlq/
  config.py      paths, NLQ_TODAY, model names from env
  db/            schema.sql · dictionary.yaml · seed.py · connection.py (read-only)
  agent/         context.py · llm.py · sql_guard.py · executor.py · answer.py · agent.py
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
