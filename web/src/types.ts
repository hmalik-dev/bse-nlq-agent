// Mirrors src/nlq/agent/models.py field for field. The API serialises AskResult unchanged.

export type Status = "answered" | "empty" | "unanswerable" | "blocked" | "error";

export type Cell = string | number | boolean | null;

export interface Step {
  name: string;
  ms: number;
}

export interface Trace {
  steps: Step[];
  repairs: number;
  model: string;
  total_ms: number;
  input_tokens: number;
  output_tokens: number;
  cost_usd: number;
}

export interface ChartSpec {
  type: "bar";
  x: string;
  y: string;
}

export interface ErrorInfo {
  code: string;
  message: string;
}

export interface AskResult {
  status: Status;
  question: string;
  answer: string;
  assumptions: string[];
  sql: string | null;
  columns: string[];
  rows: Cell[][];
  row_count: number;
  truncated: boolean;
  chart: ChartSpec | null;
  trace: Trace;
  error: ErrorInfo | null;
  suggestions: string[];
}

export type Badge = "nets" | "liberty";

export interface ExampleQuestion {
  question: string;
  badge: Badge | null;
}

export interface ColumnInfo {
  name: string;
  type: string;
  description: string;
}

export interface TableInfo {
  name: string;
  description: string;
  columns: ColumnInfo[];
}

export interface Schema {
  tables: TableInfo[];
  definitions: string[];
}
