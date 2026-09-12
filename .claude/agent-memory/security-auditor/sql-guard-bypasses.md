---
name: sql-guard-bypasses
description: Confirmed bypass classes for the sqlglot-based SQL guard in src/nlq/agent/sql_guard.py and the executor's bounds — recheck these whenever the guard changes
metadata:
  type: project
---

Confirmed on 2026-09-12 against `src/nlq/agent/sql_guard.py` + `executor.py` (branch worktree-BSE-3).
These four bypasses were all reproduced with a seeded database; retest each after any guard edit.

1. **CTE names are collected globally, not per scope.** `find_all(exp.CTE)` subtracts a CTE
   name from the allowlist check everywhere in the tree, so a CTE declared in an inner
   subquery whitelists a same-named real table in the outer query
   (`SELECT name, sql FROM sqlite_master WHERE 1 IN (WITH sqlite_master AS (SELECT 1 c) SELECT c FROM sqlite_master)`
   returned all 11 `sqlite_master` rows). Correct fix is `sqlglot.optimizer.scope.traverse_scope`.
2. **`sqlglot.errors.TokenError` is not a `ParseError`.** Catching only `ParseError` lets an
   unterminated `/*` comment escape `guard()` as an uncaught exception. Catch `SqlglotError`.
3. **Appending ` LIMIT n` to the model's raw text is comment-swallowable.** SQL ending in a
   `--` comment silently loses the appended clause; only `fetchmany` still caps the rows.
4. **No byte budget on results.** `SELECT hex(zeroblob(20000000)) FROM tickets` stays inside
   the 500-row cap and the 5 s deadline yet grew RSS by 1.8 GB in 2.7 s. Row count and wall
   clock are not sufficient bounds; total result bytes must be bounded too.

Non-issues (verified, do not relitigate): table-valued functions (`pragma_database_list()`,
`json_each(...)`) parse to a `Table` with an empty `.name` and are already rejected; quoted
function names (`"load_extension"('x')`) skip `BANNED_FUNCTIONS` but SQLite answers "not
authorized" because python's sqlite3 disables extension loading and has no readfile/writefile/
edit; `LIMIT 5, 100000` is lowered correctly; `mode=ro` + `PRAGMA query_only` refused a direct
`DELETE`.
