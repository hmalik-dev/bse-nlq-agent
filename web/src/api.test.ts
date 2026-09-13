import { afterEach, describe, expect, it, vi } from "vitest";
import { ask, examples, hasApiKey, schema } from "./api";
import { BY_STATUS, EXAMPLES, HEALTH, jsonResponse } from "./test-fixtures";

afterEach(() => vi.unstubAllGlobals());

describe("hasApiKey", () => {
  it.each([true, false])("reads api_key %s from /api/health", async (present) => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ ...HEALTH, api_key: present }));
    vi.stubGlobal("fetch", fetchMock);
    expect(await hasApiKey()).toBe(present);
    expect(fetchMock).toHaveBeenCalledWith("/api/health");
  });

  it("assumes a key when the health check fails, so asking reports the real error", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
    expect(await hasApiKey()).toBe(true);
  });
});

describe("ask", () => {
  it.each(Object.entries(BY_STATUS))("parses the %s result unchanged", async (status, fixture) => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(fixture)));
    const result = await ask(fixture.question);
    expect(result.status).toBe(status);
    expect(result).toEqual(fixture);
  });

  it("posts the question as JSON to /api/ask", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(BY_STATUS.answered));
    vi.stubGlobal("fetch", fetchMock);
    await ask("How many tickets?");
    expect(fetchMock).toHaveBeenCalledWith("/api/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: "How many tickets?" }),
    });
  });

  it("turns a non-200 into an error result with code network", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({ detail: [] }, 422)));
    const result = await ask("x");
    expect(result.status).toBe("error");
    expect(result.error).toEqual({ code: "network", message: "The server answered 422." });
    expect(result.question).toBe("x");
  });

  it("turns a network failure into an error result with code network", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
    const result = await ask("x");
    expect(result.status).toBe("error");
    expect(result.error?.code).toBe("network");
    expect(result.trace.steps).toEqual([]);
  });
});

describe("examples and schema", () => {
  it("returns the example list", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(EXAMPLES)));
    expect(await examples()).toEqual(EXAMPLES);
  });

  it("returns the schema and throws on a failed request", async () => {
    const body = { tables: [], definitions: ["Revenue is SUM(price)."] };
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(body)));
    expect(await schema()).toEqual(body);
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({}, 500)));
    await expect(schema()).rejects.toThrow("GET /api/schema answered 500");
  });
});
