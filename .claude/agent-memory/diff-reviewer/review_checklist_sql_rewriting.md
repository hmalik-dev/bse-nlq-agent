---
name: review-checklist-sql-rewriting
description: Checklist rows for reviewing SQL text rewriting and sqlglot-based guards in this repo
metadata:
  type: feedback
---

When a diff rewrites SQL text or guards it with sqlglot, check these:

- **Appending a clause to raw model text is comment-unsafe.** A trailing `--`
  comment swallows anything appended on the same line, so ` LIMIT n` becomes
  inert. Block comments and trailing semicolons are the easy cases; the line
  comment is the one that slips through.
- **Verify sqlglot class relationships instead of assuming them.** In sqlglot
  30.x `Except`/`Intersect` are *not* subclasses of `Union`; `WITH …` parses to
  a `Select` with a `with` arg (no `With` root); `walk()` yields bare nodes, not
  `(node, parent, key)` tuples as in older versions.
- **Identifier-vs-string in `Anonymous.this`.** A quoted call like
  `"load_extension"(1)` gives `this = Identifier(quoted=True)`, so `str(...)`
  keeps the quotes and name-set lookups miss. SQLite does accept quoted function
  names.
- **Error classification by wall clock.** Mapping "any sqlite error raised after
  the deadline" to a timeout mislabels genuine errors whenever the deadline is
  small or already passed; check whether the mapping should read SQLite's
  message instead.

- **Allowlist bypass probe.** Run each candidate through `guard()` and then
  through a fresh `sqlite3` connection with `set_authorizer` collecting
  `SQLITE_READ` table names; accepted + non-allowlisted read = bypass. Confirm by
  the returned rows: the authorizer reported a `sqlite_master` read for a
  `count(*)` that actually resolved to a shadowing CTE (BSE-23, false alarm).

**Why:** the first four were live defects in the BSE-3 guard/executor diff and none of
them are visible from reading the code alone.

**How to apply:** on any diff touching `sql_guard.py`, `executor.py`, or a
prompt-to-SQL path, probe the library once with a throwaway `python -c` rather
than trusting the docstrings. See [[review-checklist-docs]].
