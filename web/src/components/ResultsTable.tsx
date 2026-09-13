import type { JSX } from "react";
import type { Cell } from "../types";
import { formatCell, isNumericColumn } from "../format";
import { Badge, badgeFor } from "./Badge";

interface Props {
  columns: string[];
  rows: Cell[][];
}

/**
 * A real table. Numbers are right-aligned tabular mono; wide results scroll inside the panel.
 * A lone column stays left-aligned, so its header and value sit together instead of across a blank row.
 */
export function ResultsTable({ columns, rows }: Props): JSX.Element {
  if (rows.length === 0) return <p className="px-5 py-6 text-sm text-ink-2">No rows to show.</p>;
  const numeric = columns.map((_, index) => isNumericColumn(rows, index));
  const lone = columns.length === 1;
  const align = (index: number): string => {
    if (!numeric[index]) return "text-left";
    return lone ? "font-mono tabular-nums text-left" : "num";
  };
  return (
    <div role="region" aria-label="Results table" tabIndex={0} className="overflow-x-auto">
      <table className="w-full min-w-max border-collapse">
        <thead>
          <tr className="bg-sql">
            {columns.map((column, index) => (
              <th
                key={column}
                scope="col"
                className={`border-b border-hairline px-5 py-3 font-mono text-[11px] font-medium uppercase tracking-[0.08em] text-ink-3 ${align(index)}`}
              >
                {column.replace(/_/g, " ")}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, rowIndex) => (
            <tr key={rowIndex} className="border-b border-hairline last:border-b-0">
              {row.map((cell, index) => (
                <td
                  key={index}
                  className={`whitespace-nowrap px-5 py-3.5 text-sm ${align(index)} ${numeric[index] ? "" : "text-ink-2"}`}
                >
                  {index === 0 ? <FirstCell value={cell} column={columns[0] ?? ""} /> : formatCell(cell, columns[index] ?? "")}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function FirstCell({ value, column }: { value: Cell; column: string }): JSX.Element {
  const text = formatCell(value, column);
  const badge = badgeFor(text);
  return (
    <span className="inline-flex items-center gap-2.5 text-ink">
      {badge && <Badge name={badge} />}
      {text}
    </span>
  );
}
