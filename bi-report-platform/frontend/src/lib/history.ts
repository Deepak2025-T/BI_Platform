import type { Cell, Widget } from "../api/types";
import { cellText } from "./format";

/** One chart's numbers at one refresh (see backend history.py). */
export type HistoryPoint = { t: string; value?: number | null; values?: Record<string, number> };

export type CompareWith = "previous" | "1d" | "7d" | "30d" | "quarter" | "none";

export const COMPARE_OPTIONS: [CompareWith, string][] = [
  ["previous", "Previous refresh"], ["1d", "1 day ago"], ["7d", "1 week ago"], ["30d", "1 month ago"],
  ["quarter", "Start of quarter"], ["none", "No comparison"],
];

/** The time to compare with, as ISO; undefined means the refresh before the latest. */
export function compareAt(c: CompareWith, now = new Date()): string | undefined {
  const d = new Date(now);
  if (c === "1d") d.setDate(d.getDate() - 1);
  else if (c === "7d") d.setDate(d.getDate() - 7);
  else if (c === "30d") d.setMonth(d.getMonth() - 1);
  else if (c === "quarter") { d.setMonth(Math.floor(d.getMonth() / 3) * 3, 1); d.setHours(0, 0, 0, 0); }
  else return undefined;
  return d.toISOString();
}

const isNum = (v: Cell): v is number => typeof v === "number";

/** A chart's single number, or its value per category: the same rules as the backend's summaries. */
export function summarize(w: Widget, columns: string[], rows: Cell[][]): { value?: number | null; values?: Record<string, number> } | null {
  const ys = w.chart.y.filter((c) => columns.includes(c));
  if (w.chart.type === "kpi" || (rows.length === 1 && !w.chart.x)) {
    if (!rows.length) return null;
    const col = ys[0] ?? columns.find((_, i) => isNum(rows[0][i]));
    if (!col) return null;
    const v = rows[0][columns.indexOf(col)];
    return { value: isNum(v) ? v : null };
  }
  if (["bar", "line", "area", "pie"].includes(w.chart.type) && columns.includes(w.chart.x) && ys.length) {
    const xi = columns.indexOf(w.chart.x), yi = columns.indexOf(ys[0]);
    const values: Record<string, number> = {};
    for (const r of rows.slice(0, 30)) if (isNum(r[yi])) values[r[xi] === null ? "(blank)" : String(r[xi])] = r[yi] as number;
    return { values };
  }
  return null;
}

export type Direction = "up" | "down" | "same";

/** "▲ 3 (+18%)" and which way it moved. */
export function delta(now: number, then: number, fmt: (v: number) => string): { text: string; dir: Direction } {
  const diff = now - then;
  if (diff === 0) return { text: "No change", dir: "same" };
  const pct = then !== 0 ? ` (${diff > 0 ? "+" : ""}${Math.round((diff / Math.abs(then)) * 100)}%)` : "";
  return { text: `${diff > 0 ? "▲" : "▼"} ${fmt(Math.abs(diff))}${pct}`, dir: diff > 0 ? "up" : "down" };
}

/** Good, bad or neutral, given which way is good for this number. */
export function tone(dir: Direction, goodWhen?: "up" | "down"): "good" | "bad" | "neutral" {
  if (dir === "same" || !goodWhen) return "neutral";
  return dir === goodWhen ? "good" : "bad";
}

export interface RowChanges {
  added: Cell[][];
  removed: Cell[][];
  /** Rows with the same first-column value whose other values changed. */
  changed: { key: string; cells: { column: string; from: Cell; to: Cell }[] }[];
}

/** What changed in a table between two results. Rows are matched on the first column when its values
 *  are unique in both; otherwise whole rows are compared (so changes show as one gone, one new). */
export function rowChanges(columns: string[], now: Cell[][], thenColumns: string[], then: Cell[][]): RowChanges {
  const align = then.map((r) => columns.map((c) => { const i = thenColumns.indexOf(c); return i < 0 ? null : r[i]; }));
  const keyOf = (r: Cell[]) => cellText(r[0]);
  const unique = (rows: Cell[][]) => new Set(rows.map(keyOf)).size === rows.length && rows.every((r) => r[0] !== null);
  if (columns.length > 1 && unique(now) && unique(align)) {
    const before = new Map(align.map((r) => [keyOf(r), r]));
    const after = new Map(now.map((r) => [keyOf(r), r]));
    const changed: RowChanges["changed"] = [];
    for (const [k, r] of after) {
      const old = before.get(k);
      if (!old) continue;
      const cells = columns.map((c, i) => ({ column: c, from: old[i], to: r[i] })).filter((x, i) => i > 0 && cellText(x.from) !== cellText(x.to));
      if (cells.length) changed.push({ key: k, cells });
    }
    return { added: now.filter((r) => !before.has(keyOf(r))), removed: align.filter((r) => !after.has(keyOf(r))), changed };
  }
  const text = (r: Cell[]) => JSON.stringify(r.map(cellText));
  const count = (rows: Cell[][]) => { const m = new Map<string, number>(); rows.forEach((r) => m.set(text(r), (m.get(text(r)) ?? 0) + 1)); return m; };
  const a = count(align), b = count(now);
  const take = (rows: Cell[][], other: Map<string, number>) => {
    const left = new Map(other);
    return rows.filter((r) => { const n = left.get(text(r)) ?? 0; if (n > 0) { left.set(text(r), n - 1); return false; } return true; });
  };
  return { added: take(now, a), removed: take(align, b), changed: [] };
}

/** Labels for points on a time axis: times when everything is on one day, dates otherwise. */
export function timeLabels(times: string[]): string[] {
  const days = new Set(times.map((t) => new Date(t).toDateString()));
  return times.map((t) => new Date(t).toLocaleString(undefined, days.size === 1
    ? { hour: "2-digit", minute: "2-digit" }
    : { day: "numeric", month: "short", ...(times.length <= 14 && days.size < times.length ? { hour: "2-digit", minute: "2-digit" } : {}) }));
}
