---
name: review-checklist-docs
description: Review checklist row — in this repo, docs/decisions.md is append-only and goes stale, so any diff that changes scope must be cross-read against it
metadata:
  type: project
---

When a diff changes project scope, ticket structure or delivery plans, re-read
all of `docs/decisions.md` (not just the added entry) and `docs/design-brief.md`
for entries the change contradicts.

**Why:** `docs/decisions.md` is written append-only — new entries are added at the
bottom of a section and old ones are left in place. The repo's CLAUDE.md makes it
the mandatory pre-read before any change, so a stale entry actively misdirects the
next lane (e.g. BSE-1 cancelled hosted deployment in `docs/backlog.md` but left
"Reviewers get a hosted link ... API key held server-side under a spend cap"
standing in decisions.md).

**How to apply:** for any scope/plan change, grep decisions.md for the nouns the
diff removed or cancelled, and check that every "see X above/below" cross-reference
resolves in the stated direction. Report contradictions as correctness findings —
for a docs/config ticket they are the defect class that matters.

Also: when a backend-only diff changes what a result field *means* (e.g. BSE-14
empty `suggestions`), grep `web/src` copy, JSDoc and `test-fixtures.ts`, and the
design-brief screen list (not just its JSON block) for the old meaning.
