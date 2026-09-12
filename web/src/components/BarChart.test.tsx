import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { BarChart, chartLayout, wrapLabel } from "./BarChart";
import { ANSWERED, NETS } from "../test-fixtures";

describe("wrapLabel", () => {
  it("keeps a short label on one line", () => {
    expect(wrapLabel("Concert")).toEqual(["Concert"]);
  });

  it("wraps a long label at a word break and ends an overlong second line with an ellipsis", () => {
    expect(wrapLabel("Brooklyn Nets vs. New York Knicks")).toEqual(["Brooklyn Nets vs. New York", "Knicks"]);
    expect(wrapLabel("aaaa bbbb cccc dddd eeee", 9)).toEqual(["aaaa bbbb", "cccc ddd…"]);
  });
});

describe("chartLayout", () => {
  const MONEY_VALUE = "$118,400,215.50".length;
  const MONEY_TICK = "$118.4M".length;

  it("keeps the desktop geometry at a wide chart", () => {
    expect(chartLayout(816, MONEY_VALUE, MONEY_TICK)).toEqual({
      padX: 32,
      labelWidth: 180,
      labelGap: 20,
      labelChars: 27,
      span: (816 - 64 - 200) * 0.78,
      ticks: [0, 1 / 3, 2 / 3, 1],
    });
  });

  it("narrows the label column below 560px and leaves room for the longest value inside the card", () => {
    const layout = chartLayout(356, MONEY_VALUE, MONEY_TICK);
    expect(layout).toMatchObject({ padX: 16, labelWidth: 96, labelGap: 12, labelChars: 13, ticks: [0, 1] });
    const valueEnd = layout.padX + layout.labelWidth + layout.labelGap + layout.span + 12 + MONEY_VALUE * 8;
    expect(layout.span).toBeCloseTo(356 - 16 - 96 - 12 - 12 - MONEY_VALUE * 8);
    expect(valueEnd).toBeLessThanOrEqual(356);
  });

  it("drops to the two end ticks when four labels would overlap, and to the end alone when two would", () => {
    expect(chartLayout(560, MONEY_VALUE, MONEY_TICK).ticks).toHaveLength(4);
    const { span, ticks } = chartLayout(420, MONEY_VALUE, MONEY_TICK);
    expect(span / 3).toBeLessThan(MONEY_TICK * 7 + 12);
    expect(ticks).toEqual([0, 1]);
    expect(chartLayout(288, MONEY_VALUE, MONEY_TICK)).toMatchObject({ span: 32, ticks: [1] });
  });
});

describe("BarChart at phone width", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("draws the measured width with the narrow label column and only the two end ticks", () => {
    vi.stubGlobal(
      "ResizeObserver",
      class {
        report: ResizeObserverCallback;
        constructor(report: ResizeObserverCallback) {
          this.report = report;
        }
        observe(): void {
          this.report([{ contentRect: { width: 356 } } as ResizeObserverEntry], this as unknown as ResizeObserver);
        }
        disconnect(): void {}
      },
    );
    const { container } = render(<BarChart result={{ ...ANSWERED, rows: [["Brooklyn Nets games", 118400215.5], ["WNBA", 12910332.25]] }} />);
    expect(container.querySelector("svg")?.getAttribute("width")).toBe("356");
    expect(Array.from(container.querySelectorAll("[data-tick]"), (tick) => tick.textContent)).toEqual(["$0", "$118.4M"]);
    expect(Array.from(container.querySelectorAll("tspan"), (line) => line.textContent)).toEqual(["Brooklyn Nets", "games", "WNBA"]);
    expect(screen.getByRole("img", { name: "Brooklyn Nets games: $118,400,215.50" }).getAttribute("x")).toBe(String(16 + 96 + 12));
  });
});

describe("BarChart", () => {
  it("renders nothing without a chart spec", () => {
    const { container } = render(<BarChart result={NETS} />);
    expect(container.innerHTML).toBe("");
  });

  it("draws the bars in arrival order, scaled to the largest", () => {
    render(<BarChart result={ANSWERED} />);
    const labels = screen.getAllByRole("img").map((bar) => bar.getAttribute("aria-label"));
    expect(labels).toEqual(["NBA: $118,400,215.50", "Concert: $61,204,880.00", "WNBA: $12,910,332.25"]);
    const widths = screen.getAllByRole("img").map((bar) => Number(bar.getAttribute("width")));
    expect(widths[0]).toBeCloseTo((720 - 64 - 200) * 0.78);
    expect(widths[1]).toBeCloseTo(((widths[0] ?? 0) * 61204880) / 118400215.5);
  });

  it("draws a negative value as an empty bar with its value beside it, as the div chart did", () => {
    render(<BarChart result={{ ...ANSWERED, rows: [["NBA", 100], ["WNBA", -100]] }} />);
    const bar = screen.getByRole("img", { name: "WNBA: -$100.00" });
    expect(bar.getAttribute("width")).toBe("0");
    expect(Number(screen.getByText("-$100.00").getAttribute("x"))).toBe(Number(bar.getAttribute("x")) + 12);
  });
});
