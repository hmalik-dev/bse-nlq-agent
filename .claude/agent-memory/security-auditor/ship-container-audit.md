---
name: ship-container-audit
description: Container/key boundary audit (Dockerfile, .dockerignore, docker/entrypoint.sh, scripts/smoke.sh) — what is verified clean and which earlier findings are fixed
metadata:
  type: project
---

BSE-10 audited 2026-09-12; re-checked in BSE-23 (2026-09-12).

Verified clean (re-audit only if these files change):
- No key path into the image: `.dockerignore` has `.env*`, no `ARG`/`ENV`/`--secret` for the
  key, no `COPY .` (tests/test_ship.py guards both). `.env.example` has an empty key.
- `git log --all -G 'sk-ant-…'` and `ANTHROPIC_API_KEY=<16+ chars>` found no commits.
- Entrypoint never echoes env; `NLQ_DATABASE_PATH`/`NLQ_RESEED` (seed unlinks the target) are
  operator env only, not request-reachable — not a finding.
- `web/src` never reads `import.meta.env`, so no env can be inlined into the bundle.

Fixed since BSE-10: README/CLAUDE.md now `-p 127.0.0.1:8000:8000`; BSE-23 added
`USER nlq` (uid 10001) with root-owned app files and `/data` owned by nlq.

Hardening note (not a blocker): `.dockerignore` `.env*` matches the context root only.
