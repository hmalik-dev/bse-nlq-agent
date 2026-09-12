import type { JSX } from "react";
import { SCHEMA_TITLE } from "./SchemaDrawer";

type Open = (button: HTMLElement) => void;

export const HOME_LABEL = "BSE Insights — back to the start";

interface Props {
  onHome: () => void;
  onOpenSchema: Open;
  /** Present when the session has history to show; the button only renders below 1024. */
  onOpenHistory: Open | null;
}

/** The lockup that leads back to the ask screen, the history button on narrow screens, and the button that opens the schema drawer. */
export function Header({ onHome, onOpenSchema, onOpenHistory }: Props): JSX.Element {
  return (
    <header className="flex h-16 items-center gap-3 border-b border-hairline px-4 lg:gap-4 lg:px-6">
      {onOpenHistory && (
        <button
          type="button"
          aria-label="Open session history"
          onClick={(event) => onOpenHistory(event.currentTarget)}
          className="control flex h-9 w-9 items-center justify-center lg:hidden"
        >
          <MenuIcon />
        </button>
      )}
      <button type="button" aria-label={HOME_LABEL} onClick={onHome} className="flex items-center gap-3 rounded-control lg:gap-4">
        <img src="/brand/bse.svg" alt="" width={672} height={254} className="block h-5 w-auto lg:h-7" />
        <span className="h-6 w-px bg-hairline" aria-hidden="true" />
        <span className="font-display text-[17px] font-semibold tracking-[-0.01em]">Insights</span>
      </button>
      <div className="flex-1" />
      <button
        type="button"
        aria-label={SCHEMA_TITLE}
        onClick={(event) => onOpenSchema(event.currentTarget)}
        className="control flex h-9 items-center bg-panel px-0 text-[13px] font-medium hover:bg-raised max-lg:w-9 max-lg:justify-center lg:px-3.5"
      >
        <span aria-hidden="true" className="font-mono text-sm font-semibold lg:hidden">
          ?
        </span>
        <span className="hidden lg:inline">{SCHEMA_TITLE}</span>
      </button>
    </header>
  );
}

function MenuIcon(): JSX.Element {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <path d="M2 4h12M2 8h12M2 12h12" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  );
}
