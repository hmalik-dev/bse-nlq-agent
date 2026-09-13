import type { JSX } from "react";
import type { ExampleQuestion } from "../types";
import { Badge } from "./Badge";

interface Props {
  examples: ExampleQuestion[];
  onPick: (question: string) => void;
}

/** The six starter questions: a wrap of chips on desktop, a stack of full-width rows on a phone. Clicking one asks it. */
export function ExampleChips({ examples, onPick }: Props): JSX.Element | null {
  if (examples.length === 0) return null;
  return (
    <section aria-label="Example questions" className="flex w-full max-w-[880px] flex-col gap-2.5 lg:gap-3">
      <h2 className="font-mono text-[11px] font-medium tracking-[0.1em] text-ink-3 lg:text-xs">TRY ONE OF THESE</h2>
      <ul className="flex flex-col gap-2 lg:flex-row lg:flex-wrap lg:gap-2.5">
        {examples.map((example) => (
          <li key={example.question}>
            <button
              type="button"
              onClick={() => onPick(example.question)}
              className="control flex min-h-11 w-full items-center gap-2.5 bg-panel px-3 py-2.5 text-left text-[12.5px] leading-[1.35] hover:bg-raised lg:inline-flex lg:w-auto lg:px-3.5 lg:py-0 lg:text-[13px] lg:leading-none"
            >
              {example.badge && <Badge name={example.badge} />}
              {example.question}
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}
