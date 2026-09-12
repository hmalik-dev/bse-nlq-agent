import type { JSX } from "react";
import type { AskResult } from "../types";
import { formatSeconds } from "../format";

export interface HistoryEntry {
  id: number;
  result: AskResult;
}

interface Props {
  entries: HistoryEntry[];
  currentId: number | null;
  onSelect: (id: number) => void;
  onNew: () => void;
}

/** Every question asked this session, newest last, the current one in cyan. React state only. */
export function HistoryRail({ entries, currentId, onSelect, onNew }: Props): JSX.Element {
  return (
    <nav aria-label="Session history" className="flex w-60 shrink-0 flex-col gap-3.5 border-r border-hairline px-3 py-5">
      <button
        type="button"
        aria-label="New question"
        onClick={onNew}
        className="h-10 rounded-control bg-accent text-[13px] font-semibold text-black transition-colors duration-150 hover:bg-accent-hover"
      >
        + New question
      </button>
      <h2 className="px-2 font-mono text-[11px] font-medium tracking-[0.08em] text-ink-3">THIS SESSION</h2>
      <ul className="flex flex-col gap-1">
        {entries.map((entry) => {
          const current = entry.id === currentId;
          return (
            <li key={entry.id}>
              <button
                type="button"
                aria-current={current ? "true" : undefined}
                onClick={() => onSelect(entry.id)}
                className={`flex w-full flex-col gap-1.5 rounded-control border p-2.5 text-left transition-colors duration-150 ${
                  current ? "border-hairline bg-raised" : "border-transparent hover:bg-panel"
                }`}
              >
                <span className={`text-[12.5px] leading-[1.4] ${current ? "font-medium text-accent" : "text-ink-2"}`}>
                  {entry.result.question}
                </span>
                <span className="font-mono text-[11px] tabular-nums text-ink-3">{summary(entry.result)}</span>
              </button>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}

function summary(result: AskResult): string {
  const elapsed = formatSeconds(result.trace.total_ms, 2);
  return result.status === "answered" || result.status === "empty"
    ? `${elapsed} · ${result.row_count} rows`
    : `${elapsed} · ${result.status}`;
}
