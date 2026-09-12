import type { JSX } from "react";
export const STEP_NAMES = [
  "Reading schema",
  "Writing SQL",
  "Checking safety",
  "Running query",
  "Writing answer",
] as const;

/** The five pipeline steps while a question is in flight. The API is one call, so
 *  nothing is known until it returns; every step shows a spinner, and the real
 *  times land in the trace strip on the answer screen. */
export function PipelineSteps(): JSX.Element {
  return (
    <ol aria-label="Pipeline steps" aria-busy="true" className="card px-6 py-2">
      {STEP_NAMES.map((name) => (
        <li
          key={name}
          className="flex items-center gap-3.5 border-b border-hairline py-4 last:border-b-0"
        >
          <span className="spinner" aria-hidden="true" />
          <span className="flex-1 text-sm">{name}</span>
          <span className="font-mono text-[13px] text-ink-3">…</span>
        </li>
      ))}
    </ol>
  );
}
