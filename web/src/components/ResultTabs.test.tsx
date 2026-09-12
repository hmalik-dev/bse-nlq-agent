import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ResultTabs } from "./ResultTabs";
import { ANSWERED, NETS } from "../test-fixtures";

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

  it("renders the chart with one bar per row, the largest emphasised", async () => {
    const user = userEvent.setup();
    render(<ResultTabs result={ANSWERED} />);
    await user.click(screen.getByRole("tab", { name: "Chart" }));
    const bars = screen.getAllByRole("img");
    expect(bars).toHaveLength(3);
    expect(bars[0]?.className).not.toContain("opacity-70");
    expect(bars[1]?.className).toContain("opacity-70");
    expect(screen.getByText("Revenue by category")).toBeTruthy();
    expect(screen.getByText("$118,400,215.50")).toBeTruthy();
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
