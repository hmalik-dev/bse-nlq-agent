---
name: client-export-audit
description: BSE-20 client-side CSV/SVG export (web/src/export.ts) audit outcome — what is clean and the one low note on formula injection
metadata:
  type: project
---

BSE-20 export audit, 2026-09-12: PASS.

Proven clean: SVG export is React text nodes + XMLSerializer (escapes text and attributes; no raw HTML sink in the diff), so data cannot inject script into the standalone .svg. File name slug is `[a-z0-9-]` only, capped at 60, fallback `results`. Object URL revoked on next task; `<a download>` so the blob is never navigated. Formula prefix runs before RFC 4180 quoting; non-strings (number/boolean) are not prefixed, which is correct (a numeric -12 is not a formula).

Low note (not a blocker): the `'` prefix only checks the first character, so in semicolon-delimiter Excel locales an unquoted `a;=HYPERLINK(...)` splits into a cell starting with `=`. Fix if ever raised: add `;` to NEEDS_QUOTES. Leading space/full-width `＝` are not evaluated by Excel or LibreOffice on CSV import. Data is seeded synthetic and the questioner is the viewer, so exploitability is low.

**How to apply:** do not re-flag leading whitespace, full-width signs, or booleans; the semicolon note is the only open item.
