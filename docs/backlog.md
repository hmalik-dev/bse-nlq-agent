# Backlog

The tickets live in Linear, project
[**BSE NLQ**](https://linear.app/vendor-marketplace/project/bse-nlq-273533ecd95d)
(team `BSE`). That is where the acceptance criteria, the rulings and the current
state of each one are; this file is only the map. The reasoning behind the
choices they implement is in `docs/decisions.md`.

| Ticket | Title |
|---|---|
| BSE-1 | Pipeline readiness: project config, CI, lane env, review agents |
| BSE-2 | Data realism: Barclays-only calendar, per-event capacity, season packages, 400k customers |
| BSE-3 | SQL guard and read-only executor |
| BSE-4 | Question to SQL: prompt context, structured SqlPlan, typed errors, fake client |
| BSE-5 | Agent orchestration: Agent.ask with repair loop, answer writer, AskResult |
| BSE-6 | HTTP API: /api/ask, /api/schema, /api/examples, static serving, fake agent |
| BSE-7 | Accuracy evaluation and model choice |
| BSE-8 | Web interface, part 1: scaffold, design tokens, ask to answer flow, session history |
| BSE-9 | Web interface, part 2: failure states, schema drawer, responsive layouts, accessibility |
| BSE-10 | Ship: README with local run instructions, Dockerfile, smoke script |
| BSE-11 | Ship, part 2: hosted deployment on Fly.io with server-side key and spend cap |

## Order

```text
BSE-1
  └─> BSE-2 ┐
      BSE-3 ┘ (parallel)
        └─> BSE-4 ──> BSE-5 ┬─> BSE-6 ┐
                            └─> BSE-7 ┘ (parallel)
                                 └─> BSE-8 ──> BSE-9 ──> BSE-10
```

BSE-1 unblocks everything. BSE-2 and BSE-3 are independent of each other, as are
BSE-6 and BSE-7. BSE-10 needs BSE-7 as well as BSE-9.

**BSE-11 is canceled.** The app is run locally from the README's instructions
rather than hosted, so there is no deployment, no server-side key and no spend
cap to manage.
