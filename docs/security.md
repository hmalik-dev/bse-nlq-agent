# Security

How BSE Insights stays safe when a user, the model or a dependency sends something
hostile. It is a local, single-user tool run with the user's own key. Every
control has a test that fails if the control breaks.

## Boundaries

| Boundary | Threat | Control | Test that proves it |
|---|---|---|---|
| Question → SQL writer | Prompt injection talks the model into a write | The prompt treats a message as one request and declines a smuggled write whole, but the prompt is not the control: whatever the model writes still meets the guard and a read-only connection. The golden set's three injections measure the prompt; they cannot prove it | `tests/test_agent.py::test_blocked_by_the_guard_keeps_the_rejected_statement`, the guard and connection rows below |
| Question → SQL writer | An enormous question runs up tokens | Length cap (`NLQ_MAX_QUESTION_CHARS`, 500) on the API and the CLI | `tests/test_api.py::test_ask_rejects_a_malformed_body_with_422_before_the_agent_runs`, `tests/test_ask.py::test_a_question_over_the_length_cap_is_refused_before_the_agent_runs` |
| SQL writer → agent | Off-schema output is used as a plan | `SqlPlan` is validated; an invalid plan is `model_refused`, never run | `tests/test_models.py::test_an_answerable_plan_needs_sql`, `tests/test_agent.py::test_a_plan_that_fails_validation_is_still_priced`, `::test_a_plan_that_fails_validation_reaches_the_caller_as_a_fixed_sentence` |
| Rows → answer writer | Text in a row steers the answer | The answer writer has no tools and no SQL; its output is only ever text | `tests/test_answer.py::test_the_call_carries_the_system_prompt_and_one_user_turn`, `web/src/App.test.tsx > renders markup in a question, the answer and a cell as text in the answer, table and rail` |
| Model SQL → database | A write, `ATTACH`, `PRAGMA`, `VACUUM INTO` | The guard accepts one `SELECT` with no write node anywhere in the tree | `tests/test_sql_guard.py::test_attach_is_refused`, `::test_pragma_is_refused`, `::test_vacuum_into_a_file_is_refused`, `::test_a_write_hidden_in_a_cte_is_refused` |
| Model SQL → database | Stacked statements and comment tricks | Exactly one parsed statement | `tests/test_sql_guard.py::test_a_second_statement_is_refused`, `::test_comment_and_statement_tricks_never_get_a_write_through` |
| Model SQL → database | `load_extension`, `readfile`, `writefile` | Banned functions, matched on the unquoted name | `tests/test_sql_guard.py::test_a_filesystem_function_is_refused`, `::test_a_quoted_function_name_does_not_slip_past_the_list` |
| Model SQL → database | A CTE or alias shadows the table allowlist | Only a table named after a CTE in its own scope is exempt, never an alias | `tests/test_sql_guard.py::test_a_shadowing_cte_cannot_smuggle_a_table_past_the_allowlist`, `::test_an_alias_shared_with_a_subquery_or_cte_cannot_smuggle_a_table_past_the_allowlist` |
| Model SQL → database | The guard is bypassed entirely | `mode=ro` connection (path percent-encoded) plus `PRAGMA query_only` | `tests/test_executor.py::test_the_connection_itself_refuses_a_write_with_the_guard_and_query_only_both_gone`, `::test_the_connection_opens_with_query_only_on`, `::test_a_database_path_with_uri_characters_still_opens_read_only` |
| Model SQL → database | A recursive CTE or cartesian join runs forever | 5 s deadline through the progress handler, checked between SQLite steps; one function call over a value is a single step, which the 100 KB value limit keeps short | `tests/test_executor.py::test_a_runaway_query_is_stopped_at_the_deadline`, `::test_a_cartesian_join_over_tickets_is_stopped_at_the_deadline` |
| Model SQL → database | A huge result exhausts memory | `LIMIT max_rows + 1`; SQLite limits of 100 KB per value and 100 columns, so one row holds at most 10 MB; 8 MB across the result | `tests/test_sql_guard.py::test_a_missing_limit_is_appended_and_the_original_text_is_kept`, `tests/test_executor.py::test_a_cartesian_join_returning_rows_stops_at_the_row_cap`, `::test_a_value_over_the_length_limit_fails_inside_sqlite_before_python_holds_it`, `::test_a_result_wider_than_the_column_limit_is_refused`, `::test_the_widest_row_sqlite_allows_stays_within_twice_the_result_budget`, `::test_rows_that_add_up_past_the_byte_budget_are_refused_rather_than_held_in_memory` |
| API | A malformed body | Pydantic validation, 422 before the agent runs | `tests/test_api.py::test_ask_rejects_a_malformed_body_with_422_before_the_agent_runs` |
| API | A stack, path, SDK or validation message in a response | Fixed sentences per error code; detail goes to the log | `tests/test_api.py::test_an_agent_that_raises_becomes_an_internal_error_without_the_detail`, `::test_a_missing_database_reaches_the_client_without_the_server_path`, `tests/test_llm.py::test_a_model_error_hides_the_sdk_text_and_logs_it_once`, `tests/test_agent.py::test_a_plan_that_fails_validation_reaches_the_caller_as_a_fixed_sentence` |
| API | Static serving reads outside `static_dir` | Resolve, then 404 for anything outside (`..`, `%2e%2e%2f`, absolute, symlink) | `tests/test_api.py::test_a_path_that_climbs_out_of_the_static_directory_is_a_404`, `::test_an_absolute_path_is_a_404_not_the_file_it_names`, `::test_a_symlink_pointing_out_of_the_static_directory_is_a_404` |
| API | Another website drives `/api/ask` (CSRF, DNS rebinding) | No CORS headers; JSON body required; `Host` must be `localhost` or `127.0.0.1` (`NLQ_ALLOWED_HOSTS`) | `tests/test_api.py::test_a_cross_site_form_post_is_refused_before_the_agent_runs`, `::test_a_foreign_host_header_is_refused_before_the_agent_runs`, `::test_the_allowed_hosts_are_read_from_the_environment` |
| Secrets | The API key reaches a response, the trace or a log | Read from the environment only, sent only to Anthropic | `tests/test_secrets.py::test_the_key_never_reaches_a_response_the_trace_or_a_log`, `tests/test_golden.py::test_an_injection_refusal_echoes_neither_the_prompt_nor_the_api_key` |
| Secrets | The key reaches the image | `.dockerignore` excludes `.env*` at any depth; the Dockerfile never names the key | `tests/test_ship.py::test_env_files_and_secrets_are_kept_out_of_the_build_context`, `::test_the_dockerfile_never_names_the_key` |
| Browser | Model or row text executes as HTML | No `dangerouslySetInnerHTML`; React renders text; the SQL highlighter emits tokens, not markup | `web/src/App.test.tsx > renders markup in a question, the answer and a cell as text in the answer, table and rail`, `web/src/components/SqlBlock.test.tsx > renders markup in the statement as text, never as an element` |
| Browser | CSV export runs a formula | A leading `= + - @ tab CR` gets a `'`; `;` is quoted | `web/src/export.test.ts > defuses a string that a spreadsheet would run as a formula`, `> quotes a semicolon so a locale that splits on it cannot start a formula mid-cell` |
| Browser | Exported SVG carries script | Serialized by `XMLSerializer`, so text is escaped | `web/src/export.test.ts > escapes markup in a label, so the file carries no script and no live element` |
| Container | The server runs as root | `USER nlq` (uid 10001); only `/data` is writable, and a root-owned volume from an older image stops start-up with a fix to run | `tests/test_ship.py::test_the_container_runs_as_a_user_that_is_not_root`, `::test_the_entrypoint_explains_an_unwritable_data_directory_instead_of_seeding` |
| API | A third-party script runs on the app's origin | No Swagger UI or ReDoc, which load theirs from a CDN | `tests/test_api.py::test_the_interactive_docs_are_not_served` |
| Container | The port is open to the network | The README runs `-p 127.0.0.1:8000:8000` | `tests/test_ship.py::test_every_documented_docker_run_publishes_the_port_on_loopback_only` |

## Findings fixed in BSE-23

1. An alias shared with a subquery got `sqlite_master` past the allowlist.
2. One huge value (`hex(zeroblob(...))`) could exhaust memory before the byte cap.
3. Any `Host` header was accepted, so a DNS-rebinding page could spend the key.
4. A `#` or `?` in the database path dropped `mode=ro`.
5. An escaping static path got the index page instead of a 404.
6. The CLI had no question length cap.
7. The container ran as root.

## Findings fixed in BSE-30

1. One `instr` over a 1 MB value ran past the deadline, and one 100-column row held
   hundreds of megabytes before the 8 MB budget refused it.
2. A plan that failed validation sent pydantic's text, with the model's output, to the client.
3. `/docs` loaded Swagger UI's script from a CDN onto the app's origin.
4. `.dockerignore` kept `.env*` out only at the repository root.

## Accepted risks

- **No auth, rate limit or spend guard.** One user on their own machine with
  their own key; a spend cap on the key in the Anthropic console is the outer layer.
- **No request body size cap, and a 422 echoes the input.** Any page can send a
  large body, but it is refused before the agent runs and the page cannot read the echo.
- **`/openapi.json` is served.** It describes the routes already documented in
  `docs/design.md`, and loads nothing.
- **SQLite's and the SQL parser's error text reach `repairs_exhausted`.** It is wording
  about the model's query, never a path, and the repair loop needs it.
- **A dev-only advisory in `@vitest/mocker`** (GHSA-82fw-gwwq-j7x9). It is in the test
  runner, which never ships; `npm audit --omit=dev` and `pip-audit` are clean.
