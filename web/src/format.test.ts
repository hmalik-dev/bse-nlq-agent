import { describe, expect, it } from "vitest";
import { formatCell, formatNumber, formatSeconds, humanize, isMoneyColumn, isNumericColumn } from "./format";

describe("formatNumber", () => {
  it("adds thousands separators and keeps at most two decimals", () => {
    expect(formatNumber(17732)).toBe("17,732");
    expect(formatNumber(1234.5678)).toBe("1,234.57");
    expect(formatNumber(0)).toBe("0");
  });

  it("renders money as dollars with cents", () => {
    expect(formatNumber(1234.5, true)).toBe("$1,234.50");
    expect(formatNumber(118400215.5, true)).toBe("$118,400,215.50");
  });
});

describe("isMoneyColumn", () => {
  it.each(["price", "avg_price", "revenue", "gate_revenue", "fee", "total_cost"])("detects %s", (name) => {
    expect(isMoneyColumn(name)).toBe(true);
  });

  it.each(["tickets_sold", "category", "event_date"])("leaves %s alone", (name) => {
    expect(isMoneyColumn(name)).toBe(false);
  });
});

describe("isNumericColumn", () => {
  const rows = [
    ["NBA", 10, null],
    ["Concert", 20, "x"],
  ];
  it("is true only when every non-null value is a number", () => {
    expect(isNumericColumn(rows, 0)).toBe(false);
    expect(isNumericColumn(rows, 1)).toBe(true);
    expect(isNumericColumn(rows, 2)).toBe(false);
    expect(isNumericColumn([], 0)).toBe(false);
  });
});

describe("formatCell", () => {
  it("formats by column, dashes nulls and passes text through", () => {
    expect(formatCell(214.6, "avg_price")).toBe("$214.60");
    expect(formatCell(17732, "tickets_sold")).toBe("17,732");
    expect(formatCell(null, "anything")).toBe("—");
    expect(formatCell("2026-10-24", "event_date")).toBe("2026-10-24");
  });
});

describe("formatSeconds and humanize", () => {
  it("renders milliseconds as seconds", () => {
    expect(formatSeconds(2160)).toBe("2.2s");
    expect(formatSeconds(2160, 2)).toBe("2.16s");
    expect(formatSeconds(0)).toBe("0.0s");
  });

  it("turns a column name into a label", () => {
    expect(humanize("gate_revenue")).toBe("Gate revenue");
    expect(humanize("category")).toBe("Category");
  });
});
