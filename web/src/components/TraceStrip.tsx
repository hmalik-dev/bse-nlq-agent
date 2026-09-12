import type { JSX } from "react";
import type { AskResult } from "../types";
import { formatSeconds } from "../format";

const REPAIRED: Record<number, string> = { 1: "repaired once", 2: "repaired twice" };

/** Model, elapsed time and repairs on the left; each step's real time on the right. */
export function TraceStrip({ result }: { result: AskResult }): JSX.Element {
  const { trace, truncated, row_count } = result;
  const parts = [trace.model, formatSeconds(trace.total_ms)];
  const repaired = REPAIRED[trace.repairs] ?? (trace.repairs > 0 ? `repaired ${trace.repairs} times` : null);
  if (repaired) parts.push(repaired);

  return (
    <footer className="flex flex-col gap-2 border-t border-hairline bg-sql px-5 py-3 font-mono text-xs text-ink-3">
      <div className="flex flex-wrap items-center gap-2.5">
        <ClockIcon />
        <span className="tabular-nums">{parts.join(" · ")}</span>
        <span className="flex-1" />
        <ul aria-label="Step times" className="flex flex-wrap gap-3.5 tabular-nums">
          {trace.steps.map((step) => (
            <li key={step.name}>
              {step.name} <span className="text-ink-2">{formatSeconds(step.ms, 2)}</span>
            </li>
          ))}
        </ul>
      </div>
      {truncated && <p className="tabular-nums">Showing the first {row_count} rows</p>}
    </footer>
  );
}

function ClockIcon(): JSX.Element {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden="true">
      <circle cx="7" cy="7" r="6.25" stroke="currentColor" strokeWidth="1.5" />
      <path d="M7 3.5V7l2.5 1.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  );
}
