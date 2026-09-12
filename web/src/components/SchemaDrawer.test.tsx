import { afterEach, describe, expect, it, vi, type Mock } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState, type JSX } from "react";
import { SchemaDrawer, useSchema } from "./SchemaDrawer";
import { SCHEMA, jsonResponse } from "../test-fixtures";

/** A header button and the drawer, wired the way App wires them. */
function Harness(): JSX.Element {
  const [opener, setOpener] = useState<HTMLElement | null>(null);
  const state = useSchema(opener !== null);
  return (
    <>
      <button type="button" onClick={(event) => setOpener(event.currentTarget)}>
        What’s in the data?
      </button>
      {opener && <SchemaDrawer state={state} opener={opener} onClose={() => setOpener(null)} />}
    </>
  );
}

function stubSchema(): Mock {
  const fetchMock = vi.fn(() => Promise.resolve(jsonResponse(SCHEMA)));
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

afterEach(() => vi.unstubAllGlobals());

describe("SchemaDrawer", () => {
  it("opens with the definitions and six table groups, and moves focus inside", async () => {
    const user = userEvent.setup();
    stubSchema();
    render(<Harness />);
    await user.click(screen.getByRole("button", { name: "What’s in the data?" }));
    const dialog = await screen.findByRole("dialog", { name: "What’s in the data?" });
    expect(dialog.contains(document.activeElement)).toBe(true);
    expect(screen.getByRole("region", { name: "How we define things" }).querySelectorAll("li")).toHaveLength(2);
    const groups = dialog.querySelectorAll("details");
    expect(Array.from(groups).map((group) => group.querySelector("summary")?.textContent)).toEqual([
      "▶▼venues2 columns",
      "▶▼teams2 columns",
      "▶▼events2 columns",
      "▶▼customers2 columns",
      "▶▼orders2 columns",
      "▶▼tickets2 columns",
    ]);
    expect(groups[2]?.open).toBe(true);
    expect(groups[0]?.open).toBe(false);
    expect(groups[2]?.textContent).toContain("event_id");
    expect(groups[2]?.textContent).toContain("INTEGER");
  });

  it("traps Tab inside the drawer", async () => {
    const user = userEvent.setup();
    stubSchema();
    render(<Harness />);
    await user.click(screen.getByRole("button", { name: "What’s in the data?" }));
    const dialog = await screen.findByRole("dialog");
    await screen.findByRole("region", { name: "How we define things" });
    const close = screen.getByRole("button", { name: "Close schema panel" });
    expect(document.activeElement).toBe(close);
    await user.tab({ shift: true });
    expect(dialog.contains(document.activeElement)).toBe(true);
    expect(document.activeElement).not.toBe(close);
    await user.tab();
    expect(document.activeElement).toBe(close);
    await user.click(screen.getByText("HOW WE DEFINE THINGS"));
    await user.tab();
    expect(dialog.contains(document.activeElement)).toBe(true);
  });

  it("closes on Esc, the backdrop and the close button, returning focus to the opener each time", async () => {
    const user = userEvent.setup();
    stubSchema();
    render(<Harness />);
    const opener = screen.getByRole("button", { name: "What’s in the data?" });

    await user.click(opener);
    await screen.findByRole("dialog");
    await user.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(document.activeElement).toBe(opener);

    await user.click(opener);
    await user.click(screen.getByRole("button", { name: "Close schema panel" }));
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(document.activeElement).toBe(opener);

    await user.click(opener);
    await user.click(document.querySelector('[role="presentation"]') as HTMLElement);
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(document.activeElement).toBe(opener);
  });

  it("fetches the schema once across two opens", async () => {
    const user = userEvent.setup();
    const fetchMock = stubSchema();
    render(<Harness />);
    const opener = screen.getByRole("button", { name: "What’s in the data?" });
    await user.click(opener);
    await screen.findByRole("region", { name: "How we define things" });
    await user.keyboard("{Escape}");
    await user.click(opener);
    expect(await screen.findByRole("region", { name: "How we define things" })).toBeTruthy();
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock.mock.calls[0]?.[0]).toBe("/api/schema");
  });

  it("says so when the schema cannot be loaded", async () => {
    const user = userEvent.setup();
    vi.stubGlobal("fetch", vi.fn(() => Promise.resolve(jsonResponse({ detail: "down" }, 500))));
    render(<Harness />);
    await user.click(screen.getByRole("button", { name: "What’s in the data?" }));
    expect(await screen.findByText("Could not load the schema. Check that the server is running.")).toBeTruthy();
  });
});
