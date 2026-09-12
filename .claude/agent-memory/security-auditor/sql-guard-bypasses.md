---
name: sql-guard-bypasses
description: Confirmed bypass classes for the sqlglot SQL guard (src/nlq/agent/sql_guard.py) and executor bounds, which are fixed and which were open at the BSE-23 whole-app audit — retest after any guard/executor edit
metadata:
  type: project
---

BSE-3 (2026-09-12) found four; all FIXED by BSE-23 time and re-verified: global CTE-name
subtraction (now scope-based), TokenError escaping (now SqlglotError), inline LIMIT swallowed
by `--` (now appended on a new line), no byte budget (now MAX_RESULT_BYTES in `_fetch`).

OPEN at BSE-23 audit (2026-09-12), reproduced on a `--scale 0.1` seed:
5. **Alias collision defeats the scope exemption.** `_cte_reference_ids` looks tables up by
   `alias_or_name` in `scope.sources`, so aliasing a real table to the same name as a derived
   table or CTE exempts it: `SELECT sql FROM (SELECT 1 AS a) AS x, sqlite_master AS x` returns
   all schema rows; `... pragma_database_list() AS x` returns the absolute DB path. Fix:
   exempt only `not t.args.get("db") and t.name in scope.cte_sources` (verified: still allows
   plain and recursive CTEs, rejects all three collision shapes).
6. **Byte budget is checked after the row is materialised, and one opcode can outlast the
   deadline.** 3 x `hex(zeroblob(1e8))` hit 1.9 GB RSS before refusal; 24 x
   `length(hex(zeroblob(2e8)))` ran 5.6 s past a 5 s deadline at 4.5 GB RSS returning a tiny
   row (progress handler never fires). Fix: `connection.setlimit(SQLITE_LIMIT_LENGTH, ~1e6)`
   (+ `SQLITE_LIMIT_COLUMN`) in `open_read_only`; verified it fails in 0 ms.

Non-issues (verified, do not relitigate): stacked statements, ATTACH/PRAGMA/VACUUM INTO/
REPLACE/EXPLAIN (parse as Command → rejected), quoted/backticked `load_extension`, bare
table-valued functions (empty name → rejected), `LIMIT -1`/`LIMIT (SELECT n)` (lowered),
cartesian join and recursive `count(*)` (stopped at 5001 ms), `mode=ro` refuses DELETE.
