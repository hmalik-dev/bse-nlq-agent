import type { JSX } from "react";
export function Header(): JSX.Element {
  return (
    <header className="flex h-16 items-center gap-4 border-b border-hairline px-6">
      <img
        src="/brand/bse.svg"
        alt="BSE Global"
        width={672}
        height={254}
        className="block h-7 w-auto"
      />
      <div className="h-6 w-px bg-hairline" aria-hidden="true" />
      <span className="font-display text-[17px] font-semibold tracking-[-0.01em]">Insights</span>
      <div className="flex-1" />
      {/* Part 2 wires this to the schema drawer; until then it is present but inert. */}
      <button
        type="button"
        aria-disabled="true"
        className="control h-9 bg-panel px-3.5 text-[13px] font-medium hover:bg-raised"
      >
        What&rsquo;s in the data?
      </button>
    </header>
  );
}
