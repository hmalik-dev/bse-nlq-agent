---
name: api-boundary-audit
description: Audit conclusions for the FastAPI surface (src/nlq/api.py — /api/ask, /schema, /examples, /health, SPA catch-all) — what was proven safe and the two accepted low-severity notes
metadata:
  type: project
---

Audited 2026-09-12 on branch worktree-BSE-6 (BSE-6: `api.py`, `agent/fake.py`, `examples.py`).
Verdict PASS. Out of scope by ticket decision: auth, rate limiting, spend guard, sessions,
CORS/CSP. App is run locally by one reviewer with their own key.

Proven safe by probing the running app — do not re-derive unless `_serve_ui` changes:
- `_serve_ui`'s catch-all resolves then checks `is_relative_to(static_dir.resolve())`, so
  `/../secret`, `//etc/hosts`, `/%2e%2e/...` and a **symlink inside static pointing out** all
  fall through to `index.html`. `/api/...` is 404'd before the filesystem is touched.
- Agent exceptions are caught in `ask`, logged with `logger.exception` (fixed message, no
  question, no body) and answered as `error`/`internal` with a fixed sentence.
- `Executor.run` opens a fresh connection per call, so FastAPI's threadpool is fine and the
  lazy `_agent` race only ever builds one extra stateless Agent.
- `NLQ_FAKE_AGENT` defaults off and bypasses nothing security-relevant.

Accepted low notes (advisory, already reported once — do not re-flag as blockers):
1. `db/connection.py:22` puts the absolute database path in `DatabaseMissing`, which now
   reaches the JSON body of `POST /api/ask`. Home-directory disclosure only; `FakeAgent`'s
   `ERROR_MESSAGES["database_missing"]` is the path-free wording if it ever matters.
2. `GET /%00` raises `ValueError: embedded null character` out of `spa` → 500
   "Internal Server Error" (no detail in the body, traceback to the server log only).
3. No request-body size cap before pydantic parses; same class as the out-of-scope rate limit.

See also [[llm-boundary-audit]] (`map_api_error` detail, same single-user rationale) and
[[sql-guard-bypasses]].
