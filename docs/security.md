# Security

BSE Insights runs on one person's machine with their own Anthropic key, and answering only reads the database.

- **The model is tricked into writing data or reading files.** A check allows one query over the app's tables, and the database is read-only, so fooling the check writes nothing.
- **A query is huge or endless.** Long questions are refused; queries stop at time and size limits.
- **Text runs as code.** The answer model only writes text; text stays text on screen and in exports, with spreadsheet formulas disarmed.
- **An error leaks detail.** The screen shows fixed sentences, and garbled model replies never run.
- **Another website drives the app.** It accepts only local requests of a kind other sites cannot send, and loads no outside scripts.
- **The server overreaches.** It serves only its own files, runs as an ordinary user, and the documented commands keep it local.
- **The key leaks.** It lives only in the environment, never in a response, a log or the container image.

Each of these has a test that fails if it breaks.

## Accepted risks

- **No login, rate limit or spending cap.** Its one user can cap their own key with Anthropic.
- **A failed repair returns the database's error text.** It describes the query, never a file, and never reaches the screen.
- **Requests have no size limit, and a rejected one is echoed.** It never reaches the model, and other sites cannot read it.
