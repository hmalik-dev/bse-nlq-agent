import { useRef, useState, type JSX, type KeyboardEvent } from "react";
import type { AskResult } from "../types";
import { downloadFile, exportFileName, serializeChart, toCsv } from "../export";
import { ResultsTable } from "./ResultsTable";
import { SqlBlock } from "./SqlBlock";
import { BarChart } from "./BarChart";
import { TraceStrip } from "./TraceStrip";

type TabId = "results" | "sql" | "chart";
const LABELS: Record<TabId, string> = { results: "Results", sql: "SQL", chart: "Chart" };
const TOOL_BUTTON = "control ml-3.5 h-[30px] shrink-0 px-3 text-xs font-medium";

/** Results / SQL / Chart with a WAI-ARIA tablist: arrow keys move and select. */
export function ResultTabs({ result }: { result: AskResult }): JSX.Element {
  const tabs: TabId[] = result.chart ? ["results", "sql", "chart"] : ["results", "sql"];
  const [active, setActive] = useState<TabId>(result.rows.length === 0 ? "sql" : "results");
  const buttons = useRef<Map<TabId, HTMLButtonElement>>(new Map());
  const chart = useRef<SVGSVGElement>(null);

  function handleKey(event: KeyboardEvent<HTMLButtonElement>, index: number): void {
    const moves: Record<string, number> = { ArrowRight: index + 1, ArrowLeft: index - 1, Home: 0, End: tabs.length - 1 };
    const next = moves[event.key];
    if (next === undefined) return;
    event.preventDefault();
    const target = tabs[(next + tabs.length) % tabs.length];
    if (!target) return;
    setActive(target);
    buttons.current.get(target)?.focus();
  }

  function exportCsv(): void {
    downloadFile(exportFileName(result.question, "csv"), toCsv(result.columns, result.rows), "text/csv;charset=utf-8");
  }

  function downloadSvg(): void {
    if (!chart.current) return;
    downloadFile(exportFileName(result.question, "svg"), serializeChart(chart.current), "image/svg+xml");
  }

  return (
    <section className="card overflow-hidden">
      <div className="flex items-center border-b border-hairline px-4">
        <div role="tablist" aria-label="Result views" className="flex items-center">
          {tabs.map((tab, index) => (
            <button
              key={tab}
              ref={(element) => {
                if (element) buttons.current.set(tab, element);
              }}
              type="button"
              role="tab"
              id={`tab-${tab}`}
              aria-selected={active === tab}
              aria-controls={`panel-${tab}`}
              tabIndex={active === tab ? 0 : -1}
              onClick={() => setActive(tab)}
              onKeyDown={(event) => handleKey(event, index)}
              className={`mr-3.5 h-12 px-1.5 text-[13px] transition-colors duration-150 ${
                active === tab ? "font-semibold text-ink shadow-[inset_0_-2px_0_var(--color-accent)]" : "font-medium text-ink-2 hover:text-ink"
              }`}
            >
              {LABELS[tab]}
            </button>
          ))}
        </div>
        <span className="flex-1" />
        {active !== "chart" && <span className="whitespace-nowrap font-mono text-xs tabular-nums text-ink-3">{result.row_count} rows</span>}
        {active === "results" && result.rows.length > 0 && (
          <button
            type="button"
            onClick={exportCsv}
            title={result.truncated ? `Contains the first ${result.rows.length} rows` : `Download ${result.rows.length} rows as CSV`}
            className={TOOL_BUTTON}
          >
            Export CSV
          </button>
        )}
        {active === "chart" && (
          <button type="button" onClick={downloadSvg} className={TOOL_BUTTON}>
            Download SVG
          </button>
        )}
      </div>
      <div role="tabpanel" id={`panel-${active}`} aria-labelledby={`tab-${active}`}>
        {active === "results" && <ResultsTable columns={result.columns} rows={result.rows} />}
        {active === "sql" && result.sql !== null && <SqlBlock sql={result.sql} />}
        {active === "chart" && <BarChart result={result} svgRef={chart} />}
      </div>
      <TraceStrip result={result} />
    </section>
  );
}
