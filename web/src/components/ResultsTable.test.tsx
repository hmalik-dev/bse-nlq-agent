import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { ResultsTable } from "./ResultsTable";
import { ONE_VALUE } from "../test-fixtures";

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

describe("ResultsTable alignment", () => {
  it("puts a lone column's header and value on the same side", () => {
    render(<ResultsTable columns={ONE_VALUE.columns} rows={ONE_VALUE.rows} />);
    const header = screen.getByRole("columnheader", { name: "tickets sold" });
    const cell = screen.getByRole("cell", { name: "1,204,880" });
    for (const element of [header, cell]) {
      const classes = element.className.split(" ");
      expect(classes).toContain("text-left");
      expect(classes).not.toContain("num");
    }
    expect(cell.className.split(" ")).toContain("tabular-nums");
  });

  it("keeps numbers right-aligned when there is more than one column", () => {
    render(<ResultsTable columns={["year", "tickets_sold"]} rows={[[2024, 333707]]} />);
    expect(screen.getByRole("columnheader", { name: "tickets sold" }).className.split(" ")).toContain("num");
    expect(screen.getByRole("cell", { name: "333,707" }).className.split(" ")).toContain("num");
  });
});
