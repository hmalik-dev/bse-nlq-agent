---
name: review-checklist-model-client
description: Review checklist row — verify Anthropic SDK surface and fake-client fidelity against the installed package, not from memory of the API
metadata:
  type: feedback
---

When a diff calls the Anthropic SDK or fakes it, verify the surface against the
installed package under `.venv/lib/python3.*/site-packages/anthropic/` before
reporting drift. Cheap checks that settled a whole review of BSE-4's `llm.py`:

- `resources/messages/messages.py::parse` — kwarg names (`output_format`,
  `output_config`) and that it is keyword-only.
- `types/parsed_message.py` — `parsed_output` is a property over text blocks, so
  a fake needs `parsed_output`, `content`, `usage`, `stop_reason`, `model`.
- `lib/_parse/_response.py::parse_text` — invalid model JSON raises
  `pydantic.ValidationError` from inside `parse`, so the caller needs a second
  `except` beside `anthropic.AnthropicError`.
- `lib/_parse/_transform.py` — unsupported JSON-schema keywords (`maxLength`,
  `maxItems`) are folded into the field description, not rejected; `"null"` is a
  supported type, so `str | None` fields are safe.
- `_exceptions.py` — `APITimeoutError` subclasses `APIConnectionError`, and the
  exception constructors a fake uses are `(message, *, response, body)` for
  status errors and `(request=…)` for connection errors.
- `import httpx2` is **correct** in this environment — that is the module name
  the installed `anthropic` ships against, and `tests/fakes.py` on main already
  uses it. Do not report it as a typo for `httpx`; grep the base ref first.

**Why:** the repo's fake client is the only thing the tests exercise, so any
drift between it and the SDK ships as a runtime-only failure.

**How to apply:** one Bash call of greps over site-packages answers all of the
above; do it before writing a "fake drifts from the SDK" finding. See
[[review-checklist-sql-rewriting]].
