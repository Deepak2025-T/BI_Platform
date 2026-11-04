import type { Widget, WidgetSize } from "../api/types";

/** Tile widths on the 12-column dashboard grid, narrowest first. */
export const WIDTHS: { size: FixedSize; cols: number; label: string; short: string }[] = [
  { size: "quarter", cols: 3, label: "Quarter", short: "¼" },
  { size: "third", cols: 4, label: "Third", short: "⅓" },
  { size: "half", cols: 6, label: "Half", short: "½" },
  { size: "twothird", cols: 8, label: "Two thirds", short: "⅔" },
  { size: "full", cols: 12, label: "Full width", short: "Full" },
];

export const HEIGHT = { default: 280, min: 160, max: 640, step: 40 };
export const HEIGHTS: [number, string][] = [[200, "Short"], [280, "Medium"], [400, "Tall"], [520, "X-tall"]];

/** How many grid columns a tile spans; "auto" depends on the chart type. */
export function tileCols(w: Widget): number {
  return colsFor(w.size, w.kind === "text" || w.chart.type === "table" ? 12 : w.chart.type === "kpi" ? 4 : 6);
}

/** The width step nearest to a number of columns. */
export function sizeForCols(cols: number): FixedSize {
  return WIDTHS.reduce((best, x) => (Math.abs(x.cols - cols) < Math.abs(best.cols - cols) ? x : best)).size;
}

export type FixedSize = Exclude<WidgetSize, "auto">;

/** Columns for a size; "auto" (or missing) uses autoCols. */
export function colsFor(size: WidgetSize | undefined, autoCols: number): number {
  return WIDTHS.find((x) => x.size === size)?.cols ?? autoCols;
}

/** The width step one narrower (-1) or wider (+1) than a number of columns. */
export function stepWidth(cols: number, dir: -1 | 1): FixedSize {
  const i = WIDTHS.findIndex((x) => x.size === sizeForCols(cols));
  return WIDTHS[Math.min(WIDTHS.length - 1, Math.max(0, i + dir))].size;
}

export const clampHeight = (h: number) =>
  Math.min(HEIGHT.max, Math.max(HEIGHT.min, Math.round(h / HEIGHT.step) * HEIGHT.step));

/** Whether a tile's height can change: KPI numbers and text size to their content. */
export const hasHeight = (w: Widget) => w.kind !== "text" && w.chart.type !== "kpi";

/** "Half × 280 px", or just "Half" when the height is fixed. */
export function sizeLabel(cols: number, height?: number): string {
  const width = WIDTHS.find((x) => x.size === sizeForCols(cols))!.label;
  return height === undefined ? width : `${width} × ${height} px`;
}
