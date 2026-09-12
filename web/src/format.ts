import type { Cell } from "./types";

const MONEY_COLUMN = /price|revenue|gate|fee|cost/i;
const thousands = new Intl.NumberFormat("en-US", { maximumFractionDigits: 2 });
const dollars = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

/** A column whose name says it holds money, so its numbers render as dollars. */
export function isMoneyColumn(name: string): boolean {
  return MONEY_COLUMN.test(name);
}

/** A column is numeric when every non-null value in it is a number. */
export function isNumericColumn(rows: Cell[][], index: number): boolean {
  const values = rows.map((row) => row[index]).filter((value) => value !== null && value !== undefined);
  return values.length > 0 && values.every((value) => typeof value === "number");
}

/** Thousands separators, or dollars with cents for a money column. */
export function formatNumber(value: number, money = false): string {
  return money ? dollars.format(value) : thousands.format(value);
}

/** One table cell as text: numbers formatted by column, nulls as a dash, the rest as-is. */
export function formatCell(value: Cell, column: string): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "number") return formatNumber(value, isMoneyColumn(column));
  return String(value);
}

/** Milliseconds as seconds: `2160` -> `2.2s` with one decimal, `2.16s` with two. */
export function formatSeconds(ms: number, decimals = 1): string {
  return `${(ms / 1000).toFixed(decimals)}s`;
}

/** `gate_revenue` -> `Gate revenue`, for chart titles. */
export function humanize(column: string): string {
  const words = column.replace(/_/g, " ").trim();
  return words.charAt(0).toUpperCase() + words.slice(1);
}
