---
name: review-checklist-ci-scope
description: Review checklist row — this repo's CI lints only `src tests`, so a new top-level Python package escapes the merge gate
metadata:
  type: feedback
---

`.github/workflows/ci.yml` runs `ruff format --check src tests` and
`ruff check src tests` (and `pytest -q`). Any new top-level Python package —
`eval/` is the first one — is imported by the tests but is **not** linted or
format-checked.

**Why:** CLAUDE.md names CI the merge gate, so unlinted code merges green and
the gap is invisible from the diff of the new package alone.

**How to apply:** whenever a diff adds Python outside `src/` or `tests/`, check
whether `ci.yml` and the CLAUDE.md lint command were widened to cover it, and
report the omission. See [[review-checklist-docs]].

Also settled once, so do not re-derive: in sqlglot 30.x
`parse_one(sql).args.get("order")` is a correct top-level-ORDER BY test — it is
`True` for `… UNION … ORDER BY 1`, `False` for a UNION branch's own ORDER BY,
`False` for an ORDER BY inside a subquery or a CTE body; and
`find_all(exp.With | exp.Window | exp.Having)` finds all three even though a
`WITH` query's root node is a `Select`.
