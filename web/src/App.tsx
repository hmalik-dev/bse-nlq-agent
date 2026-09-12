import { useEffect, useRef, useState, type JSX } from "react";
import { ask, examples as fetchExamples } from "./api";
import type { AskResult, ExampleQuestion } from "./types";
import { Header } from "./components/Header";
import { Footer } from "./components/Footer";
import { AskForm } from "./components/AskForm";
import { ExampleChips } from "./components/ExampleChips";
import { PipelineSteps } from "./components/PipelineSteps";
import { AnswerCard } from "./components/AnswerCard";
import { BlockedCard, EmptyCard, ErrorCard, UnanswerableCard } from "./components/FailureCards";
import { ResultTabs } from "./components/ResultTabs";
import { HistoryRail, type HistoryEntry } from "./components/HistoryRail";
import { SchemaDrawer, useSchema } from "./components/SchemaDrawer";
import { SlideOver } from "./components/SlideOver";

type Screen = { kind: "ask" } | { kind: "thinking"; question: string } | { kind: "answer"; id: number };
type Panel = { kind: "schema" | "history"; opener: HTMLElement } | null;

export function App(): JSX.Element {
  const [examples, setExamples] = useState<ExampleQuestion[]>([]);
  const [draft, setDraft] = useState("");
  const [history, setHistory] = useState<HistoryEntry[]>([]);
  const [screen, setScreen] = useState<Screen>({ kind: "ask" });
  const [panel, setPanel] = useState<Panel>(null);
  const schema = useSchema(panel?.kind === "schema");
  const nextId = useRef(1);

  useEffect(() => {
    let cancelled = false;
    fetchExamples()
      .then((list) => {
        if (!cancelled) setExamples(list);
      })
      .catch(() => {
        if (!cancelled) setExamples([]); // no chips is a degraded page, not a broken one
      });
    return () => {
      cancelled = true;
    };
  }, []);

  async function submit(question: string): Promise<void> {
    setScreen({ kind: "thinking", question });
    const result = await ask(question);
    const id = nextId.current++;
    setHistory((previous) => [...previous, { id, result }]);
    setDraft(result.status === "error" ? question : ""); // an error keeps the question so nothing is lost
    setScreen({ kind: "answer", id });
  }

  function pick(question: string): void {
    setDraft(question);
    void submit(question);
  }

  function reset(): void {
    setDraft("");
    setScreen({ kind: "ask" });
  }

  function show(id: number): void {
    const entry = history.find((item) => item.id === id);
    setPanel(null);
    setDraft(entry?.result.status === "error" ? entry.result.question : "");
    setScreen({ kind: "answer", id });
  }

  const current = screen.kind === "answer" ? history.find((entry) => entry.id === screen.id) : undefined;
  const showRail = history.length > 0 && screen.kind !== "thinking";
  const rail = (
    <HistoryRail
      entries={history}
      currentId={current?.id ?? null}
      onSelect={show}
      onNew={() => {
        setPanel(null);
        reset();
      }}
    />
  );

  return (
    <div className="flex min-h-screen flex-col">
      <Header
        onOpenSchema={(opener) => setPanel({ kind: "schema", opener })}
        onOpenHistory={showRail ? (opener) => setPanel({ kind: "history", opener }) : null}
      />
      <div className="flex flex-1">
        {showRail && <div className="hidden w-60 shrink-0 border-r border-hairline lg:block">{rail}</div>}
        <main className="min-w-0 flex-1">
          {screen.kind === "ask" && (
            <AskScreen draft={draft} examples={examples} onChange={setDraft} onSubmit={submit} onPick={pick} />
          )}
          {screen.kind === "thinking" && <ThinkingScreen question={screen.question} />}
          {current && (
            <AnswerScreen
              key={current.id}
              result={current.result}
              draft={draft}
              onChange={setDraft}
              onSubmit={submit}
              onPick={pick}
              onReset={reset}
            />
          )}
        </main>
      </div>
      <Footer />
      {panel?.kind === "schema" && <SchemaDrawer state={schema} opener={panel.opener} onClose={() => setPanel(null)} />}
      {panel?.kind === "history" && (
        <SlideOver
          title="This session"
          side="left"
          width="w-full max-w-[320px]"
          closeLabel="Close session history"
          opener={panel.opener}
          onClose={() => setPanel(null)}
        >
          {rail}
        </SlideOver>
      )}
    </div>
  );
}

interface AskScreenProps {
  draft: string;
  examples: ExampleQuestion[];
  onChange: (value: string) => void;
  onSubmit: (question: string) => void;
  onPick: (question: string) => void;
}

function AskScreen({ draft, examples, onChange, onSubmit, onPick }: AskScreenProps): JSX.Element {
  return (
    <div className="mx-auto flex max-w-[1200px] flex-col items-center px-4 pb-14 pt-10 lg:px-6 lg:pt-[88px]">
      <h1 className="text-center font-display text-[28px] font-semibold leading-[1.1] tracking-[-0.025em] lg:text-[44px]">
        Ask anything about ticket sales
      </h1>
      <p className="mt-3.5 text-center text-base text-ink-2">
        Plain English in, SQL and a written answer out. Events at Barclays Center, 2024 to today.
      </p>
      <div className="mt-8 w-full max-w-[880px] lg:mt-11">
        <AskForm value={draft} onChange={onChange} onSubmit={onSubmit} />
      </div>
      <div className="mt-8 w-full max-w-[880px] lg:mt-10">
        <ExampleChips examples={examples} onPick={onPick} />
      </div>
    </div>
  );
}

function ThinkingScreen({ question }: { question: string }): JSX.Element {
  return (
    <div className="mx-auto flex max-w-[1200px] flex-col gap-6 px-4 pb-16 pt-10 lg:px-6">
      <div className="card px-6 py-5 text-lg font-medium leading-[1.35]">{question}</div>
      <PipelineSteps />
    </div>
  );
}

interface AnswerScreenProps {
  result: AskResult;
  draft: string;
  onChange: (value: string) => void;
  onSubmit: (question: string) => void;
  onPick: (question: string) => void;
  onReset: () => void;
}

/** One card per status; the tabs follow wherever SQL ran and rows came back, and an error keeps the question box. */
function AnswerScreen({ result, draft, onChange, onSubmit, onPick, onReset }: AnswerScreenProps): JSX.Element {
  return (
    <div className="mx-auto flex max-w-[1200px] flex-col gap-5 px-4 pb-12 pt-6 lg:px-6 lg:pt-8">
      <p className="text-sm leading-[1.4] text-ink-2">{result.question}</p>
      {result.status === "answered" && <AnswerCard result={result} />}
      {result.status === "empty" && <EmptyCard result={result} onPick={onPick} />}
      {result.status === "unanswerable" && <UnanswerableCard result={result} onPick={onPick} />}
      {result.status === "blocked" && <BlockedCard result={result} onReset={onReset} />}
      {result.status === "error" && <ErrorCard result={result} onRetry={() => onSubmit(result.question)} />}
      {result.status === "error" && <AskForm value={draft} onChange={onChange} onSubmit={onSubmit} />}
      {(result.status === "answered" || result.status === "empty") && result.sql !== null && <ResultTabs result={result} />}
    </div>
  );
}
