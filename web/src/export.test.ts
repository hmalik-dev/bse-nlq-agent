import { afterEach, describe, expect, it, vi } from "vitest";
import { downloadFile, exportFileName, serializeChart, toCsv } from "./export";

describe("toCsv", () => {
  it("writes raw column names and raw values, each line ending in CRLF", () => {
    expect(toCsv(["category", "revenue"], [["NBA", 1234.5], ["Concert", 61204880]])).toBe(
      "category,revenue\r\nNBA,1234.5\r\nConcert,61204880\r\n",
    );
  });

  it("quotes a comma, doubles a quote and quotes a newline", () => {
    expect(toCsv(["a", "b", "c"], [["Nets, Knicks", 'The "Garden"', "line one\nline two"]])).toBe(
      'a,b,c\r\n"Nets, Knicks","The ""Garden""","line one\nline two"\r\n',
    );
  });

  it("quotes a semicolon so a locale that splits on it cannot start a formula mid-cell", () => {
    expect(toCsv(["a"], [['Acme;=HYPERLINK("x")']])).toBe('a\r\n"Acme;=HYPERLINK(""x"")"\r\n');
  });

  it("writes null as an empty field and booleans as words", () => {
    expect(toCsv(["a", "b", "c"], [[null, "x", true]])).toBe("a,b,c\r\n,x,true\r\n");
  });

  it("leaves a negative number unchanged", () => {
    expect(toCsv(["delta"], [[-12]])).toBe("delta\r\n-12\r\n");
  });

  it("defuses a string that a spreadsheet would run as a formula", () => {
    expect(toCsv(["f"], [["=SUM(A1)"], ["+1"], ["-12"], ["@cmd"], ["\tx"]])).toBe(
      "f\r\n'=SUM(A1)\r\n'+1\r\n'-12\r\n'@cmd\r\n'\tx\r\n",
    );
    expect(toCsv(["f"], [["\rx"]])).toBe("f\r\n\"'\rx\"\r\n");
  });

  it("keeps a unicode performer name as it is", () => {
    expect(toCsv(["performer"], [["Beyoncé"], ["Sigur Rós"], ["坂本龍一"]])).toBe(
      "performer\r\nBeyoncé\r\nSigur Rós\r\n坂本龍一\r\n",
    );
  });
});

describe("exportFileName", () => {
  it("slugs the question", () => {
    expect(exportFileName("Top 5 event categories by total revenue", "csv")).toBe(
      "top-5-event-categories-by-total-revenue.csv",
    );
    expect(exportFileName("  Beyoncé's shows — 2024?  ", "svg")).toBe("beyonce-s-shows-2024.svg");
  });

  it("falls back to results when nothing usable is left", () => {
    expect(exportFileName("", "csv")).toBe("results.csv");
    expect(exportFileName("?!… 坂本", "svg")).toBe("results.svg");
  });

  it("caps the slug at 60 characters without a trailing dash", () => {
    const name = exportFileName("Which Brooklyn Nets home games sold the most tickets in the 2025 season", "csv");
    expect(name).toBe("which-brooklyn-nets-home-games-sold-the-most-tickets-in-the.csv");
    expect(name.length - ".csv".length).toBeLessThanOrEqual(60);
  });
});

describe("serializeChart", () => {
  it("adds the namespace and a panel background ahead of the chart", () => {
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.appendChild(document.createElementNS("http://www.w3.org/2000/svg", "rect"));
    const text = serializeChart(svg);
    expect(text).toMatch(/^<svg xmlns="http:\/\/www\.w3\.org\/2000\/svg"><rect width="100%" height="100%" fill="#16161A"\/><rect\/><\/svg>$/);
    expect(svg.childNodes).toHaveLength(1);
  });
});

describe("downloadFile", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.useRealTimers();
  });

  it("clicks a temporary link to an object URL, then revokes the URL", () => {
    vi.useFakeTimers();
    const create = vi.fn(() => "blob:test");
    const revoke = vi.fn();
    Object.assign(URL, { createObjectURL: create, revokeObjectURL: revoke });
    const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function (this: HTMLAnchorElement) {
      expect(this.download).toBe("results.csv");
      expect(this.getAttribute("href")).toBe("blob:test");
    });
    downloadFile("results.csv", "a\r\n", "text/csv");
    expect(click).toHaveBeenCalledTimes(1);
    expect(document.querySelector("a[download]")).toBeNull();
    vi.runAllTimers();
    expect(revoke).toHaveBeenCalledWith("blob:test");
  });
});
