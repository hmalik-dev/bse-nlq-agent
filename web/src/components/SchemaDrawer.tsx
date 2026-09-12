import { useEffect, useRef, useState, type JSX } from "react";
import type { Schema, TableInfo } from "../types";
import { schema as fetchSchema } from "../api";
import { SlideOver } from "./SlideOver";

export const SCHEMA_TITLE = "What’s in the data?";
const OPEN_BY_DEFAULT = new Set(["events", "tickets"]);
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

/** The business definitions, then the six tables as collapsible groups. */
export function SchemaDrawer({ state, opener, onClose }: Props): JSX.Element {
  return (
    <SlideOver title={SCHEMA_TITLE} side="right" width="w-full lg:w-[480px]" closeLabel="Close schema panel" opener={opener} onClose={onClose}>
      <div className="flex flex-col gap-5 px-6 py-5">
        {state.kind === "loading" && <p className="text-sm text-ink-2">Loading the schema…</p>}
        {state.kind === "failed" && <p className="text-sm text-error">{LOAD_FAILED}</p>}
        {state.kind === "ready" && <Definitions definitions={state.schema.definitions} />}
        {state.kind === "ready" && state.schema.tables.map((table) => <TableGroup key={table.name} table={table} />)}
      </div>
    </SlideOver>
  );
}

function Definitions({ definitions }: { definitions: string[] }): JSX.Element {
  return (
    <section
      aria-label="How we define things"
      className="flex flex-col gap-2.5 rounded-control border border-hairline bg-raised px-[18px] py-4"
    >
      <h3 className="font-mono text-[11px] font-medium tracking-[0.08em] text-ink-3">HOW WE DEFINE THINGS</h3>
      <ul className="flex flex-col gap-2 text-[13px] leading-[1.5] text-ink-2">
        {definitions.map((definition) => (
          <li key={definition}>{definition}</li>
        ))}
      </ul>
    </section>
  );
}

function TableGroup({ table }: { table: TableInfo }): JSX.Element {
  return (
    <details open={OPEN_BY_DEFAULT.has(table.name)} className="group rounded-control border border-hairline">
      <summary className="flex cursor-pointer list-none items-center gap-2.5 rounded-control px-3.5 py-3 font-mono text-[13px] font-medium hover:bg-raised">
        <span aria-hidden="true" className="text-[10px] text-ink-3 group-open:text-accent">
          <span className="group-open:hidden">▶</span>
          <span className="hidden group-open:inline">▼</span>
        </span>
        {table.name}
        <span className="ml-auto font-normal text-ink-3">{table.columns.length} columns</span>
      </summary>
      <p className="px-3.5 pb-2 text-xs text-ink-2">{table.description}</p>
      <ul className="flex flex-col gap-[7px] px-3.5 pb-3 pl-8">
        {table.columns.map((column) => (
          <li key={column.name} className="flex flex-wrap items-baseline gap-x-3 text-xs">
            <span className="font-mono">{column.name}</span>
            <span className="font-mono text-ink-3">{column.type}</span>
            <span className="min-w-full text-ink-2">{column.description}</span>
          </li>
        ))}
      </ul>
    </details>
  );
}
