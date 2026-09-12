# design-plan — imported Claude Design canvas

Reference mockup for the BSE Insights UI. **Nothing here is built or wired up
yet** — this folder is the visual source of truth that `web/` will be
implemented against. Do not import from it at runtime.

## Source

| | |
|---|---|
| Project | `Responsive states design canvas` (owner: Humza Malik) |
| Project id | `b0d8463a-c312-492f-b20f-e17b649cb5ef` |
| URL | https://claude.ai/design/p/b0d8463a-c312-492f-b20f-e17b649cb5ef?file=BSE+Insights.dc.html |
| Imported | 2026-09-11, via the `claude_design` MCP (`DesignSync.get_file`) |

## Files

| File | Notes |
|---|---|
| `BSE Insights.dc.html` | The canvas. 17 frames across 4 artboards. Fetched whole (not truncated). |
| `support.js` | Claude Design's `dc-runtime` bundle, loaded by the canvas as `./support.js`. Generated — never edit. |
| `brand/*.svg` | The four marks the canvas references. |

These are exactly the files the canvas needs: `BSE Insights.dc.html` imports
`./support.js` and `brand/{barclays-center,bse,liberty,nets}.svg`, and nothing
else. The project also holds `BSE Insights-print.dc.html`, `doc-page.js` (the
paged-document component the print variant uses, unreachable from this canvas)
and a duplicate `uploads/` copy of the marks. None are needed to render the
design, so none were kept.

### About `brand/`

The canvas's own copies of the four SVGs are the **same artwork** as the ones
already committed at `web/public/brand/` — identical `viewBox`/dimensions and
identical path data — differing only in that the uploaded copies carry a ~14 KB
base64 C2PA provenance block each, and declare white via inline `fill` instead
of a `<style>` class. The repo copies were used here so the folder stays
self-contained without duplicating the artwork in a third, heavier form. Both
render the same white marks, which per `docs/design-brief.md` only work on dark
surfaces.

## Frames

Four artboards. `1a` is the desktop set at 1440; `q12`/`q14`/`q16` are the
responsive cuts.

| # | Frame | Artboard |
|---|---|---|
| 01 | Ask, empty state | 1a (1440) |
| 02 | Thinking | 1a |
| 03 | Answer — results table | 1a |
| 04 | Answer — chart | 1a |
| 05 | Answer — SQL tab | 1a |
| 06 | Empty result | 1a |
| 07 | Unanswerable | 1a |
| 08 | Blocked | 1a |
| 09 | Error | 1a |
| 10 | Schema drawer | 1a |
| 11 | Session history | 1a |
| 12 | Ask | q12 (1024) |
| 13 | Answer | q12 (1024) |
| 14 | Ask | q14 (768) |
| 15 | Answer | q14 (768) |
| 16 | Ask | q16 (mobile) |
| 17 | Answer | q16 (mobile) |

Frames 06–09 cover the states `CLAUDE.md` names as the verification surface
(blocked and unanswerable), so the mockup is complete against it.

## Tokens observed in the canvas

Counts are occurrences in the markup — a rough guide to what is structural vs.
accent. Reconcile against `docs/design-brief.md` before encoding these into
Tailwind; where the two disagree, the design brief is the decision of record and
this file is only evidence.

**Surfaces (dark, ascending)** `#08080A` page · `#0B0B0D` frame · `#121215` ·
`#16161A` raised · `#1E1E23` input/hover
**Lines** `#26262B` (dominant border) · `#3A3A42` · `#3F3F46`
**Text** `#FFFFFF` primary · `#A1A1AA` secondary · `#71717A` muted
**Accent** `#00AEEF` BSE cyan · `#5CCBF5` hover · `#2CC0F5`
**Status** `#87D5B5` Liberty green · `#FBBF24` warning · `#F87171` error

**Type** `Archivo` 500/600/700 headings · `Inter` 400/500/600 body ·
`JetBrains Mono` 400/500/700 for SQL, labels and numerics. All three come from
Google Fonts in the canvas `<helmet>`.

## Viewing it

The canvas is plain HTML that needs `support.js` served next to it, so open it
over HTTP rather than `file://`:

```
cd design-plan && python3 -m http.server 8000
# then http://localhost:8000/BSE%20Insights.dc.html
```

## Re-syncing

`DesignSync` read methods take the project id above. Fetching a file returns its
content inline, so pull straight into this folder rather than through the
conversation. Edits made here do **not** flow back to the canvas — this is a
one-way import.

## Status

Imported only. **Nothing has been implemented against it**, and `web/` is still
empty apart from the committed brand assets. Building the interface is ticket 6
in `docs/backlog.md`, which depends on tickets 2-5 (the agent and the HTTP API)
landing first.
