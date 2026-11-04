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
};

/** Switches a chart to another type, choosing columns that fit the data. */
export function retype(chart: ChartSpec, type: ChartType, columns: string[], rows: Cell[][]): ChartSpec {
  const numeric = columns.filter((_, i) => rows.length > 0 && rows.every((r) => r[i] === null || typeof r[i] === "number"));
  const others = columns.filter((c) => !numeric.includes(c));
  if (type === "table") return { type, x: "", y: [] };
  const y = chart.y.filter((c) => numeric.includes(c));
  if (type === "kpi") return { type, x: "", y: (y.length ? y : numeric).slice(0, 1) };
  const x = others.includes(chart.x) ? chart.x : others[0] ?? "";
  const ys = y.length ? y : numeric.slice(0, type === "pie" ? 1 : 3);
  return { type, x, y: type === "pie" ? ys.slice(0, 1) : ys };
}
