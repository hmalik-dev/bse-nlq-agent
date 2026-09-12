import { useEffect, useRef, useState, type JSX } from "react";
import { ask, examples as fetchExamples } from "./api";
import type { AskResult, ExampleQuestion } from "./types";
import { Header } from "./components/Header";
import { Footer } from "./components/Footer";
import { AskForm } from "./components/AskForm";
import { ExampleChips } from "./components/ExampleChips";
import { PipelineSteps } from "./components/PipelineSteps";
import { AnswerCard } from "./components/AnswerCard";
import { ResultTabs } from "./components/ResultTabs";
import { HistoryRail, type HistoryEntry } from "./components/HistoryRail";

type Screen = { kind: "ask" } | { kind: "thinking"; question: string } | { kind: "answer"; id: number };

export function App(): JSX.Element {
  const [examples, setExamples] = useState<ExampleQuestion[]>([]);
  const [draft, setDraft] = useState("");
  const [history, setHistory] = useState<HistoryEntry[]>([]);
  const [screen, setScreen] = useState<Screen>({ kind: "ask" });
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
    setDraft("");
    setScreen({ kind: "answer", id });
  }

  function pick(question: string): void {
    setDraft(question);
    void submit(question);
  }

  const current = screen.kind === "answer" ? history.find((entry) => entry.id === screen.id) : undefined;
  const showRail = history.length > 0 && screen.kind !== "thinking";

  return (
    <div className="flex min-h-screen flex-col">
      <Header />
      <div className="flex flex-1">
        {showRail && (
          <HistoryRail
            entries={history}
            currentId={current?.id ?? null}
            onSelect={(id) => setScreen({ kind: "answer", id })}
            onNew={() => setScreen({ kind: "ask" })}
          />
        )}
        <main className="min-w-0 flex-1">
          {screen.kind === "ask" && (
            <AskScreen draft={draft} examples={examples} onChange={setDraft} onSubmit={submit} onPick={pick} />
          )}
          {screen.kind === "thinking" && <ThinkingScreen question={screen.question} />}
          {current && <AnswerScreen key={current.id} result={current.result} />}
        </main>
      </div>
      <Footer />
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
    <div className="mx-auto flex max-w-[1200px] flex-col items-center px-6 pb-14 pt-[88px]">
      <h1 className="text-center font-display text-[44px] font-semibold leading-[1.1] tracking-[-0.025em]">
        Ask anything about ticket sales
      </h1>
      <p className="mt-3.5 text-center text-base text-ink-2">
        Plain English in, SQL and a written answer out. Events at Barclays Center, 2024 to today.
      </p>
      <div className="mt-11 w-full max-w-[880px]">
        <AskForm value={draft} onChange={onChange} onSubmit={onSubmit} />
      </div>
      <div className="mt-10 w-full max-w-[880px]">
        <ExampleChips examples={examples} onPick={onPick} />
      </div>
    </div>
  );
}

function ThinkingScreen({ question }: { question: string }): JSX.Element {
  return (
    <div className="mx-auto flex max-w-[1200px] flex-col gap-6 px-6 pb-16 pt-10">
      <div className="card px-6 py-5 text-lg font-medium leading-[1.35]">{question}</div>
      <PipelineSteps />
    </div>
  );
}

function AnswerScreen({ result }: { result: AskResult }): JSX.Element {
  return (
    <div className="mx-auto flex max-w-[1200px] flex-col gap-5 px-6 pb-12 pt-8">
      <p className="text-sm leading-[1.4] text-ink-2">{result.question}</p>
      <AnswerCard result={result} />
      {result.sql !== null && <ResultTabs result={result} />}
    </div>
  );
}
