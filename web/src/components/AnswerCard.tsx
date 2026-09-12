import type { JSX } from "react";
import type { AskResult } from "../types";

/** The written answer in the largest type on the page, with the assumptions beneath it. */
export function AnswerCard({ result }: { result: AskResult }): JSX.Element {
  return (
    <section aria-label="Answer" aria-live="polite" className="card flex flex-col gap-[18px] px-5 py-5 lg:px-8 lg:py-7">
      <p className="font-display text-[22px] font-medium leading-[1.35] tracking-[-0.02em] text-pretty lg:text-[28px]">
        {result.answer}
      </p>
      <AssumptionChips assumptions={result.assumptions} />
    </section>
  );
}

/** Each assumption the agent made, as an ASSUMED chip. */
export function AssumptionChips({ assumptions }: { assumptions: string[] }): JSX.Element | null {
  if (assumptions.length === 0) return null;
  return (
    <ul className="flex flex-wrap gap-2">
      {assumptions.map((assumption) => (
        <li
          key={assumption}
          className="inline-flex min-h-8 items-center gap-2 rounded-control border border-hairline bg-raised px-3 py-1 text-xs text-ink-2"
        >
          <span className="font-mono text-ink-3">ASSUMED</span>
          {assumption}
        </li>
      ))}
    </ul>
  );
}
