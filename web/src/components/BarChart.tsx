import { useLayoutEffect, useRef, useState, type JSX, type Ref, type RefObject } from "react";
import type { AskResult } from "../types";
import { formatCell, humanize, isMoneyColumn } from "../format";

// Drawn as SVG so Download SVG can save exactly what is on screen. Every colour and font is
// an attribute, never a Tailwind class, because a class would not travel with the file.
const INK = "#FFFFFF";
const INK_2 = "#A1A1AA";
const INK_3 = "#71717A";
const HAIRLINE = "#26262B";
export const SEAFOAM = "#87D5B5";
export const MUTED_OPACITY = 0.7;
const DISPLAY_FONT = "Archivo, Inter, system-ui, sans-serif";
const BODY_FONT = "Inter, system-ui, sans-serif";
const MONO_FONT = "'JetBrains Mono', ui-monospace, Menlo, monospace";
const TABULAR = { fontVariantNumeric: "tabular-nums" } as const;

// The geometry of the div chart it replaces: 32px sides, 28px top, 32px bottom, a 180px label
// column, 28px bars 18px apart, and the longest bar taking 78% of the room beside the labels.
const PAD_X = 32;
const PAD_TOP = 28;
const PAD_BOTTOM = 32;
const CAPTION_SIZE = 15;
const SECTION_GAP = 22;
const LABEL_WIDTH = 180;
const LABEL_GAP = 20;
const LABEL_CHARS = 27; // what fits in 180px at 13px Inter; longer labels wrap onto a second line
const LABEL_LINE = 17;
const BAR_HEIGHT = 28;
const BAR_GAP = 18;
const BAR_SPAN = 0.78;
const VALUE_GAP = 12;
const AXIS_PAD = 12;
const TICK_SIZE = 11;
const TICKS = 3;
const DEFAULT_WIDTH = 720; // until the first measurement, and in tests where nothing is laid out

interface Props {
  result: AskResult;
  svgRef?: Ref<SVGSVGElement>;
}

/** Horizontal seafoam bars, one per row as the rows arrived, the largest emphasised. */
export function BarChart({ result, svgRef }: Props): JSX.Element | null {
  const frame = useRef<HTMLDivElement>(null);
  const width = useWidth(frame);
  const { chart, columns, rows } = result;
  if (!chart) return null;
  const xIndex = columns.indexOf(chart.x);
  const yIndex = columns.indexOf(chart.y);
  const values = rows.map((row) => (typeof row[yIndex] === "number" ? (row[yIndex] as number) : 0));
  const max = Math.max(...values, 0);
  const barsTop = PAD_TOP + CAPTION_SIZE + SECTION_GAP;
  const axisY = barsTop + rows.length * (BAR_HEIGHT + BAR_GAP) - BAR_GAP + SECTION_GAP;
  const height = axisY + AXIS_PAD + TICK_SIZE + PAD_BOTTOM;
  const caption = `${humanize(chart.y)} by ${humanize(chart.x).toLowerCase()}`;
  const span = Math.max(width - 2 * PAD_X - LABEL_WIDTH - LABEL_GAP, 0) * BAR_SPAN;

  return (
    <div ref={frame}>
      <svg ref={svgRef} width={width} height={height} viewBox={`0 0 ${width} ${height}`} role="group" aria-label={caption}>
        <text x={PAD_X} y={PAD_TOP + CAPTION_SIZE / 2} dominantBaseline="central" fill={INK} fontFamily={DISPLAY_FONT} fontSize={CAPTION_SIZE} fontWeight={600}>
          {caption}
        </text>
        {rows.map((row, index) => (
          <Bar
            key={index}
            top={barsTop + index * (BAR_HEIGHT + BAR_GAP)}
            length={max > 0 ? (Math.max(values[index] ?? 0, 0) / max) * span : 0}
            largest={values[index] === max}
            label={formatCell(row[xIndex] ?? null, chart.x)}
            value={formatCell(row[yIndex] ?? null, chart.y)}
          />
        ))}
        <Axis y={axisY} width={width} span={span} max={max} money={isMoneyColumn(chart.y)} />
      </svg>
    </div>
  );
}

interface BarProps {
  top: number;
  length: number;
  largest: boolean;
  label: string;
  value: string;
}

/** One row: its label right-aligned in the label column, the bar, then its value. */
function Bar({ top, length, largest, label, value }: BarProps): JSX.Element {
  const middle = top + BAR_HEIGHT / 2;
  const barX = PAD_X + LABEL_WIDTH + LABEL_GAP;
  const lines = wrapLabel(label);
  return (
    <g>
      <text x={PAD_X + LABEL_WIDTH} y={middle - ((lines.length - 1) * LABEL_LINE) / 2} textAnchor="end" dominantBaseline="central" fill={largest ? INK : INK_2} fontFamily={BODY_FONT} fontSize={13}>
        {lines.map((line, index) => (
          <tspan key={index} x={PAD_X + LABEL_WIDTH} dy={index === 0 ? 0 : LABEL_LINE}>
            {line}
          </tspan>
        ))}
      </text>
      <rect data-bar data-largest={largest || undefined} role="img" aria-label={`${label}: ${value}`} x={barX} y={top} width={length} height={BAR_HEIGHT} rx={4} fill={SEAFOAM} fillOpacity={largest ? 1 : MUTED_OPACITY} />
      <text x={barX + length + VALUE_GAP} y={middle} dominantBaseline="central" fill={INK} fontFamily={MONO_FONT} fontSize={13} fontWeight={500} style={TABULAR}>
        {value}
      </text>
    </g>
  );
}

/** A baseline under the bars with four evenly spaced ticks, spanning the longest bar. */
function Axis({ y, width, span, max, money }: { y: number; width: number; span: number; max: number; money: boolean }): JSX.Element {
  const start = PAD_X + LABEL_WIDTH + LABEL_GAP;
  const anchors = ["start", "middle", "middle", "end"] as const;
  return (
    <g aria-hidden="true">
      <line x1={PAD_X} x2={width - PAD_X} y1={y + 0.5} y2={y + 0.5} stroke={HAIRLINE} />
      {anchors.map((anchor, step) => (
        <text key={step} x={start + (span * step) / TICKS} y={y + AXIS_PAD + TICK_SIZE / 2} textAnchor={anchor} dominantBaseline="central" fill={INK_3} fontFamily={MONO_FONT} fontSize={TICK_SIZE} style={TABULAR}>
          {compact((max * step) / TICKS, money)}
        </text>
      ))}
    </g>
  );
}

/** A label split into at most two lines at word breaks, the second cut with an ellipsis if needed. */
export function wrapLabel(label: string, limit = LABEL_CHARS): string[] {
  if (label.length <= limit) return [label];
  const breakAt = label.lastIndexOf(" ", limit);
  const cut = breakAt > 0 ? breakAt : limit;
  const rest = label.slice(cut).trim();
  return [label.slice(0, cut), rest.length > limit ? `${rest.slice(0, limit - 1).trimEnd()}…` : rest];
}

/** The rendered width of an element, following it as the layout changes. */
function useWidth(ref: RefObject<HTMLElement | null>): number {
  const [width, setWidth] = useState(DEFAULT_WIDTH);
  useLayoutEffect(() => {
    const element = ref.current;
    if (!element || typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(([entry]) => {
      const measured = Math.floor(entry?.contentRect.width ?? 0);
      if (measured > 0) setWidth(measured);
    });
    observer.observe(element);
    return () => observer.disconnect();
  }, [ref]);
  return width;
}

function compact(value: number, money: boolean): string {
  const text = new Intl.NumberFormat("en-US", { notation: "compact", maximumFractionDigits: 1 }).format(value);
  return money ? `$${text}` : text;
}
