import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { SetupScreen } from "./SetupScreen";

describe("SetupScreen", () => {
  it("names the missing key and says where it goes, with nothing to ask", () => {
    render(<SetupScreen />);
    expect(screen.getByRole("heading", { level: 1, name: "API key required" })).toBeTruthy();
    expect(screen.getByText(/then restart the server/).textContent).toBe(
      "Add ANTHROPIC_API_KEY to the .env file in the project folder, then restart the server.",
    );
    expect(screen.queryByRole("textbox")).toBeNull();
    expect(screen.queryByRole("button")).toBeNull();
  });
});
