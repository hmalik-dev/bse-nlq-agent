import { afterEach, describe, expect, it, vi, type Mock } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { App } from "./App";
import { ANSWERED, EXAMPLES, NETS, jsonResponse } from "./test-fixtures";

/** Routes /api/examples to the chips and /api/ask to a result picked by keyword, like the fake agent. */
function stubApi(): Mock {
  const fetchMock = vi.fn((url: string, init?: RequestInit) => {
    if (url === "/api/examples") return Promise.resolve(jsonResponse(EXAMPLES));
    const { question } = JSON.parse(String(init?.body)) as { question: string };
    const result = /nets/i.test(question) ? NETS : ANSWERED;
    return Promise.resolve(jsonResponse({ ...result, question }));
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

const askCalls = (fetchMock: Mock): number =>
  fetchMock.mock.calls.filter(([url]) => url === "/api/ask").length;

afterEach(() => vi.unstubAllGlobals());

describe("App", () => {
  it("renders six chips from the API, two with badges, and disables Ask while empty", async () => {
    stubApi();
    render(<App />);
    const chips = await screen.findAllByRole("listitem");
    expect(chips).toHaveLength(6);
    expect(document.querySelectorAll("[data-badge=nets]")).toHaveLength(1);
    expect(document.querySelectorAll("[data-badge=liberty]")).toHaveLength(1);
    expect((screen.getByRole("button", { name: "Ask" }) as HTMLButtonElement).disabled).toBe(true);
    expect(screen.getByRole("button", { name: "What’s in the data?" }).getAttribute("aria-disabled")).toBe("true");
  });

  it("submits an example chip and renders the answer", async () => {
    const user = userEvent.setup();
    const fetchMock = stubApi();
    render(<App />);
    await user.click(await screen.findByRole("button", { name: "Top 5 event categories by total revenue" }));
    expect(await screen.findByText(ANSWERED.answer)).toBeTruthy();
    expect(askCalls(fetchMock)).toBe(1);
    expect(screen.getAllByRole("tab").map((tab) => tab.textContent)).toEqual(["Results", "SQL", "Chart"]);
  });

  it("submits on Enter, keeps Shift+Enter as a newline", async () => {
    const user = userEvent.setup();
    const fetchMock = stubApi();
    render(<App />);
    const box = await screen.findByLabelText("Your question");
    await user.type(box, "line one{Shift>}{Enter}{/Shift}line two");
    expect((box as HTMLTextAreaElement).value).toBe("line one\nline two");
    expect(askCalls(fetchMock)).toBe(0);
    await user.keyboard("{Enter}");
    await waitFor(() => expect(askCalls(fetchMock)).toBe(1));
    const body = String(fetchMock.mock.calls.find(([url]) => url === "/api/ask")?.[1]?.body);
    expect(JSON.parse(body)).toEqual({ question: "line one\nline two" });
  });

  it("lists every question in the rail and restores an earlier result without asking again", async () => {
    const user = userEvent.setup();
    const fetchMock = stubApi();
    render(<App />);
    await user.click(await screen.findByRole("button", { name: "Top 5 event categories by total revenue" }));
    await screen.findByText(ANSWERED.answer);
    await user.click(screen.getByRole("button", { name: "New question" }));
    await user.type(screen.getByLabelText("Your question"), "nets tickets last month{Enter}");
    await screen.findByText(NETS.answer);
    expect(askCalls(fetchMock)).toBe(2);

    const rail = screen.getByRole("navigation", { name: "Session history" });
    const entries = rail.querySelectorAll("li button");
    expect(entries).toHaveLength(2);
    expect(entries[1]?.getAttribute("aria-current")).toBe("true");
    expect(entries[1]?.textContent).toContain("2.16s · 2 rows");

    await user.click(entries[0] as HTMLElement);
    expect(await screen.findByText(ANSWERED.answer)).toBeTruthy();
    expect(askCalls(fetchMock)).toBe(2);
    expect(rail.querySelectorAll("li button")[0]?.getAttribute("aria-current")).toBe("true");

    // A tab chosen on one result does not leak into the next: the Nets result has no chart.
    await user.click(screen.getByRole("tab", { name: "Chart" }));
    await user.click(entries[1] as HTMLElement);
    await screen.findByText(NETS.answer);
    expect(screen.getByRole("tab", { name: "Results" }).getAttribute("aria-selected")).toBe("true");

    await user.click(screen.getByRole("button", { name: "New question" }));
    expect(screen.getByRole("heading", { name: "Ask anything about ticket sales" })).toBeTruthy();
  });

  it("shows the pipeline steps while the request is in flight", async () => {
    const user = userEvent.setup();
    let resolve: (value: Response) => void = () => undefined;
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string) =>
        url === "/api/examples"
          ? Promise.resolve(jsonResponse(EXAMPLES))
          : new Promise<Response>((done) => {
              resolve = done;
            }),
      ),
    );
    render(<App />);
    await user.type(await screen.findByLabelText("Your question"), "slow question{Enter}");
    expect(screen.getByRole("list", { name: "Pipeline steps" }).getAttribute("aria-busy")).toBe("true");
    expect(screen.queryByLabelText("Your question")).toBeNull();
    resolve(jsonResponse(ANSWERED));
    expect(await screen.findByText(ANSWERED.answer)).toBeTruthy();
  });
});
