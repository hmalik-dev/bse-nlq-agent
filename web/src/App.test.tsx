import { afterEach, describe, expect, it, vi, type Mock } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { App } from "./App";
import { HOME_LABEL } from "./components/Header";
import { ANSWERED, BLOCKED, EMPTY, ERROR, EXAMPLES, NETS, UNANSWERABLE, jsonResponse } from "./test-fixtures";

/** Routes /api/examples to the chips and /api/ask to a result picked by keyword, like the fake agent. */
function stubApi(): Mock {
  const fetchMock = vi.fn((url: string, init?: RequestInit) => {
    if (url === "/api/examples") return Promise.resolve(jsonResponse(EXAMPLES));
    const { question } = JSON.parse(String(init?.body)) as { question: string };
    const result = byKeyword(question);
    return Promise.resolve(jsonResponse({ ...result, question }));
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function byKeyword(question: string) {
  if (/nothing/i.test(question)) return EMPTY;
  if (/delete/i.test(question)) return BLOCKED;
  if (/rate limit/i.test(question)) return ERROR;
  if (/weather/i.test(question)) return UNANSWERABLE;
  return /nets/i.test(question) ? NETS : ANSWERED;
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
    expect(screen.getByRole("button", { name: "What’s in the data?" }).getAttribute("aria-disabled")).toBeNull();
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

  it("renders markup in a question, the answer and a cell as text in the answer, table and rail", async () => {
    const payload = "<img src=x onerror=alert(1)>";
    const hostile = { ...ANSWERED, answer: `Answer ${payload}`, columns: ["name", "n"], rows: [[payload, 1]], chart: null };
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string, init?: RequestInit) => {
        if (url === "/api/examples") return Promise.resolve(jsonResponse(EXAMPLES));
        const { question } = JSON.parse(String(init?.body)) as { question: string };
        return Promise.resolve(jsonResponse({ ...hostile, question }));
      }),
    );
    const user = userEvent.setup();
    render(<App />);
    await user.type(await screen.findByLabelText("Your question"), `Top ${payload}{Enter}`);

    expect(await screen.findByText(`Answer ${payload}`)).toBeTruthy();
    expect(screen.getByRole("cell", { name: payload })).toBeTruthy();
    const rail = screen.getByRole("navigation", { name: "Session history" });
    expect(rail.textContent).toContain(`Top ${payload}`);
    expect(document.querySelector('img[src="x"]')).toBeNull();
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

  it("renders the empty state on the SQL tab and asks a suggestion when its chip is clicked", async () => {
    const user = userEvent.setup();
    const fetchMock = stubApi();
    render(<App />);
    await user.type(await screen.findByLabelText("Your question"), "nothing here{Enter}");
    expect(await screen.findByRole("heading", { name: "No rows matched this question" })).toBeTruthy();
    expect(screen.getAllByRole("tab").map((tab) => tab.textContent)).toEqual(["Results", "SQL"]);
    expect(screen.getByRole("tab", { name: "SQL" }).getAttribute("aria-selected")).toBe("true");
    await user.click(screen.getByRole("tab", { name: "Results" }));
    expect(screen.getByText("No rows to show.")).toBeTruthy();
    expect(screen.queryByRole("button", { name: /Export CSV|Download SVG/ })).toBeNull();
    await user.click(screen.getByRole("button", { name: "Try a wider date range" }));
    await screen.findByText(ANSWERED.answer);
    expect(askCalls(fetchMock)).toBe(2);
    expect(JSON.parse(String(fetchMock.mock.calls.at(-1)?.[1]?.body))).toEqual({ question: "Try a wider date range" });
  });

  it("refuses a destructive question without tabs and clears to the ask screen", async () => {
    const user = userEvent.setup();
    stubApi();
    render(<App />);
    await user.type(await screen.findByLabelText("Your question"), "Delete all ticket records{Enter}");
    expect(await screen.findByText("REJECTED STATEMENT")).toBeTruthy();
    expect(screen.queryByRole("tab")).toBeNull();
    expect(screen.queryByRole("button", { name: /Export CSV|Download SVG/ })).toBeNull();
    await user.click(screen.getByRole("button", { name: "Ask a different question" }));
    expect((screen.getByLabelText("Your question") as HTMLTextAreaElement).value).toBe("");
    expect(screen.getByRole("heading", { name: "Ask anything about ticket sales" })).toBeTruthy();
  });

  it("offers no export on an unanswerable question", async () => {
    const user = userEvent.setup();
    stubApi();
    render(<App />);
    await user.type(await screen.findByLabelText("Your question"), "What's the weather?{Enter}");
    expect(await screen.findByText(UNANSWERABLE.answer)).toBeTruthy();
    expect(screen.queryByRole("tab")).toBeNull();
    expect(screen.queryByRole("button", { name: /Export CSV|Download SVG/ })).toBeNull();
  });

  it("keeps the question in the box on an error and Retry asks it again", async () => {
    const user = userEvent.setup();
    const fetchMock = stubApi();
    render(<App />);
    await user.type(await screen.findByLabelText("Your question"), "rate limit please{Enter}");
    await screen.findByRole("heading", { name: "Asking is paused until the service responds." });
    expect((screen.getByLabelText("Your question") as HTMLTextAreaElement).value).toBe("rate limit please");
    expect(screen.queryByText(ERROR.error?.message ?? "")).toBeNull();
    expect(screen.queryByRole("tab")).toBeNull();
    expect(screen.queryByRole("button", { name: /Export CSV|Download SVG/ })).toBeNull();
    await user.click(screen.getByRole("button", { name: "Retry" }));
    await screen.findByRole("heading", { name: "Asking is paused until the service responds." });
    expect(askCalls(fetchMock)).toBe(2);
    expect(JSON.parse(String(fetchMock.mock.calls.at(-1)?.[1]?.body))).toEqual({ question: "rate limit please" });
    expect((screen.getByLabelText("Your question") as HTMLTextAreaElement).value).toBe("rate limit please");
  });

  it("opens the history as a menu from the header button and closes it on selection", async () => {
    const user = userEvent.setup();
    stubApi();
    render(<App />);
    expect(screen.queryByRole("button", { name: "Open session history" })).toBeNull();
    await user.click(await screen.findByRole("button", { name: "Top 5 event categories by total revenue" }));
    await screen.findByText(ANSWERED.answer);
    await user.click(screen.getByRole("button", { name: "Open session history" }));
    const menu = screen.getByRole("dialog", { name: "This session" });
    await user.click(menu.querySelector("li button") as HTMLElement);
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(screen.getByText(ANSWERED.answer)).toBeTruthy();
  });

  it("opens the schema drawer from the header and returns focus on Esc", async () => {
    const user = userEvent.setup();
    stubApi();
    render(<App />);
    const opener = await screen.findByRole("button", { name: "What’s in the data?" });
    await user.click(opener);
    expect(screen.getByRole("dialog", { name: "What’s in the data?" })).toBeTruthy();
    await user.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(document.activeElement).toBe(opener);
  });

  it("returns from the answer screen to an empty ask screen from the lockup, keeping the history", async () => {
    const user = userEvent.setup();
    stubApi();
    render(<App />);
    await user.click(await screen.findByRole("button", { name: "Top 5 event categories by total revenue" }));
    await screen.findByText(ANSWERED.answer);
    expect(document.querySelector("[aria-current]")).toBeTruthy();
    await user.click(screen.getByRole("button", { name: HOME_LABEL }));
    expect(screen.getByRole("heading", { name: "Ask anything about ticket sales" })).toBeTruthy();
    expect(screen.queryByText(ANSWERED.answer)).toBeNull();
    expect((screen.getByLabelText("Your question") as HTMLTextAreaElement).value).toBe("");
    const rail = screen.getAllByRole("navigation", { name: "Session history" })[0] as HTMLElement;
    expect(rail.textContent).toContain("Top 5 event categories by total revenue");
    expect(document.querySelector("[aria-current]")).toBeNull();
  });

  it("makes the lockup a keyboard control that leaves a draft alone on the ask screen", async () => {
    const user = userEvent.setup();
    stubApi();
    render(<App />);
    const box = await screen.findByLabelText("Your question");
    await user.type(box, "half a question");
    box.blur();
    await user.tab();
    expect(document.activeElement).toBe(screen.getByRole("button", { name: HOME_LABEL }));
    await user.keyboard("{Enter}");
    await user.keyboard(" ");
    expect((screen.getByLabelText("Your question") as HTMLTextAreaElement).value).toBe("half a question");
  });

  it("activates the lockup with Enter from the answer screen", async () => {
    const user = userEvent.setup();
    stubApi();
    render(<App />);
    await user.click(await screen.findByRole("button", { name: "Top 5 event categories by total revenue" }));
    await screen.findByText(ANSWERED.answer);
    screen.getByRole("button", { name: HOME_LABEL }).focus();
    await user.keyboard("{Enter}");
    expect(screen.getByRole("heading", { name: "Ask anything about ticket sales" })).toBeTruthy();
  });
});
