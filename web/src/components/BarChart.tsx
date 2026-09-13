import { useLayoutEffect, useRef, useState, type JSX, type Ref, type RefObject } from "react";
import type { AskResult } from "../types";
import { formatCell, humanize, isMoneyColumn } from "../format";

// Drawn as SVG so Download SVG can save exactly what is on screen. Every color and font is
// an attribute, never a Tailwind class, because a class would not travel with the file.
const INK = "#FFFFFF";
const INK_2 = "#A1A1AA";
const INK_3 = "#71717A";
const HAIRLINE = "#26262B";
const SEAFOAM = "#87D5B5";
const MUTED_OPACITY = 0.7;
const DISPLAY_FONT = "Archivo, Inter, system-ui, sans-serif";
const BODY_FONT = "Inter, system-ui, sans-serif";
const MONO_FONT = "'JetBrains Mono', ui-monospace, Menlo, monospace";
const TABULAR = { fontVariantNumeric: "tabular-nums" } as const;

// The geometry of the div chart it replaces: 32px sides, 28px top, 32px bottom, a 180px label
// column, 28px bars 18px apart, and the longest bar taking 78% of the room beside the labels.
// Below NARROW_WIDTH (a phone) the sides and label column shrink so the bars keep some room.
const WIDE = { padX: 32, labelWidth: 180, labelGap: 20, labelChars: 27 } as const;
const NARROW = { padX: 16, labelWidth: 96, labelGap: 12, labelChars: 13 } as const; // 13 chars fit 96px at 13px Inter
const NARROW_WIDTH = 560;
const PAD_TOP = 28;
const PAD_BOTTOM = 32;
const CAPTION_SIZE = 15;
const SECTION_GAP = 22;
const LABEL_LINE = 17;
const BAR_HEIGHT = 28;
const BAR_GAP = 18;
const BAR_SPAN = 0.78;
const VALUE_GAP = 12;
const AXIS_PAD = 12;
const TICK_SIZE = 11;
const TICKS = 3; // steps between four axis labels, when they fit
const ZERO_TICK = "$0";
const VALUE_GLYPH = 8; // a JetBrains Mono digit at 13px is 7.8px, rounded up so the value always fits
const TICK_GLYPH = 7; // the same at 11px, 6.6px rounded up
const TICK_CLEARANCE = 12;
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
  const money = isMoneyColumn(chart.y);
  const longestValue = Math.max(...rows.map((row) => formatCell(row[yIndex] ?? null, chart.y).length), 0);
  const layout = chartLayout(width, longestValue, compact(max, money).length);

  return (
    <div ref={frame}>
      <svg ref={svgRef} width={width} height={height} viewBox={`0 0 ${width} ${height}`} role="group" aria-label={caption}>
        <text x={layout.padX} y={PAD_TOP + CAPTION_SIZE / 2} dominantBaseline="central" fill={INK} fontFamily={DISPLAY_FONT} fontSize={CAPTION_SIZE} fontWeight={600}>
          {caption}
        </text>
        {rows.map((row, index) => (
          <Bar
            key={index}
            layout={layout}
            top={barsTop + index * (BAR_HEIGHT + BAR_GAP)}
            length={max > 0 ? (Math.max(values[index] ?? 0, 0) / max) * layout.span : 0}
            largest={values[index] === max}
            label={formatCell(row[xIndex] ?? null, chart.x)}
            value={formatCell(row[yIndex] ?? null, chart.y)}
          />
        ))}
        <Axis y={axisY} width={width} layout={layout} max={max} money={money} />
      </svg>
    </div>
  );
}

export interface ChartLayout {
  padX: number;
  labelWidth: number;
  labelGap: number;
  labelChars: number;
  /** Length of the longest bar. */
  span: number;
  /** Where the axis labels sit, as fractions of the span: four, the two ends, or only the end. */
  ticks: number[];
}

/**
 * The horizontal geometry at a given width. The longest bar takes 78% of the room beside the
 * labels, but never so much that its value (longestValue characters) runs past the chart's edge.
 */
export function chartLayout(width: number, longestValue: number, longestTick: number): ChartLayout {
  const columns = width < NARROW_WIDTH ? NARROW : WIDE;
  const room = Math.max(width - 2 * columns.padX - columns.labelWidth - columns.labelGap, 0);
  const valueRoom = VALUE_GAP + longestValue * VALUE_GLYPH;
  const span = Math.max(Math.min(room * BAR_SPAN, room + columns.padX - valueRoom), 0);
  return { ...columns, span, ticks: tickFractions(span, longestTick) };
}

/** As many evenly spaced axis labels as fit without touching: four, then the two ends, then the end alone. */
function tickFractions(span: number, longestTick: number): number[] {
  const tickWidth = longestTick * TICK_GLYPH + TICK_CLEARANCE;
  if (span / TICKS >= tickWidth) return [0, 1 / 3, 2 / 3, 1];
  if (span >= tickWidth + ZERO_TICK.length * TICK_GLYPH) return [0, 1];
  return [1];
}

interface BarProps {
  layout: ChartLayout;
  top: number;
  length: number;
  largest: boolean;
  label: string;
  value: string;
}

/** One row: its label right-aligned in the label column, the bar, then its value. */
function Bar({ layout, top, length, largest, label, value }: BarProps): JSX.Element {
  const middle = top + BAR_HEIGHT / 2;
  const labelX = layout.padX + layout.labelWidth;
  const barX = labelX + layout.labelGap;
  const lines = wrapLabel(label, layout.labelChars);
  return (
    <g>
      <text x={labelX} y={middle - ((lines.length - 1) * LABEL_LINE) / 2} textAnchor="end" dominantBaseline="central" fill={largest ? INK : INK_2} fontFamily={BODY_FONT} fontSize={13}>
        {lines.map((line, index) => (
          <tspan key={index} x={labelX} dy={index === 0 ? 0 : LABEL_LINE}>
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

interface AxisProps {
  y: number;
  width: number;
  layout: ChartLayout;
  max: number;
  money: boolean;
}

/** The first tick starts at its mark, the last ends at it, and every one between is centered. */
function tickAnchor(fraction: number): "start" | "middle" | "end" {
  if (fraction === 0) return "start";
  if (fraction === 1) return "end";
  return "middle";
}

/** A baseline under the bars with evenly spaced tick labels, spanning the longest bar. */
function Axis({ y, width, layout, max, money }: AxisProps): JSX.Element {
  const { padX, span, ticks } = layout;
  const start = padX + layout.labelWidth + layout.labelGap;
  return (
    <g aria-hidden="true">
      <line x1={padX} x2={width - padX} y1={y + 0.5} y2={y + 0.5} stroke={HAIRLINE} />
      {ticks.map((fraction) => (
        <text key={fraction} data-tick x={start + span * fraction} y={y + AXIS_PAD + TICK_SIZE / 2} textAnchor={tickAnchor(fraction)} dominantBaseline="central" fill={INK_3} fontFamily={MONO_FONT} fontSize={TICK_SIZE} style={TABULAR}>
          {compact(max * fraction, money)}
        </text>
      ))}
    </g>
  );
}

/** A label split into at most two lines at word breaks, the second cut with an ellipsis if needed. */
export function wrapLabel(label: string, limit: number = WIDE.labelChars): string[] {
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
