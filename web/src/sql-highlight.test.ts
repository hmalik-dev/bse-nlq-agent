import { describe, expect, it } from "vitest";
import { highlight, tokenize } from "./sql-highlight";

describe("tokenize", () => {
  it("marks keywords in any case and leaves identifiers as text", () => {
    expect(tokenize("SELECT e.category from tickets")).toEqual([
      { kind: "keyword", text: "SELECT" },
      { kind: "text", text: " " },
      { kind: "text", text: "e" },
      { kind: "text", text: "." },
      { kind: "text", text: "category" },
      { kind: "text", text: " " },
      { kind: "keyword", text: "from" },
      { kind: "text", text: " " },
      { kind: "text", text: "tickets" },
    ]);
  });

  it("keeps a quoted string as one token, including an escaped quote", () => {
    const tokens = tokenize("WHERE t.status = 'sold' AND h.name = 'O''Neil'");
    expect(tokens.filter((token) => token.kind === "string").map((token) => token.text)).toEqual([
      "'sold'",
      "'O''Neil'",
    ]);
  });

  it("treats a -- comment as one token to the end of the line", () => {
    expect(tokenize("  -- events after today, 'quoted' or not")).toEqual([
      { kind: "text", text: "  " },
      { kind: "comment", text: "-- events after today, 'quoted' or not" },
    ]);
  });

  it("does not color a keyword inside an identifier", () => {
    const tokens = tokenize("ORDER BY tickets_sold DESC");
    expect(tokens.map((token) => token.kind)).toEqual(["keyword", "text", "keyword", "text", "text", "text", "keyword"]);
  });
});

describe("highlight", () => {
  it("returns one token list per line, in order", () => {
    const lines = highlight("SELECT 1\nFROM t");
    expect(lines).toHaveLength(2);
    expect(lines[0]?.[0]).toEqual({ kind: "keyword", text: "SELECT" });
    expect(lines[1]?.[0]).toEqual({ kind: "keyword", text: "FROM" });
  });
});
