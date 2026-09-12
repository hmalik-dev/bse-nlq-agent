---
name: ship-container-audit
description: BSE-10 container/key boundary audit — what was verified clean in the image, and the one real finding (docker -p publishes on all host interfaces)
metadata:
  type: project
---

BSE-10 (Dockerfile, .dockerignore, docker/entrypoint.sh, scripts/smoke.sh, README) audited 2026-09-12.

**Verified clean, do not re-audit unless these files change:**
- No key path into the image: `.dockerignore` has `.env*`, no `ARG`/`ENV`/`--secret`, no `COPY .`; built image has only `PATH HOSTNAME LANG GPG_KEY PYTHON_* UV_LINK_MODE NLQ_DATABASE_PATH HOME`, no `.env` and no `*.db` anywhere on disk.
- `docker/entrypoint.sh` and `scripts/smoke.sh` never echo env; the smoke script's `.env` probe is `grep -qE '^ANTHROPIC_API_KEY=.+'` (quiet, value never printed). Its failure-path `echo "$result"` only prints API JSON, whose error messages are fixed strings (see [[llm-boundary-audit]]).
- README contains no key; it points at a one-time secure link and never suggests committing or pasting the key.

**Confirmed finding:** `README.md:129` / `CLAUDE.md:30` use `-p 8000:8000`, which publishes the unauthenticated app on every host interface (and bypasses host firewalls on Linux), letting a LAN peer spend the reviewer's key — there is no auth and the spend guard was descoped. Fix: `-p 127.0.0.1:8000:8000`. `--host 0.0.0.0` inside the container is correct.

**Hardening note (not a blocker):** `.dockerignore` `.env*` only matches the context root, so a future `web/.env*` would enter the web build stage; only `VITE_`-prefixed vars inline, and the final stage copies just built assets.
