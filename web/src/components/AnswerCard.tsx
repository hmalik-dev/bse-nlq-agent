import type { JSX } from "react";
import type { AskResult, Status } from "../types";

// The agent reports an empty result by status, with no sentence; part 2 draws the full state.
const EMPTY_ANSWER: Partial<Record<Status, string>> = { empty: "No rows matched this question." };

/** The written answer in the largest type on the page, with the assumptions beneath it. */
export function AnswerCard({ result }: { result: AskResult }): JSX.Element {
  const text = result.error?.message ?? (result.answer || EMPTY_ANSWER[result.status] || "");
  return (
    <section aria-label="Answer" className="card flex flex-col gap-[18px] px-8 py-7">
      <p className="font-display text-[28px] font-medium leading-[1.35] tracking-[-0.02em] text-pretty">
        {text}
      </p>
      {result.assumptions.length > 0 && (
        <ul className="flex flex-wrap gap-2">
          {result.assumptions.map((assumption) => (
            <li
              key={assumption}
              className="inline-flex h-8 items-center gap-2 rounded-control border border-hairline bg-raised px-3 text-xs text-ink-2"
            >
              <span className="font-mono text-ink-3">ASSUMED</span>
              {assumption}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
