// One AskResult per status, shaped like the fake agent's answers. Test-only.
import type { AskResult, Trace } from "./types";

export const TRACE: Trace = {
  steps: [
    { name: "Reading schema", ms: 2 },
    { name: "Writing SQL", ms: 1240 },
    { name: "Checking safety", ms: 8 },
    { name: "Running query", ms: 18 },
    { name: "Writing answer", ms: 892 },
  ],
  repairs: 0,
  model: "fake",
  total_ms: 2160,
  input_tokens: 9800,
  output_tokens: 310,
  cost_usd: 0.0227,
};

const BASE: AskResult = {
  status: "answered",
  question: "Top 5 event categories by total revenue",
  answer: "NBA games brought in the most revenue at $118.4M.",
  assumptions: ["Revenue is the face value of sold tickets."],
  sql: "-- revenue by category\nSELECT e.category, SUM(t.price) AS revenue\nFROM tickets AS t\nWHERE t.status = 'sold'\nGROUP BY e.category",
  columns: ["category", "revenue"],
  rows: [
    ["NBA", 118400215.5],
    ["Concert", 61204880],
    ["WNBA", 12910332.25],
  ],
  row_count: 3,
  truncated: false,
  chart: { type: "bar", x: "category", y: "revenue" },
  trace: TRACE,
  error: null,
  suggestions: [],
};

export const ANSWERED: AskResult = BASE;

export const NETS: AskResult = {
  ...BASE,
  question: "nets tickets last month",
  answer: "Nets home games sold 35,464 tickets in August 2026.",
  sql: "SELECT e.name AS event, COUNT(*) AS tickets_sold\nFROM tickets AS t\nGROUP BY e.event_id",
  columns: ["event", "event_date", "tickets_sold", "avg_price"],
  rows: [
    ["Brooklyn Nets vs. New York Knicks", "2026-10-24", 17732, 214.6],
    ["Brooklyn Nets vs. Boston Celtics", "2026-10-31", 17732, 198.25],
  ],
  row_count: 2,
  chart: null,
  trace: { ...TRACE, repairs: 1 },
};

export const EMPTY: AskResult = {
  ...BASE,
  status: "empty",
  question: "nothing",
  answer: "",
  columns: ["name", "event_date"],
  rows: [],
  row_count: 0,
  chart: null,
  suggestions: ["Try a wider date range", "Try a different category"],
};

export const UNANSWERABLE: AskResult = {
  ...BASE,
  status: "unanswerable",
  question: "What's the weather?",
  answer: "The data holds no weather information.",
  assumptions: [],
  sql: null,
  columns: [],
  rows: [],
  row_count: 0,
  chart: null,
  suggestions: ["Top 5 event categories by total revenue"],
};

export const BLOCKED: AskResult = {
  ...UNANSWERABLE,
  status: "blocked",
  question: "Delete all ticket records",
  answer: "That request was refused before it ran. The connection is read-only.",
  sql: "DELETE FROM tickets",
  suggestions: [],
};

export const ERROR: AskResult = {
  ...UNANSWERABLE,
  status: "error",
  question: "rate limit",
  answer: "",
  suggestions: [],
  error: { code: "rate_limited", message: "The model is rate limited right now." },
};

export const BY_STATUS: Record<AskResult["status"], AskResult> = {
  answered: ANSWERED,
  empty: EMPTY,
  unanswerable: UNANSWERABLE,
  blocked: BLOCKED,
  error: ERROR,
};

export const EXAMPLES = [
  { question: "How many tickets did we sell for Nets home games last month?", badge: "nets" as const },
  { question: "Top 5 event categories by total revenue", badge: null },
  { question: "Which 2024 events had the highest average ticket price?", badge: null },
  { question: "Which Liberty home games sold the most tickets this season?", badge: "liberty" as const },
  { question: "How much revenue did refunds cost us last season?", badge: null },
  { question: "Compare web and box office sales for concerts", badge: null },
];

/** A Response the way fetch would hand it back. */
export function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}
