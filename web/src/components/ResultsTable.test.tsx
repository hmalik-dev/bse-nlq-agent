import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { ResultsTable } from "./ResultsTable";

function bodyRows(): HTMLTableRowElement[] {
  const [, ...rows] = screen.getAllByRole("row") as HTMLTableRowElement[];
  return rows;
}

describe("ResultsTable row dividers", () => {
  it.each([
    { name: "2 columns", columns: ["category", "revenue"], row: (i: number) => [`Cat ${i}`, i * 100] },
    { name: "3 columns", columns: ["event", "category", "revenue"], row: (i: number) => [`Event ${i}`, "Concert", i * 100] },
  ])("draws one full-width divider per row and drops it on the last row ($name)", ({ columns, row }) => {
    render(<ResultsTable columns={columns} rows={[1, 2, 3].map(row)} />);
    const rows = bodyRows();
    expect(rows).toHaveLength(3);
    for (const tableRow of rows) {
      expect(tableRow.className.split(" ")).toEqual(["border-b", "border-hairline", "last:border-b-0"]);
    }
    const cellClasses = rows.flatMap((tableRow) => Array.from(tableRow.cells, (cell) => cell.className.split(" ")));
    expect(cellClasses).toHaveLength(3 * columns.length);
    for (const classes of cellClasses) {
      expect(classes).not.toContain("border-b");
      expect(classes).not.toContain("last:border-b-0");
    }
  });
});
