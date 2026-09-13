import type { AskResult, ExampleQuestion, Health, Schema } from "./types";

const API = "/api";
const NETWORK_MESSAGE = "Could not reach the server. Check that it is running and try again.";

/** Ask one question. Never throws: a failed request becomes an error result with code `network`. */
export async function ask(question: string): Promise<AskResult> {
  try {
    const response = await fetch(`${API}/ask`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    });
    if (!response.ok) return networkError(question, `The server answered ${response.status}.`);
    return (await response.json()) as AskResult;
  } catch {
    return networkError(question, NETWORK_MESSAGE);
  }
}

/** The six starter questions for the chips. */
export async function examples(): Promise<ExampleQuestion[]> {
  return getJson<ExampleQuestion[]>(`${API}/examples`);
}

/** The tables, columns and business definitions for the schema drawer. */
export async function schema(): Promise<Schema> {
  return getJson<Schema>(`${API}/schema`);
}

/** Whether the server has an API key. A failed check counts as yes: asking then reports its own error. */
export async function hasApiKey(): Promise<boolean> {
  try {
    const health = await getJson<Health>(`${API}/health`);
    return health.api_key;
  } catch {
    return true;
  }
}

async function getJson<T>(url: string): Promise<T> {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`GET ${url} answered ${response.status}`);
  return (await response.json()) as T;
}

function networkError(question: string, message: string): AskResult {
  return {
    status: "error",
    question,
    answer: "",
    assumptions: [],
    sql: null,
    columns: [],
    rows: [],
    row_count: 0,
    truncated: false,
    chart: null,
    trace: {
      steps: [],
      repairs: 0,
      model: "",
      total_ms: 0,
      input_tokens: 0,
      output_tokens: 0,
      cost_usd: 0,
    },
    error: { code: "network", message },
    suggestions: [],
  };
}
