import type { JSX } from "react";
export function Footer(): JSX.Element {
  return (
    <footer className="border-t border-hairline">
      <div className="mx-auto flex max-w-[1200px] flex-wrap items-center gap-4 px-4 py-5 lg:px-6">
        <img
          src="/brand/barclays-center.svg"
          alt="Barclays Center"
          width={567}
          height={222}
          className="block h-5 w-auto"
        />
        <span className="text-[13px] text-ink-2">Events at Barclays Center, 2024 to today</span>
        <div className="flex-1" />
        <span className="inline-flex h-6 items-center rounded-full border border-hairline bg-panel px-2.5 font-mono text-[11px] text-ink-2">
          Demo · synthetic data
        </span>
      </div>
    </footer>
  );
}
