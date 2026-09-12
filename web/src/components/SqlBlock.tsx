import { useEffect, useState, type JSX } from "react";
import { highlight, type Token } from "../sql-highlight";

const COPIED_FOR_MS = 2000;
const TOKEN_CLASS: Record<Token["kind"], string> = {
  keyword: "text-accent",
  string: "text-seafoam",
  comment: "text-ink-3",
  text: "",
};

/** The statement on the SQL surface with line numbers, light colouring and a copy button. */
export function SqlBlock({ sql }: { sql: string }): JSX.Element {
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (!copied) return;
    const timer = setTimeout(() => setCopied(false), COPIED_FOR_MS);
    return () => clearTimeout(timer);
  }, [copied]);

  async function copy(): Promise<void> {
    try {
      await navigator.clipboard.writeText(sql);
      setCopied(true);
    } catch {
      setCopied(false); // the browser refused clipboard access; the SQL is still on screen to select
    }
  }

  return (
    <div className="relative bg-sql py-5">
      <button
        type="button"
        aria-label="Copy SQL"
        onClick={copy}
        className="control absolute top-3.5 right-4 h-[30px] px-3 text-xs font-medium"
      >
        {copied ? "Copied" : "Copy"}
      </button>
      {/* No ligatures: JetBrains Mono would draw `<=` as one glyph, which misreads in SQL. */}
      <pre className="overflow-x-auto px-6 font-mono text-[13.5px] leading-8 [font-variant-ligatures:none]">
        {highlight(sql).map((tokens, index) => (
          <div key={index} className="whitespace-pre">
            <span className="inline-block w-[34px] select-none text-gutter" aria-hidden="true">
              {String(index + 1).padStart(2, " ")}
            </span>
            {tokens.map((token, tokenIndex) => (
              <span key={tokenIndex} className={TOKEN_CLASS[token.kind]}>
                {token.text}
              </span>
            ))}
          </div>
        ))}
      </pre>
    </div>
  );
}
