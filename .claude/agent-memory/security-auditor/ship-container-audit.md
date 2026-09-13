---
name: ship-container-audit
description: Container and hosted-deploy key boundary audit (Dockerfile, .dockerignore, docker/entrypoint.sh, fly.toml, scripts/deploy.sh) — what is verified clean and which findings are open
metadata:
  type: project
---

BSE-10 audited 2026-09-12; re-checked in BSE-23 and BSE-11 (2026-09-12).

Verified clean (re-audit only if these files change):
- No key path into the image: `.dockerignore` has `.env*`, no `ARG`/`ENV`/`--secret` for the
  key, no `COPY .` (tests/test_ship.py guards both). `.env.example` has an empty key.
- `git log --all -G 'sk-ant-…'` and `ANTHROPIC_API_KEY=<16+ chars>` found no commits;
  a repo-wide scan for key-shaped literals is clean, `.env` is gitignored.
- Entrypoint never echoes env; `NLQ_DATABASE_PATH`/`NLQ_RESEED`/`NLQ_SEED_SCALE` (quoted,
  and `--scale` is argparse float >0) are operator env only, not request-reachable.
- `web/src` never reads `import.meta.env`, so no env can be inlined into the bundle.
- `fly.toml` holds no secret; `[env]` is paths/scale/allowed-hosts. The health check's
  `Host` and `NLQ_ALLOWED_HOSTS` both derive from `app` in tests, so a rename can't
  silently strip TrustedHostMiddleware. `/api/health` returns booleans only.

Open / operator-left (BSE-11):
- `scripts/deploy.sh` passes the key as an argv word to `fly secrets set`; other local
  users see it in `ps` / `/proc`. Fix: `printf 'K=%s\n' "$KEY" | fly secrets import --stage`.
- No request-body limit anywhere (Starlette buffers the whole JSON body before the
  500-char check) on a 1 GB public machine; docs/security.md lists it, the ticket calls
  the proxy limit a non-goal. Spend cap on the key is an Anthropic-console action.

Hardening note (not a blocker): `.dockerignore` `.env*` matches the context root only.
