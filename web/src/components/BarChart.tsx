import type { JSX } from "react";
import type { AskResult } from "../types";
import { formatCell, humanize } from "../format";

const LABEL_WIDTH = "180px";

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
                  style={{ width: `${max > 0 ? (value / max) * 78 : 0}%` }}
                />
                <span className="num text-[13px] font-medium">{yLabel}</span>
              </span>
            </li>
          );
        })}
      </ul>
    </figure>
  );
}
