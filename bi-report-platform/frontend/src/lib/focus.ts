/**
 * Clicking a chart and seeing the records behind it.
 *
 * A dashboard's charts are counts: "17 risks are High". The question that follows is always
 * "which 17?", and the answer is already on the page - the section's summary table holds one row
 * per record. So a click doesn't fetch anything. It names a column and a value, and every table on
 * the report that has that column shows just the rows that match. The charts are left whole, so
 * the selection reads against its own context rather than against itself.
 */

import type { Cell, ChartSpec, ChartType, Widget } from "../api/types";
import { axisText, cellText, columnLabel } from "./format";

/** What the reader has clicked into: one value of one column, and the chart it was clicked on. */
export interface Focus {
  /** The column the clicked chart groups by, as that chart's own query names it. */
  column: string;
  value: string;
  widgetId: string;
}

/** The chart types a click means something on: each one draws a row per category. */
const CLICKABLE: ChartType[] = ["bar", "line", "area", "pie", "donut", "heatmap", "combo"];

/** The column a click on this chart picks out, or "" when a click means nothing on it. */
export function clickColumn(chart: ChartSpec): string {
  return CLICKABLE.includes(chart.type) && chart.x ? chart.x : "";
}

/** Tables are what a selection acts on; everything else is left whole. */
export const showsRecords = (w: Widget) => w.chart?.type === "table" || w.chart?.type === "matrix";

/**
 * Which column of a table a selection applies to, or -1.
 *
 * Names are matched exactly first. A chart and a table on the same dashboard are separate queries,
 * though, and OpenPages files one field under a different group per object type - Domain is
 * "OPSS-Rsk:Domain" on a risk and "OPSS-Ctl:Domain" on a control - so a second pass matches on the
 * words people actually read, which is what both of those come out as.
 */
export function focusIndex(columns: string[], column: string): number {
  const exact = columns.indexOf(column);
  if (exact >= 0) return exact;
  const want = columnLabel(column).toLowerCase();
  return columns.findIndex((c) => columnLabel(c).toLowerCase() === want);
}

/**
 * Whether one table cell is the value that was clicked.
 *
 * Two things stop a straight comparison. A field a record can hold several of at once arrives as
 * one cell, "Fraud, Conduct". And a chart grouped on a date was folded to months before it was
 * drawn, so the bar says "11/25" while the table still holds the timestamp it was folded from -
 * a click on a month would otherwise match nothing, which is the one thing a reader notices.
 */
const holds = (cell: string, value: string) =>
  cell === value || cell.split(", ").includes(value) || axisText(cell) === value;

/**
 * The rows of one table that match the selection, or null when this table has no such column -
 * which is the ordinary case for most tiles and means "leave this one alone".
 */
export function focusRows(columns: string[], rows: Cell[][], focus: Focus): Cell[][] | null {
  const i = focusIndex(columns, focus.column);
  if (i < 0) return null;
  return rows.filter((r) => holds(cellText(r[i]), focus.value));
}

/** How the selection reads above the report: "Residual rating: High". */
export const focusLabel = (focus: Focus) => `${columnLabel(focus.column)}: ${focus.value}`;
