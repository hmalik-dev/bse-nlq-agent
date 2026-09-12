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

Former judgement call, RESOLVED by BSE-23: `map_api_error` now returns the fixed
`MODEL_ERROR_MESSAGE` and logs the SDK text (`logger.exception`), covered by
tests/test_llm.py::test_a_model_error_hides_the_sdk_text_and_logs_it_once. Note the log line
carries the SDK body (request_id), never the key. Row data reaches the answer writer as
plain text in the user turn; its output is rendered as React text, so steering is text-only.

BSE-7 (eval harness, 2026-09-12) — PASS after one fix. Confirmed pattern worth reusing:
**any generated artifact a scripted/fake mode can overwrite must record its provenance.**
`eval.run --fake` wrote `docs/eval-results.md` and `eval/results/*.json` with fabricated
15/15 numbers indistinguishable from a live sweep; fixed by threading `fake` into both
writers. Verified clean there: reference SQL goes through `sql_guard.guard` + read-only
`Executor`, no unsafe golden entry carries SQL, artifacts hold `database.name` only (no
home path, key or email), `--fake` needs the explicit flag, no new dependency, and the
prompt edits (LIMIT 1 guidance, season rules) leave the read-only and decline rules intact.
`--out`/`--models` reach `Path.write_text` unvalidated but are operator-only on a local
CLI — not a finding, do not re-raise.

Non-issue: `tests/fakes.py` imports `httpx2` (anthropic's transport) without declaring it;
`httpx2-jsfetch` in `uv.lock` is an emscripten-only extra of `httpx2`, not installed.
