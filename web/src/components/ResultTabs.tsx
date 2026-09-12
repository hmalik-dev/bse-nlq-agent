import { useRef, useState, type JSX, type KeyboardEvent } from "react";
import type { AskResult } from "../types";
import { ResultsTable } from "./ResultsTable";
import { SqlBlock } from "./SqlBlock";
import { BarChart } from "./BarChart";
import { TraceStrip } from "./TraceStrip";

type TabId = "results" | "sql" | "chart";
const LABELS: Record<TabId, string> = { results: "Results", sql: "SQL", chart: "Chart" };

/** Results / SQL / Chart with a WAI-ARIA tablist: arrow keys move and select. */
export function ResultTabs({ result }: { result: AskResult }): JSX.Element {
  const tabs: TabId[] = result.chart ? ["results", "sql", "chart"] : ["results", "sql"];
  const [active, setActive] = useState<TabId>(result.rows.length === 0 ? "sql" : "results");
  const buttons = useRef<Map<TabId, HTMLButtonElement>>(new Map());

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

  return (
    <section className="card overflow-hidden">
      <div role="tablist" aria-label="Result views" className="flex items-center border-b border-hairline px-4">
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
        <span className="flex-1" />
        <span className="font-mono text-xs tabular-nums text-ink-3">{result.row_count} rows</span>
      </div>
      <div role="tabpanel" id={`panel-${active}`} aria-labelledby={`tab-${active}`}>
        {active === "results" && <ResultsTable columns={result.columns} rows={result.rows} />}
        {active === "sql" && result.sql !== null && <SqlBlock sql={result.sql} />}
        {active === "chart" && <BarChart result={result} />}
      </div>
      <TraceStrip result={result} />
    </section>
  );
}
