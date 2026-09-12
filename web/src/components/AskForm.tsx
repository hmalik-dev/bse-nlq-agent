import { useState, type ChangeEvent, type JSX, type KeyboardEvent } from "react";

const MAX_LINES = 3;
const LINE_HEIGHT_PX = 22;
const PADDING_PX = 34;
const MAX_HEIGHT_PX = MAX_LINES * LINE_HEIGHT_PX + PADDING_PX;

interface Props {
  value: string;
  onChange: (value: string) => void;
  onSubmit: (question: string) => void;
}

/** The question box and the Ask button. Enter submits; Shift+Enter adds a line. */
export function AskForm({ value, onChange, onSubmit }: Props): JSX.Element {
  const [height, setHeight] = useState<number | undefined>(undefined);
  const question = value.trim();

  function submit(): void {
    if (question) onSubmit(question);
  }

  function handleKey(event: KeyboardEvent<HTMLTextAreaElement>): void {
    if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault();
      submit();
    }
  }

  function handleChange(event: ChangeEvent<HTMLTextAreaElement>): void {
    onChange(event.target.value);
    // Grow from one line to three with the text, then scroll inside.
    event.target.style.height = "auto";
    setHeight(Math.min(event.target.scrollHeight, MAX_HEIGHT_PX));
  }

  return (
    <form
      className="flex w-full max-w-[880px] flex-col gap-2"
      onSubmit={(event) => {
        event.preventDefault();
        submit();
      }}
    >
      <label htmlFor="question" className="text-[13px] font-medium text-ink-2">
        Your question
      </label>
      <div className="flex flex-col gap-3 lg:flex-row lg:items-stretch">
        <textarea
          id="question"
          name="question"
          rows={1}
          value={value}
          onChange={handleChange}
          onKeyDown={handleKey}
          placeholder="e.g. How many tickets did we sell for Nets home games last month?"
          style={{ height }}
          className="min-h-14 flex-1 resize-none rounded-control border border-hairline bg-panel px-4 py-[17px] text-[15px] leading-[22px] text-ink placeholder:text-ink-3 transition-colors duration-150 focus:border-accent focus:shadow-focus focus:outline-none"
        />
        <button
          type="submit"
          disabled={!question}
          className="h-14 rounded-control bg-accent px-8 text-[15px] font-semibold text-black transition-colors duration-150 hover:bg-accent-hover disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:bg-accent lg:self-start"
        >
          Ask
        </button>
      </div>
      <p className="mt-0.5 text-xs text-ink-3">Read-only. Single SELECT statements only.</p>
    </form>
  );
}
