import { useEffect, useId, useRef, type JSX, type ReactNode, type RefObject } from "react";

const FOCUSABLE = 'a[href], button:not([disabled]), input, textarea, select, summary, [tabindex]:not([tabindex="-1"])';

interface Props {
  title: string;
  side: "left" | "right";
  width: string;
  closeLabel: string;
  /** The control that opened the panel; focus goes back to it on close. */
  opener: HTMLElement | null;
  onClose: () => void;
  children: ReactNode;
}

/** A panel over a dimmed page. Focus moves in and stays in; Esc, the backdrop and the close button return it. */
export function SlideOver({ title, side, width, closeLabel, opener, onClose, children }: Props): JSX.Element {
  const panel = useRef<HTMLDivElement>(null);
  const titleId = useId();
  useFocusReturn(panel, opener);

  useEffect(() => {
    function onKey(event: KeyboardEvent): void {
      if (event.key === "Escape") onClose();
      if (event.key === "Tab") cycleFocus(event, panel);
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  const edge = side === "right" ? "right-0 border-l" : "left-0 border-r";
  return (
    <div className="fixed inset-0 z-20">
      <div role="presentation" onClick={onClose} className="absolute inset-0 bg-canvas/65" />
      <div
        ref={panel}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        className={`absolute inset-y-0 ${edge} ${width} flex flex-col overflow-y-auto border-hairline bg-panel shadow-[-24px_0_48px_rgba(0,0,0,0.5)]`}
      >
        <div className="flex h-[72px] shrink-0 items-center justify-between border-b border-hairline px-6">
          <h2 id={titleId} className="font-display text-[17px] font-semibold">
            {title}
          </h2>
          <button type="button" aria-label={closeLabel} onClick={onClose} className="control h-8 w-8 text-ink-2">
            <span aria-hidden="true">✕</span>
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}

/** Focus the first control on open and give focus back to the opener on close. */
function useFocusReturn(panel: RefObject<HTMLDivElement | null>, opener: HTMLElement | null): void {
  useEffect(() => {
    focusable(panel)[0]?.focus();
    return () => opener?.focus();
  }, [panel, opener]);
}

/** Keep Tab inside the panel: past the last control wraps to the first, and back again. */
function cycleFocus(event: KeyboardEvent, panel: RefObject<HTMLDivElement | null>): void {
  const controls = focusable(panel);
  const first = controls[0];
  const last = controls[controls.length - 1];
  if (!first || !last) return;
  if (!panel.current?.contains(document.activeElement)) {
    event.preventDefault();
    first.focus(); // a click on plain text dropped focus to the body; bring it back in
  } else if (event.shiftKey && document.activeElement === first) {
    event.preventDefault();
    last.focus();
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault();
    first.focus();
  }
}

function focusable(panel: RefObject<HTMLDivElement | null>): HTMLElement[] {
  return Array.from(panel.current?.querySelectorAll<HTMLElement>(FOCUSABLE) ?? []);
}
