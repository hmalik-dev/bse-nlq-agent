// One sentence per API error code. The codes are the contract; an unknown code gets the generic line.
const COPY: Record<string, string> = {
  rate_limited: "Asking is paused until the service responds.",
  missing_api_key: "The service is not configured with an API key.",
  model_timeout: "The service did not respond. Try again.",
  network: "The service did not respond. Try again.",
  query_timeout: "That question took too long to run. Try narrowing it.",
  repairs_exhausted: "The generated query kept failing. Try rewording.",
  database_missing: "The database has not been generated yet. Run `uv run python -m nlq.db.seed`, then try again.",
  usage_exhausted: "This demo has used up its usage allowance. Nothing is broken; asking works again once it is topped up.",
};
export const GENERIC_ERROR = "Something went wrong.";

/** What the error card says for a given `error.code`. Never the raw message from the server. */
export function errorCopy(code: string): string {
  return COPY[code] ?? GENERIC_ERROR;
}
