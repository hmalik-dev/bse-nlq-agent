---
name: llm-boundary-audit
description: Audit conclusions for the Anthropic model boundary (config.py secret handling, llm.py error mapping) — what was verified clean and the one judgement call, so later audits do not relitigate
metadata:
  type: project
---

Audited 2026-09-12 on branch worktree-BSE-4 (BSE-4: `config.py`, `agent/llm.py`,
`agent/context.py`, `agent/models.py`, `tests/fakes.py`). Verdict was PASS.

Verified clean — do not re-flag unless the code changes:
- `ANTHROPIC_API_KEY` is read only via `config.anthropic_api_key()` (`os.environ`), never
  written, logged or placed on `LlmResult`/`SqlPlan`/`NlqError`. No `logging` in `src/nlq`.
- `dotenv.load_dotenv(PROJECT_ROOT / ".env", override=False)` — shell env wins; `.env` is
  gitignored.
- Both YAML reads (`dictionary.yaml`, `examples.yaml`) use `yaml.safe_load`; every path in
  `context.py` is a module constant, none derived from a request.
- The user's question reaches only the Anthropic request body — no shell, no filesystem, no
  SQL in this layer. SQL execution stays behind the BSE-3 guard + read-only connection
  ([[sql-guard-bypasses]]).

Judgement call (advisory, not a blocker): `map_api_error`'s
`ModelError(f"The model call failed: {error}")` surfaces the SDK's
`"Error code: N - {raw body}"`, which carries Anthropic's `request_id`/workspace metadata
but never the key or the prompt. Acceptable for a single-user demo; if a multi-user or
hosted surface appears, reduce it to a generic sentence and keep the detail in the trace.

Non-issue: `tests/fakes.py` imports `httpx2` (anthropic's transport) without declaring it;
`httpx2-jsfetch` in `uv.lock` is an emscripten-only extra of `httpx2`, not installed.
