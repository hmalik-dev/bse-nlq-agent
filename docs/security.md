# Security

BSE Insights runs on one person's machine with their own Anthropic key, and it can only read the database.

- **A question tricks the model into changing data.** A check allows one read-only query, and the database is opened read-only, so fooling the check still cannot write.
- **A question or query is huge or never ends.** Long questions are refused; queries stop at a time limit and a size limit.
- **Text runs as code.** Text from the data, the model or a question is shown as text, on screen and in exports, where spreadsheet formulas are disarmed.
- **An error reveals internal detail.** Errors come back as fixed sentences, and a garbled model reply is refused, never run.
- **Another website drives the app or spends the key.** The app answers only requests addressed to this machine and loads no outside scripts.
- **The server reaches past its job.** It serves only its own files, runs as an ordinary user, and listens only on this machine.
- **The key leaks.** It lives only in the environment and never reaches a response, a log or the container image.

Each of these has a test that fails if it breaks.

## Accepted risks

- **No login, rate limit or spending cap in the app.** One person runs it with their own key, capped in the Anthropic console.
- **Database wording about the model's own query is shown.** It never names a file, and repairs need it.
