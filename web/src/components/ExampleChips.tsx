import type { JSX } from "react";
import type { ExampleQuestion } from "../types";
import { Badge } from "./Badge";

interface Props {
  examples: ExampleQuestion[];
  onPick: (question: string) => void;
}

/** The six starter questions. Clicking one fills the input and asks it. */
export function ExampleChips({ examples, onPick }: Props): JSX.Element | null {
  if (examples.length === 0) return null;
  return (
    <section aria-label="Example questions" className="flex w-full max-w-[880px] flex-col gap-3">
      <h2 className="font-mono text-xs font-medium tracking-[0.1em] text-ink-3">TRY ONE OF THESE</h2>
      <ul className="flex flex-wrap gap-2.5">
        {examples.map((example) => (
          <li key={example.question}>
            <button
              type="button"
              onClick={() => onPick(example.question)}
              className="control inline-flex h-11 items-center gap-2.5 bg-panel px-3.5 text-[13px] hover:bg-raised"
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
