import type { JSX } from "react";

/** No API key on the server: one card saying how to add it, and nothing to ask. */
export function SetupScreen({ database }: { database: boolean }): JSX.Element {
  return (
    <div className="mx-auto flex max-w-[1200px] flex-col items-center px-4 pb-10 pt-10 lg:px-6 lg:pt-[104px]">
      <section className="card flex w-full max-w-[720px] flex-col gap-5 p-6 lg:p-8">
        <div className="flex items-center gap-3">
          <span
            aria-hidden="true"
            className="flex h-[22px] w-[22px] flex-none items-center justify-center rounded-full bg-warning/16 text-[13px] font-bold text-warning"
          >
            !
          </span>
          <h1 className="font-display text-[26px] font-semibold leading-[1.2] tracking-[-0.02em] lg:text-[30px]">
            API key required
          </h1>
        </div>
        <p className="text-[15px] leading-[1.6] text-pretty text-ink-2">
          Stop the service, add <code className="font-mono text-ink">ANTHROPIC_API_KEY</code> to your{" "}
          <code className="font-mono text-ink">.env</code> file, then start it again and reload this page.
        </p>
        <div className="flex flex-col gap-2 rounded-card border border-hairline bg-sql px-5 py-4">
          <span className="font-mono text-[11px] font-medium tracking-[0.08em] text-ink-3">.ENV</span>
          <code className="overflow-x-auto whitespace-pre font-mono text-[13.5px] leading-[1.9]">
            ANTHROPIC_API_KEY=<span className="text-ink-3">sk-ant-…</span>
          </code>
        </div>
        <div className="h-px bg-hairline" />
        <p className="flex items-center gap-2.5 font-mono text-xs tabular-nums text-ink-3">
          <span aria-hidden="true" className="h-2 w-2 flex-none rounded-full bg-warning" />
          GET /api/health · api_key: false · database: {database ? "ok" : "missing"}
        </p>
      </section>
    </div>
  );
}
