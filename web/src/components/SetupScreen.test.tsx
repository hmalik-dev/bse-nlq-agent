import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { SetupScreen } from "./SetupScreen";

const INSTRUCTION =
  "Stop the service, add ANTHROPIC_API_KEY to your .env file, then start it again and reload this page.";
const ENV_LINE = ["ANTHROPIC_API_KEY", "sk-ant-…"].join("="); // the placeholder shown, joined so it never reads as a key

describe("SetupScreen", () => {
  it("names the missing key, says where it goes and shows the .env line, with nothing to ask", () => {
    render(<SetupScreen database />);
    expect(screen.getByRole("heading", { level: 1, name: "API key required" })).toBeTruthy();
    expect(screen.getByText(/reload this page/).textContent).toBe(INSTRUCTION);
    expect(screen.getByText(new RegExp(`^${ENV_LINE.split("=")[0]}=`)).textContent?.trim()).toBe(ENV_LINE);
    expect(screen.queryByRole("textbox")).toBeNull();
    expect(screen.queryByRole("button")).toBeNull();
  });

  it.each([
    [true, "GET /api/health · api_key: false · database: ok"],
    [false, "GET /api/health · api_key: false · database: missing"],
  ])("reports the health check with database %s", (database, line) => {
    render(<SetupScreen database={database} />);
    expect(screen.getByText(/^GET \/api\/health/).textContent?.trim()).toBe(line);
  });
});
