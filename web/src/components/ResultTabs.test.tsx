import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ResultTabs } from "./ResultTabs";
import * as exporter from "../export";
import { serializeChart } from "../export";
import { ANSWERED, EMPTY, NETS } from "../test-fixtures";

describe("ResultTabs", () => {
  it("shows Results, SQL and Chart with Results selected by default", () => {
    render(<ResultTabs result={ANSWERED} />);
    const tabs = screen.getAllByRole("tab");
    expect(tabs.map((tab) => tab.textContent)).toEqual(["Results", "SQL", "Chart"]);
    expect(tabs[0]?.getAttribute("aria-selected")).toBe("true");
    expect(screen.getByRole("tabpanel").querySelector("table")).not.toBeNull();
  });

  it("omits the Chart tab when chart is null", () => {
    render(<ResultTabs result={NETS} />);
    expect(screen.getAllByRole("tab").map((tab) => tab.textContent)).toEqual(["Results", "SQL"]);
    expect(screen.queryByRole("tab", { name: "Chart" })).toBeNull();
  });

  it("moves selection with the arrow keys and wraps at the ends", async () => {
    const user = userEvent.setup();
    render(<ResultTabs result={ANSWERED} />);
    const [results, sql, chart] = screen.getAllByRole("tab");
    results?.focus();
    await user.keyboard("{ArrowRight}");
    expect(sql?.getAttribute("aria-selected")).toBe("true");
    expect(document.activeElement).toBe(sql);
    await user.keyboard("{ArrowRight}{ArrowRight}");
    expect(results?.getAttribute("aria-selected")).toBe("true");
    await user.keyboard("{End}");
    expect(chart?.getAttribute("aria-selected")).toBe("true");
    expect(screen.getByRole("tabpanel").getAttribute("aria-labelledby")).toBe("tab-chart");
  });

  it("renders the chart as SVG with one bar per row, the largest emphasised", async () => {
    const user = userEvent.setup();
    render(<ResultTabs result={ANSWERED} />);
    await user.click(screen.getByRole("tab", { name: "Chart" }));
    const bars = screen.getAllByRole("img");
    expect(bars).toHaveLength(3);
    expect(bars.every((bar) => bar.tagName === "rect")).toBe(true);
    expect(bars[0]?.getAttribute("fill-opacity")).toBe("1");
    expect(bars[1]?.getAttribute("fill-opacity")).toBe("0.7");
    expect(bars[0]?.getAttribute("aria-label")).toBe("NBA: $118,400,215.50");
    expect(Number(bars[1]?.getAttribute("width"))).toBeLessThan(Number(bars[0]?.getAttribute("width")));
    expect(screen.getByText("Revenue by category")).toBeTruthy();
    expect(screen.getByText("$118,400,215.50")).toBeTruthy();
    expect(screen.getByText("Concert")).toBeTruthy();
    expect(screen.getByText("$0")).toBeTruthy();
    expect(screen.getByText("$118.4M")).toBeTruthy();
  });

  it("serializes the chart as a standalone SVG whose colors do not depend on classes", async () => {
    const user = userEvent.setup();
    render(<ResultTabs result={ANSWERED} />);
    await user.click(screen.getByRole("tab", { name: "Chart" }));
    const svg = screen.getByRole("group", { name: "Revenue by category" }) as unknown as SVGSVGElement;
    const file = new DOMParser().parseFromString(serializeChart(svg), "image/svg+xml").documentElement;
    expect(file.getAttribute("xmlns")).toBe("http://www.w3.org/2000/svg");
    expect(file.firstElementChild?.getAttribute("fill")).toBe("#16161A");
    const bars = file.querySelectorAll("[data-bar]");
    expect(bars).toHaveLength(ANSWERED.rows.length);
    expect(file.querySelectorAll("[data-largest]")).toHaveLength(1);
    expect(bars[0]?.hasAttribute("data-largest")).toBe(true);
    expect(bars[0]?.getAttribute("fill")).toBe("#87D5B5");
    expect(file.textContent).toContain("Revenue by category");
    expect(file.querySelectorAll("[class]")).toHaveLength(0);
  });

  it("shows the row count and Export CSV only on the Results tab, Download SVG only on Chart", async () => {
    const user = userEvent.setup();
    render(<ResultTabs result={ANSWERED} />);
    expect(screen.getByText("3 rows")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Export CSV" }).getAttribute("title")).toBe("Download 3 rows as CSV");
    expect(screen.queryByRole("button", { name: "Download SVG" })).toBeNull();
    await user.click(screen.getByRole("tab", { name: "Chart" }));
    expect(screen.queryByRole("button", { name: "Export CSV" })).toBeNull();
    expect(screen.queryByText("3 rows")).toBeNull();
    expect(screen.getByRole("button", { name: "Download SVG" })).toBeTruthy();
    await user.click(screen.getByRole("tab", { name: "SQL" }));
    expect(screen.queryByRole("button", { name: /Export CSV|Download SVG/ })).toBeNull();
  });

  it("exports exactly the rows the table shows, under a slug of the question", async () => {
    const user = userEvent.setup();
    const download = vi.spyOn(exporter, "downloadFile").mockImplementation(() => undefined);
    const truncated = { ...ANSWERED, row_count: 5000, truncated: true };
    render(<ResultTabs result={truncated} />);
    const button = screen.getByRole("button", { name: "Export CSV" });
    expect(button.getAttribute("title")).toBe("Contains the first 3 rows");
    await user.click(button);
    expect(download).toHaveBeenCalledWith(
      "top-5-event-categories-by-total-revenue.csv",
      "category,revenue\r\nNBA,118400215.5\r\nConcert,61204880\r\nWNBA,12910332.25\r\n",
      "text/csv;charset=utf-8",
    );
    await user.click(screen.getByRole("tab", { name: "Chart" }));
    await user.click(screen.getByRole("button", { name: "Download SVG" }));
    const [name, svg, type] = download.mock.calls[1] ?? [];
    expect([name, type]).toEqual(["top-5-event-categories-by-total-revenue.svg", "image/svg+xml"]);
    expect(svg).toContain('fill="#16161A"');
    download.mockRestore();
  });

  it("offers no export on an empty result, which opens on SQL", () => {
    render(<ResultTabs result={EMPTY} />);
    expect(screen.getByRole("tab", { name: "SQL" }).getAttribute("aria-selected")).toBe("true");
    expect(screen.getByText("0 rows")).toBeTruthy();
    expect(screen.queryByRole("button", { name: /Export CSV|Download SVG/ })).toBeNull();
  });

  it("formats the table by column and badges Nets rows", () => {
    render(<ResultTabs result={NETS} />);
    expect(screen.getByText("$214.60")).toBeTruthy();
    expect(screen.getAllByText("17,732")[0]?.className).toContain("num");
    expect(document.querySelectorAll("[data-badge=nets]")).toHaveLength(2);
    expect(screen.getByRole("region", { name: "Results table" }).tabIndex).toBe(0);
    expect(screen.getByText("fake · 2.2s · repaired once")).toBeTruthy();
  });
});
