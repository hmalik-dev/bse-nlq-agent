import type { JSX } from "react";

/** The venue line and the demo pill, on one row; the phone layout drops "Events at" and "synthetic data". */
export function Footer(): JSX.Element {
  return (
    <footer className="border-t border-hairline">
      <div className="mx-auto flex max-w-[1200px] items-center gap-2.5 px-4 pb-4 pt-3 lg:flex-wrap lg:gap-4 lg:px-6 lg:py-5">
        <img
          src="/brand/barclays-center.svg"
          alt="Barclays Center"
          width={567}
          height={222}
          className="block h-[18px] w-auto lg:h-5"
        />
        <span className="text-[11.5px] leading-[1.3] text-ink-2 lg:text-[13px] lg:leading-none">
          <span className="max-lg:hidden">Events at </span>Barclays Center, 2024 to today
        </span>
        <div className="flex-1" />
        <span className="inline-flex h-[22px] items-center rounded-full border border-hairline bg-panel px-[9px] font-mono text-[10px] text-ink-2 lg:h-6 lg:px-2.5 lg:text-[11px]">
          Demo<span className="max-lg:hidden">{" · synthetic data"}</span>
        </span>
      </div>
    </footer>
  );
}
