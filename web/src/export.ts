// Taking a result away: the rows as CSV, the chart as a standalone SVG. Built in the browser.
import type { Cell } from "./types";

const CRLF = "\r\n";
const NEEDS_QUOTES = /[",;\r\n]/; // `;` too: Excel splits on it in many locales
const FORMULA_START = /^[=+\-@\t\r]/;
const SLUG_MAX = 60;
const SVG_NS = "http://www.w3.org/2000/svg";
const XMLNS_NS = "http://www.w3.org/2000/xmlns/";
const PANEL_FILL = "#16161A";

/** One CSV field: raw value, a formula-looking string defused with `'`, RFC 4180 quoting. */
function csvField(value: Cell): string {
  if (value === null) return "";
  let text = String(value);
  if (typeof value === "string" && FORMULA_START.test(text)) text = `'${text}`;
  return NEEDS_QUOTES.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
}

/** The header of raw column names, then one line per row, every line ending in CRLF. */
export function toCsv(columns: string[], rows: Cell[][]): string {
  return [columns, ...rows].map((line) => line.map(csvField).join(",") + CRLF).join("");
}

/** `Top 5 event categories!` -> `top-5-event-categories.csv`, capped, `results.csv` when nothing is left. */
export function exportFileName(question: string, extension: "csv" | "svg"): string {
  const slug = question
    .normalize("NFKD")
    .replace(/[̀-ͯ]/g, "") // strip the combining accents NFKD split off
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .slice(0, SLUG_MAX)
    .replace(/^-+|-+$/g, "");
  return `${slug || "results"}.${extension}`;
}

/** The on-screen chart as a file of its own: a copy with the namespace and the panel behind it. */
export function serializeChart(svg: SVGSVGElement): string {
  const copy = svg.cloneNode(true) as SVGSVGElement;
  // As a namespace declaration: a plain `xmlns` attribute serializes twice and the file will not parse.
  copy.setAttributeNS(XMLNS_NS, "xmlns", SVG_NS);
  const background = document.createElementNS(SVG_NS, "rect");
  background.setAttribute("width", "100%");
  background.setAttribute("height", "100%");
  background.setAttribute("fill", PANEL_FILL);
  copy.insertBefore(background, copy.firstChild);
  return new XMLSerializer().serializeToString(copy);
}

/** Saves text as a file through a temporary link, then lets the object URL go. */
export function downloadFile(fileName: string, content: string, type: string): void {
  const url = URL.createObjectURL(new Blob([content], { type }));
  const link = document.createElement("a");
  link.href = url;
  link.download = fileName;
  document.body.append(link);
  link.click();
  link.remove();
  // Revoked on the next task: Firefox can cancel a download whose URL is revoked in the same one.
  setTimeout(() => URL.revokeObjectURL(url), 0);
}
