import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { BarChart, wrapLabel } from "./BarChart";
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
});
