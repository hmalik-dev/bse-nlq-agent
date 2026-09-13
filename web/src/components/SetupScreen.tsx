import type { JSX } from "react";

/** No API key on the server: say how to add one, and offer nothing to ask. */
export function SetupScreen(): JSX.Element {
  return (
    <div className="mx-auto flex max-w-[1200px] flex-col items-center px-4 pb-14 pt-10 lg:px-6 lg:pt-[88px]">
      <h1 className="text-center font-display text-[28px] font-semibold leading-[1.1] tracking-[-0.025em] lg:text-[44px]">
        API key required
      </h1>
      <p className="mt-3.5 max-w-[640px] text-center text-base text-ink-2">
        Add <code className="font-mono">ANTHROPIC_API_KEY</code> to the <code className="font-mono">.env</code> file in
        the project folder, then restart the server.
      </p>
    </div>
  );
}
