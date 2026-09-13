import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { BlockedCard, EmptyCard, ErrorCard, REFUSED_LINE, UnanswerableCard } from "./FailureCards";
import { errorCopy, GENERIC_ERROR } from "../error-copy";
import { BLOCKED, EMPTY, ERROR, UNANSWERABLE } from "../test-fixtures";

describe("EmptyCard", () => {
  it("says no rows matched, keeps the assumptions and submits a suggestion on click", async () => {
    const user = userEvent.setup();
    const onPick = vi.fn();
    render(<EmptyCard result={EMPTY} onPick={onPick} />);
    expect(screen.getByRole("heading", { name: "No rows matched this question" })).toBeTruthy();
    expect(screen.getByText(EMPTY.assumptions[0] ?? "")).toBeTruthy();
    const chips = screen.getByRole("list", { name: "Suggested questions" }).querySelectorAll("button");
    expect(chips).toHaveLength(2);
    await user.click(chips[1] as HTMLElement);
    expect(onPick).toHaveBeenCalledWith("Try a different category");
  });
});

describe("UnanswerableCard", () => {
  it("shows the answer text, what the data covers and three example chips", () => {
    render(<UnanswerableCard result={UNANSWERABLE} onPick={vi.fn()} />);
    expect(screen.getByText(UNANSWERABLE.answer)).toBeTruthy();
    expect(screen.getByRole("heading", { name: "WHAT IT DOES COVER" }).parentElement?.textContent).toContain(
      "eventsticketsorderscustomersrevenue",
    );
    expect(screen.getByRole("list", { name: "Suggested questions" }).querySelectorAll("button")).toHaveLength(3);
  });
});

describe("BlockedCard", () => {
  it("shows the refusal line, the struck-through statement and clears on the button", async () => {
    const user = userEvent.setup();
    const onReset = vi.fn();
    render(<BlockedCard result={BLOCKED} onReset={onReset} />);
    expect(screen.getByText(REFUSED_LINE, { exact: false })).toBeTruthy();
    expect(screen.getByText("REJECTED STATEMENT")).toBeTruthy();
    expect(screen.getByText("DELETE FROM tickets").className).toContain("line-through");
    await user.click(screen.getByRole("button", { name: "Ask a different question" }));
    expect(onReset).toHaveBeenCalledTimes(1);
  });

  it("hides the statement when sql is null", () => {
    render(<BlockedCard result={{ ...BLOCKED, sql: null }} onReset={vi.fn()} />);
    expect(screen.queryByText("REJECTED STATEMENT")).toBeNull();
    expect(screen.getByRole("heading", { name: "That request was refused before it ran" })).toBeTruthy();
  });
});

describe("ErrorCard", () => {
  it("shows the copy for the code, never the raw message, and retries on the button", async () => {
    const user = userEvent.setup();
    const onRetry = vi.fn();
    render(<ErrorCard result={ERROR} onRetry={onRetry} />);
    expect(screen.getByRole("heading", { name: "Asking is paused until the service responds." })).toBeTruthy();
    expect(screen.queryByText(ERROR.error?.message ?? "")).toBeNull();
    await user.click(screen.getByRole("button", { name: "Retry" }));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it("uses the generic line for an internal error and shows nothing of its message", () => {
    const internal = { ...ERROR, error: { code: "internal", message: "Traceback (most recent call last)" } };
    render(<ErrorCard result={internal} onRetry={vi.fn()} />);
    expect(screen.getByRole("heading", { name: GENERIC_ERROR })).toBeTruthy();
    expect(document.body.textContent).not.toContain("Traceback");
  });
});

describe("errorCopy", () => {
  it("has one sentence per API code and falls back to the generic line", () => {
    expect(errorCopy("missing_api_key")).toBe("The service is not configured with an API key.");
    expect(errorCopy("rate_limited")).toBe("Asking is paused until the service responds.");
    expect(errorCopy("model_timeout")).toBe(errorCopy("network"));
    expect(errorCopy("network")).toBe("The service did not respond. Try again.");
    expect(errorCopy("query_timeout")).toBe("That question took too long to run. Try narrowing it.");
    expect(errorCopy("repairs_exhausted")).toBe("The generated query kept failing. Try rewording.");
    expect(errorCopy("database_missing")).toContain("uv run python -m nlq.db.seed");
    expect(errorCopy("usage_exhausted")).toBe(
      "This demo has used up its usage allowance. Nothing is broken; asking works again once it is topped up.",
    );
    expect(errorCopy("something_new")).toBe(GENERIC_ERROR);
  });
});
