import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { TraceStrip } from "./TraceStrip";
import { PipelineSteps, STEP_NAMES } from "./PipelineSteps";
import { AnswerCard } from "./AnswerCard";
import { ANSWERED, EMPTY, ERROR, NETS } from "../test-fixtures";

describe("AnswerCard", () => {
  it("shows the answer, the error message, or the fixed empty sentence", () => {
    const { unmount } = render(<AnswerCard result={ANSWERED} />);
    expect(screen.getByText(ANSWERED.answer)).toBeTruthy();
    unmount();
    render(<AnswerCard result={ERROR} />);
    expect(screen.getByText("The model is rate limited right now.")).toBeTruthy();
    render(<AnswerCard result={EMPTY} />);
    expect(screen.getByText("No rows matched this question.")).toBeTruthy();
  });
});

describe("PipelineSteps", () => {
  it("lists the five steps with a spinner each and no times", () => {
    render(<PipelineSteps />);
    const items = screen.getAllByRole("listitem");
    expect(items.map((item) => item.textContent)).toEqual(STEP_NAMES.map((name) => `${name}…`));
    expect(document.querySelectorAll(".spinner")).toHaveLength(5);
  });
});

describe("TraceStrip", () => {
  it("shows the model, the elapsed seconds and each step's real time", () => {
    render(<TraceStrip result={ANSWERED} />);
    expect(screen.getByText("fake · 2.2s")).toBeTruthy();
    const times = screen.getByRole("list", { name: "Step times" });
    expect(times.textContent).toBe(
      "Reading schema 0.00sWriting SQL 1.24sChecking safety 0.01sRunning query 0.02sWriting answer 0.89s",
    );
  });

  it("hides steps that are absent from the trace and names the repairs", () => {
    const trace = { ...NETS.trace, steps: [{ name: "Writing SQL", ms: 500 }], repairs: 2 };
    render(<TraceStrip result={{ ...NETS, trace, truncated: true, row_count: 500 }} />);
    expect(screen.getByRole("list", { name: "Step times" }).textContent).toBe("Writing SQL 0.50s");
    expect(screen.getByText("fake · 2.2s · repaired twice")).toBeTruthy();
    expect(screen.getByText("Showing the first 500 rows")).toBeTruthy();
  });
});
