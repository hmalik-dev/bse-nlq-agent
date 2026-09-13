# design-plan

How to open the Claude Design canvas the interface was built from. It is a style
reference; tokens, frames and parity rules are in `docs/design.md`.

`BSE Insights.dc.html` needs `support.js` (generated, never edit) served beside
it, so open it over HTTP, not `file://`:

```sh
cd design-plan && python3 -m http.server 8100
# then open http://localhost:8100/BSE%20Insights.dc.html
```

Nothing here is imported at runtime. The source project is
<https://claude.ai/design/p/b0d8463a-c312-492f-b20f-e17b649cb5ef>.
