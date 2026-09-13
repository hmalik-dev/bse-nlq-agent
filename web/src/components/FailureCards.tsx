import type { JSX, ReactNode } from "react";
import type { AskResult } from "../types";
import { errorCopy } from "../error-copy";
import { AssumptionChips } from "./AnswerCard";
import { formatSeconds } from "../format";

const COVERED = ["events", "tickets", "orders", "customers", "revenue"];
const EMPTY_EXPLANATION = "The query ran and returned no rows. Try one of these questions instead.";
export const REFUSED_LINE = "Refused: INSERT, UPDATE, DELETE, DROP, ALTER, GRANT, multiple statements";
const ALLOWED_LINE = "Allowed: a single SELECT statement";
const CARD = "card flex flex-col gap-5 px-5 py-5 lg:px-8 lg:py-7";
const HEADING = "font-display text-[22px] font-medium leading-[1.35] tracking-[-0.02em] text-pretty lg:text-[28px]";
const BODY = "max-w-[760px] text-[15px] leading-[1.55] text-ink-2";
const LABEL = "font-mono text-xs font-medium tracking-[0.08em] text-ink-3";
const NOTE = "font-mono text-xs text-ink-3";
const PRIMARY = "h-10 self-start rounded-control bg-accent px-[18px] text-[13px] font-semibold text-black transition-colors duration-150 hover:bg-accent-hover";

interface Props {
  result: AskResult;
  onPick: (question: string) => void;
}

/** No rows came back: the SQL ran, so the assumptions and tabs stay; example questions are offered. */
export function EmptyCard({ result, onPick }: Props): JSX.Element {
  return (
    <Card>
      <h2 className={HEADING}>No rows matched this question</h2>
      <p className={BODY}>{EMPTY_EXPLANATION}</p>
      <AssumptionChips assumptions={result.assumptions} />
      <SuggestionChips suggestions={result.suggestions} onPick={onPick} />
    </Card>
  );
}

/** The data does not hold what was asked: say so, list what it does cover, offer three examples. */
export function UnanswerableCard({ result, onPick }: Props): JSX.Element {
  return (
    <Card>
      <div className="flex items-start gap-3">
        <Mark tone="warning" />
        <h2 className={HEADING}>This data cannot answer that</h2>
      </div>
      <p className={BODY}>{result.answer}</p>
      <div className="flex flex-col gap-3 rounded-control border border-hairline bg-raised px-5 py-[18px]">
        <h3 className={LABEL}>WHAT IT DOES COVER</h3>
        <ul className="flex flex-wrap gap-2">
          {COVERED.map((topic) => (
            <li key={topic} className="inline-flex h-7 items-center rounded-control bg-panel px-[11px] font-mono text-xs">
              {topic}
            </li>
          ))}
        </ul>
      </div>
      <h3 className={LABEL}>QUESTIONS THIS DATA CAN ANSWER</h3>
      <SuggestionChips suggestions={result.suggestions} onPick={onPick} />
      <p className={NOTE}>No SQL was generated · {formatSeconds(result.trace.total_ms)}</p>
    </Card>
  );
}

/** A destructive request refused before it ran, with the rejected statement dimmed and struck through. */
export function BlockedCard({ result, onReset }: { result: AskResult; onReset: () => void }): JSX.Element {
  return (
    <Card tone="error">
      <div className="flex items-center gap-3">
        <span className="rounded-control bg-error/15 px-2 py-1 font-mono text-[11px] font-semibold tracking-[0.08em] text-error">
          BLOCKED
        </span>
        <span className={NOTE}>rejected before execution · {formatSeconds(result.trace.total_ms)}</span>
      </div>
      <h2 className={HEADING}>That request was refused before it ran</h2>
      <p className={BODY}>{result.answer}</p>
      {result.sql !== null && (
        <div className="flex flex-col gap-2 rounded-control border border-hairline bg-sql px-5 py-4">
          <span className="font-mono text-[11px] font-medium tracking-[0.08em] text-ink-3">REJECTED STATEMENT</span>
          <code className="font-mono text-sm text-ink-3 line-through">{result.sql}</code>
        </div>
      )}
      <ul className="flex flex-col gap-1.5 text-[13px] text-ink-2">
        <li>
          <span aria-hidden="true" className="mr-2 text-seafoam">✓</span>
          {ALLOWED_LINE}
        </li>
        <li>
          <span aria-hidden="true" className="mr-2 text-error">✕</span>
          {REFUSED_LINE}
        </li>
      </ul>
      <button type="button" onClick={onReset} className={PRIMARY}>
        Ask a different question
      </button>
    </Card>
  );
}

/** The service failed: one plain sentence for the code, never the raw message, and a Retry button. */
export function ErrorCard({ result, onRetry }: { result: AskResult; onRetry: () => void }): JSX.Element {
  return (
    <Card tone="error">
      <div className="flex items-start gap-3">
        <Mark tone="error" />
        <h2 className={HEADING}>{errorCopy(result.error?.code ?? "")}</h2>
      </div>
      <p className={BODY}>Nothing was lost. Your question is still in the box below.</p>
      <button type="button" onClick={onRetry} className={PRIMARY}>
        Retry
      </button>
    </Card>
  );
}

function Card({ tone = "plain", children }: { tone?: "plain" | "error"; children: ReactNode }): JSX.Element {
  return (
    <section aria-label="Answer" aria-live="polite" className={`${CARD} ${tone === "error" ? "border-error" : ""}`}>
      {children}
    </section>
  );
}

function Mark({ tone }: { tone: "warning" | "error" }): JSX.Element {
  const color = tone === "warning" ? "bg-warning/15 text-warning" : "bg-error/15 text-error";
  return (
    <span aria-hidden="true" className={`mt-1.5 inline-flex h-[22px] w-[22px] shrink-0 items-center justify-center rounded-full font-mono text-xs font-semibold ${color}`}>
      !
    </span>
  );
}

/** Rewordings or example questions as chips. Clicking one asks it. */
function SuggestionChips({ suggestions, onPick }: { suggestions: string[]; onPick: (question: string) => void }): JSX.Element | null {
  if (suggestions.length === 0) return null;
  return (
    <ul aria-label="Suggested questions" className="flex flex-wrap gap-2.5">
      {suggestions.map((suggestion) => (
        <li key={suggestion}>
          <button type="button" onClick={() => onPick(suggestion)} className="control h-10 px-3.5 text-[13px] hover:bg-panel">
            {suggestion}
          </button>
        </li>
      ))}
    </ul>
  );
}
