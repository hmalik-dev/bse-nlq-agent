---
name: review-checklist-deploy-config
description: Checklist rows for reviewing hosting/deploy config diffs (Fly, Docker volumes, proxy health checks, host allowlists)
metadata:
  type: feedback
---

Rows to run on any diff that adds hosting config (fly.toml, deploy scripts, entrypoint changes).

**Why:** these diffs cannot be exercised locally (the lane ships them [BLOCKED]), so the only
defence is reading the interaction between the platform and the app's own guards.

**How to apply:**
- Mounted volume vs `USER`: a Docker named volume inherits the image's ownership, a cloud
  volume (Fly, EBS) is a fresh root-owned fs. A non-root entrypoint that writes there can
  crash-loop, and any "docker volume rm ..." advice in the error is wrong on that platform.
- Platform health check vs `TrustedHostMiddleware`: starlette matches `host.split(":")[0]`
  exactly against the allowlist, so a check that reaches the machine by IP gets 400 forever.
  A `headers.Host` override in the check config is a claim about the platform's checker
  (Go's net/http ignores `Header["Host"]`) — flag it as unverifiable, do not call it fine.
- Going public re-opens accepted risks: re-read `docs/security.md` "Accepted risks" for
  anything justified by "local, single-user" (body-size cap, no auth, no rate limit).
- "App name of the operator's choosing" + tests asserting the literal name = CI breaks on
  rename. Check the rename comment lists every file that carries the name.
- Optional env branches in the deploy script (`${VAR:+--env ...}`) are usually untested and
  persist in the machine config until the next plain deploy.
- Hash the untracked files (`md5 -q`) when reviewing alongside another agent: the tree can
  change under you mid-review. See [[review-checklist-docs]].
