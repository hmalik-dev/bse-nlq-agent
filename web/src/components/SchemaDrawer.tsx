import { useEffect, useRef, useState, type JSX } from "react";
import type { ColumnInfo, Definition, Schema, TableInfo } from "../types";
import { schema as fetchSchema } from "../api";
import { SlideOver } from "./SlideOver";

export const SCHEMA_TITLE = "What’s in the data?";
const OPEN_BY_DEFAULT = new Set(["events", "tickets"]);
const LABEL = "font-mono text-[11px] font-medium tracking-[0.08em] text-ink-3";
const LOAD_FAILED = "Could not load the schema. Check that the server is running.";

export type SchemaState = { kind: "loading" } | { kind: "ready"; schema: Schema } | { kind: "failed" };

/** Fetch the schema the first time the drawer opens and keep it for the session; only a failure is retried. */
export function useSchema(open: boolean): SchemaState {
  const [state, setState] = useState<SchemaState>({ kind: "loading" });
  const requested = useRef(false);
  useEffect(() => {
    if (!open || requested.current) return;
    requested.current = true;
    setState({ kind: "loading" });
    fetchSchema()
      .then((schema) => setState({ kind: "ready", schema }))
      .catch(() => {
        requested.current = false;
        setState({ kind: "failed" });
      });
  }, [open]);
  return state;
}

interface Props {
  state: SchemaState;
  opener: HTMLElement | null;
  onClose: () => void;
}

/** The definitions, then the six tables as collapsible cards; the list scrolls and the footer stays put. */
export function SchemaDrawer({ state, opener, onClose }: Props): JSX.Element {
  return (
    <SlideOver title={SCHEMA_TITLE} side="right" width="w-full lg:w-[480px]" closeLabel="Close schema panel" opener={opener} onClose={onClose}>
      <div className="flex min-h-0 flex-1 flex-col gap-5 overflow-y-auto px-6 py-5">
        {state.kind === "loading" && <p className="text-sm text-ink-2">Loading the schema…</p>}
        {state.kind === "failed" && <p className="text-sm text-error">{LOAD_FAILED}</p>}
        {state.kind === "ready" && <Definitions definitions={state.schema.definitions} />}
        {state.kind === "ready" && <Tables tables={state.schema.tables} />}
      </div>
      <footer className="flex shrink-0 items-center gap-3 border-t border-hairline px-6 py-4">
        <img src="/brand/barclays-center.svg" alt="Barclays Center" width={567} height={222} className="block h-5 w-auto" />
        <span className="text-xs leading-[1.4] text-ink-3">Events at Barclays Center, 2024 to today</span>
      </footer>
    </SlideOver>
  );
}

function Definitions({ definitions }: { definitions: Definition[] }): JSX.Element {
  return (
    <section
      aria-label="How we define things"
      className="flex shrink-0 flex-col gap-2.5 rounded-card border border-hairline bg-raised px-[18px] py-4"
    >
      <h3 className={LABEL}>HOW WE DEFINE THINGS</h3>
      <ul className="flex flex-col gap-2.5 text-[13px] leading-[1.55] text-ink-2">
        {definitions.map(({ term, text }) => (
          <li key={term}>
            <span className="text-ink">{term}</span> <WithLiterals text={text} />
          </li>
        ))}
      </ul>
    </section>
  );
}

/** Text with `backticked` values set in seafoam mono: the odd pieces of a split on the backtick. */
function WithLiterals({ text }: { text: string }): JSX.Element {
  return (
    <>
      {text.split("`").map((piece, index) =>
        index % 2 === 1 ? (
          <code key={index} className="font-mono text-seafoam">
            {piece}
          </code>
        ) : (
          piece
        ),
      )}
    </>
  );
}

function Tables({ tables }: { tables: TableInfo[] }): JSX.Element {
  return (
    <section aria-label="Tables" className="flex flex-col gap-2">
      <h3 className={LABEL}>{tables.length} TABLES</h3>
      {tables.map((table) => (
        <TableCard key={table.name} table={table} />
      ))}
    </section>
  );
}

function TableCard({ table }: { table: TableInfo }): JSX.Element {
  return (
    <details open={OPEN_BY_DEFAULT.has(table.name)} className="group shrink-0 overflow-hidden rounded-card border border-hairline">
      <summary className="flex cursor-pointer list-none items-center gap-2.5 bg-raised px-3.5 py-3 font-mono text-[13px] font-medium">
        <span aria-hidden="true" className="text-[11px] font-normal text-ink-3 group-open:text-accent">
          <span className="group-open:hidden">▶</span>
          <span className="hidden group-open:inline">▼</span>
        </span>
        {table.name}
        <span className="ml-auto text-[11px] font-normal tabular-nums text-ink-3">{table.columns.length} columns</span>
      </summary>
      <div className="flex flex-col gap-3 border-t border-hairline py-3 pl-8 pr-3.5">
        <p className="text-xs leading-[1.45] text-ink-2">{table.description}</p>
        <ul className="flex flex-col gap-2.5">
          {table.columns.map((column) => (
            <ColumnRow key={column.name} column={column} />
          ))}
        </ul>
      </div>
    </details>
  );
}

/** Name left and type right on one line, the description beneath in smaller secondary text. */
function ColumnRow({ column }: { column: ColumnInfo }): JSX.Element {
  const type = column.references === null ? column.type : `${column.type} → ${column.references}`;
  return (
    <li className="flex flex-col gap-1">
      <div className="flex items-baseline justify-between gap-3 font-mono text-xs">
        <span className="min-w-0 break-all text-ink">{column.name}</span>
        <span className="shrink-0 text-ink-3">{type}</span>
      </div>
      <p className="text-[11px] leading-[1.45] text-ink-2">{column.description}</p>
    </li>
  );
}
