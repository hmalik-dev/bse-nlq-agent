import type { JSX } from "react";
import type { AskResult } from "../types";
import { formatCell, humanize, isMoneyColumn } from "../format";

const LABEL_WIDTH = "180px";
const BAR_SPAN = 78; // percent of the row the longest bar takes, leaving room for its value label
const TICKS = 3;

/** Horizontal seafoam bars, one per row as the rows arrived, the largest emphasised. */
export function BarChart({ result }: { result: AskResult }): JSX.Element | null {
  const { chart, columns, rows } = result;
  if (!chart) return null;
  const xIndex = columns.indexOf(chart.x);
  const yIndex = columns.indexOf(chart.y);
  const values = rows.map((row) => {
    const value = row[yIndex];
    return typeof value === "number" ? value : 0;
  });
  const max = Math.max(...values, 0);

  return (
    <figure className="flex flex-col gap-[22px] px-8 pb-8 pt-7">
      <figcaption className="font-display text-[15px] font-semibold">
        {humanize(chart.y)} by {humanize(chart.x).toLowerCase()}
      </figcaption>
      <ul className="flex flex-col gap-[18px]" aria-label="Bars">
        {rows.map((row, index) => {
          const value = values[index] ?? 0;
          const largest = value === max;
          const xLabel = formatCell(row[xIndex] ?? null, chart.x);
          const yLabel = formatCell(row[yIndex] ?? null, chart.y);
          return (
            <li
              key={index}
              className="grid items-center gap-5"
              style={{ gridTemplateColumns: `${LABEL_WIDTH} 1fr` }}
            >
              <span className={`text-right text-[13px] leading-[1.3] ${largest ? "text-ink" : "text-ink-2"}`}>
                {xLabel}
              </span>
              <span className="flex items-center gap-3">
                <span
                  role="img"
                  aria-label={`${xLabel}: ${yLabel}`}
                  data-bar
                  className={`h-7 rounded-[4px] bg-seafoam ${largest ? "" : "opacity-70"}`}
                  style={{ width: `${max > 0 ? (value / max) * BAR_SPAN : 0}%` }}
                />
                <span className="num text-[13px] font-medium">{yLabel}</span>
              </span>
            </li>
          );
        })}
      </ul>
      <Axis max={max} money={isMoneyColumn(chart.y)} />
    </figure>
  );
}

/** A baseline under the bars with four evenly spaced ticks, spanning the longest bar. */
function Axis({ max, money }: { max: number; money: boolean }): JSX.Element {
  const ticks = [0, 1, 2, 3].map((step) => (max * step) / TICKS);
  return (
    <div
      className="grid gap-5 border-t border-hairline pt-3"
      style={{ gridTemplateColumns: `${LABEL_WIDTH} 1fr` }}
      aria-hidden="true"
    >
      <span />
      <span
        className="flex justify-between font-mono text-[11px] tabular-nums text-ink-3"
        style={{ width: `${BAR_SPAN}%` }}
      >
        {ticks.map((tick) => (
          <span key={tick}>{compact(tick, money)}</span>
        ))}
      </span>
    </div>
  );
}

function compact(value: number, money: boolean): string {
  const text = new Intl.NumberFormat("en-US", { notation: "compact", maximumFractionDigits: 1 }).format(value);
  return money ? `$${text}` : text;
}
