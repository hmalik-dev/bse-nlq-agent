---
name: api-boundary-audit
description: Audit conclusions for the FastAPI surface (src/nlq/api.py) — traversal probes that passed, what was fixed since BSE-6, and the accepted low notes not to re-flag
metadata:
  type: project
---

BSE-6 (2026-09-12) PASS; re-verified in BSE-23 whole-app audit (2026-09-12).
Out of scope by product decision: auth, rate limiting, spend guard, sessions. Single local
reviewer with their own key.

Proven safe (re-derive only if `_serve_ui`/`_static_file` change): `..`, `%2e%2e`, `..%2f`,
absolute `//path`, `/assets/..` and a symlink out of static all 404 (BSE-23 changed
out-of-root from index fallback to 404); `/%00` now serves index, not 500. Agent exceptions
become fixed `internal` "Something went wrong." (probe with key/path in the exception: no
leak). `DatabaseMissing` no longer carries the path (logged only). Question cap is now in
both `AskRequest` and `ask.py`.

Accepted low notes (advisory, do not re-flag as blockers):
1. No request-body size cap; FastAPI's 422 echoes `input`, so a 5 MB question returns 5 MB.
2. `/docs` and `/openapi.json` are exposed (200). Local-only app.
3. `text/plain` / form POSTs to /api/ask get 422 (no CSRF via simple requests); no CORS
   middleware, preflight 405.

Raised in BSE-23 as low finding: any `Host` header gets 200 (no TrustedHostMiddleware), so a
DNS-rebinding page can drive /api/ask and spend the key. If the caller rejects it as a
product decision, move it to the accepted list.
See [[llm-boundary-audit]], [[sql-guard-bypasses]].
