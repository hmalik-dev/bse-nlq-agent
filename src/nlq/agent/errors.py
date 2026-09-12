"""The failures the agent can produce, each with a code the API and UI show.

Repairable errors are the ones worth sending back to the model: it wrote
something the database rejected and can try again. The rest are final.
"""

from __future__ import annotations


class NlqError(Exception):
    """Base class for every failure the agent reports to its caller."""

    code: str = "nlq_error"
    repairable: bool = False

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class UnsafeSql(NlqError):
    """The statement was write-shaped or otherwise out of bounds. Never retried."""

    code = "unsafe_sql"


class InvalidSql(NlqError):
    """The statement does not parse, or names a table the schema does not have."""

    code = "invalid_sql"
    repairable = True


class QueryFailed(NlqError):
    """SQLite refused to run the statement; `message` is SQLite's own wording."""

    code = "query_failed"
    repairable = True


class QueryTimeout(NlqError):
    """The query ran past its deadline and was interrupted."""

    code = "query_timeout"


class DatabaseMissing(NlqError):
    """There is no database file to read. Run the seed."""

    code = "database_missing"


class ApiKeyError(NlqError):
    """No usable Anthropic API key: unset, empty, or rejected by the API."""

    code = "missing_api_key"


class ModelRateLimited(NlqError):
    """The API refused the call because the account is over its rate limit."""

    code = "rate_limited"


class ModelTimeout(NlqError):
    """The API did not answer in time, or could not be reached at all."""

    code = "model_timeout"


class ModelRefused(NlqError):
    """The model stopped without producing a plan that fits the schema.

    The API still returned and billed a response, so the tokens it used ride
    along for the trace; an SDK failure with no response has nothing to carry.
    """

    code = "model_refused"

    def __init__(self, message: str, *, input_tokens: int = 0, output_tokens: int = 0) -> None:
        super().__init__(message)
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens


class ModelError(NlqError):
    """Any other failure the API reported."""

    code = "model_error"
