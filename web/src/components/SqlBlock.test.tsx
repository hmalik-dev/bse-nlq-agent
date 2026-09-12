import { afterEach, describe, expect, it, vi } from "vitest";
import { act, fireEvent, render, screen } from "@testing-library/react";
import { SqlBlock } from "./SqlBlock";

const SQL = "-- note\nSELECT name FROM events WHERE category = 'Concert'";

afterEach(() => vi.useRealTimers());

describe("SqlBlock", () => {
  it("numbers the lines and colours keywords, strings and comments", () => {
    render(<SqlBlock sql={SQL} />);
    const pre = screen.getByText("SELECT").closest("pre");
    expect(pre?.textContent).toContain(" 1-- note");
    expect(screen.getByText("SELECT").className).toBe("text-accent");
    expect(screen.getByText("'Concert'").className).toBe("text-seafoam");
    expect(screen.getByText("-- note").className).toBe("text-ink-3");
    expect(screen.getByText("events").className).toBe("");
  });

  it("copies the SQL and says Copied for two seconds", async () => {
    vi.useFakeTimers();
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", { value: { writeText }, configurable: true });
    render(<SqlBlock sql={SQL} />);
    const button = screen.getByRole("button", { name: "Copy SQL" });
    await act(async () => {
      fireEvent.click(button);
    });
    expect(writeText).toHaveBeenCalledWith(SQL);
    expect(button.textContent).toBe("Copied");
    await act(async () => {
      vi.advanceTimersByTime(2000);
    });
    expect(button.textContent).toBe("Copy");
  });
});
