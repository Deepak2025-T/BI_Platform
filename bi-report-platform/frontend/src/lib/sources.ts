import type { Cell, ChartSpec, ChartType, DataSourceInfo } from "../api/types";

/** Select value for a source: "builtin" or the connection id. */
export const sourceValue = (s: Pick<DataSourceInfo, "id">) => (s.id === null ? "builtin" : String(s.id));
export const sourceIdOf = (value: string): number | null => (value === "builtin" ? null : Number(value));

const SOURCE_KEY = "bi_source";

/** The database picked last time, remembered in this browser only. */
export function rememberedSource(): string | null {
  try { return localStorage.getItem(SOURCE_KEY); } catch { return null; }
}

export function rememberSource(value: string) {
  try { localStorage.setItem(SOURCE_KEY, value); } catch { /* storage unavailable */ }
}

export const CHART_LABELS: Record<ChartType, string> = {
  kpi: "Number", bar: "Bars", line: "Line", area: "Area", pie: "Pie", table: "Table",
  combo: "Line and column", scatter: "Scatter", donut: "Donut", gauge: "Gauge", matrix: "Matrix",
  heatmap: "Heatmap",
};

/**
 * The value columns of a result: the ones that hold a number and nothing but numbers.
 *
 * A column of nothing but nulls is not one of them. Counting it as a number left a chart whose
 * only category column had come back empty with no categories at all, so every shape but Number
 * and Table said it had nothing to draw.
 */
export const numericColumns = (columns: string[], rows: Cell[][]) =>
  columns.filter((_, i) => rows.some((r) => typeof r[i] === "number")
                        && rows.every((r) => r[i] === null || typeof r[i] === "number"));

/**
 * Why this data can't be drawn as that type, or "" when it can.
 *
 * The picker shows every shape the app knows, so a shape this result can't fill has to say so
 * rather than quietly falling back to the rows - which is what the renderer does, and what makes
 * a type switch look like it did nothing.
 */
export function cannotDraw(type: ChartType, columns: string[], rows: Cell[][]): string {
  if (type === "combo" || type === "scatter" || type === "gauge") return "Not drawn yet";
  const numeric = numericColumns(columns, rows);
  const others = columns.filter((c) => !numeric.includes(c));
  if (type === "table" || type === "matrix") return "";
  if (!numeric.length) return "Needs a number column";
  if (type === "kpi") return "";
  if (!others.length) return "Needs a column of names or dates";
  // A grid is one cell per pair, so it needs a second column of names: one down the side, one
  // across the top.
  if (type === "heatmap" && others.length < 2) return "Needs two columns of names: rows and columns";
  return "";
}

/** Switches a chart to another type, choosing columns that fit the data. */
export function retype(chart: ChartSpec, type: ChartType, columns: string[], rows: Cell[][]): ChartSpec {
  const numeric = numericColumns(columns, rows);
  const others = columns.filter((c) => !numeric.includes(c));
  if (type === "table" || type === "matrix") return { type, x: "", y: [] };
  const y = chart.y.filter((c) => numeric.includes(c));
  // Number tiles and gauges show one value and have no axis.
  if (type === "kpi" || type === "gauge") return { type, x: "", y: (y.length ? y : numeric).slice(0, 1) };
  const x = others.includes(chart.x) ? chart.x : others[0] ?? "";
  // A heat map is the one shape that names two category columns: the rows down the side and the
  // columns across the top. Without the second it has no grid and the renderer shows the rows
  // instead, so it is chosen here rather than left for the person to find.
  if (type === "heatmap") {
    const across = chart.legend && chart.legend !== x && others.includes(chart.legend)
      ? chart.legend : others.find((c) => c !== x) ?? "";
    return { type, x, y: (y.length ? y : numeric).slice(0, 1), legend: across };
  }
  // Pies and donuts draw one slice per row, so they take a single value column.
  const single = type === "pie" || type === "donut";
  const ys = y.length ? y : numeric.slice(0, single ? 1 : 3);
  return { type, x, y: single ? ys.slice(0, 1) : ys };
}
