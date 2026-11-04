import type { NumberFormat } from "../api/types";

export function money(v: number, fmt: NumberFormat = "short"): string {
  if (fmt === "full") return "$" + Math.round(v).toLocaleString("en-US");
  const abs = Math.abs(v);
  if (abs >= 1_000_000) return "$" + (v / 1_000_000).toFixed(2).replace(/\.?0+$/, "") + "M";
  if (abs >= 1_000) return "$" + Math.round(v / 1_000) + "K";
  return "$" + Math.round(v);
}

export const pct = (x: number) => `${Math.round(x * 100)}%`;

export function shortDate(iso: string) {
  return new Date(iso).toLocaleDateString(undefined, { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
}

/** Numbers of unknown meaning (counts, amounts) in a short form: 1,234 / 12.3K / 4.5M. */
export function compact(v: number): string {
  if (!Number.isFinite(v)) return String(v);
  return Math.abs(v) < 10_000
    ? v.toLocaleString(undefined, { maximumFractionDigits: 2 })
    : v.toLocaleString(undefined, { notation: "compact", maximumFractionDigits: 1 });
}

/** A query result cell as text. */
export function cellText(v: unknown): string {
  if (v === null || v === undefined) return "";
  if (typeof v === "number") return v.toLocaleString(undefined, { maximumFractionDigits: 2 });
  return String(v);
}

/** "total_revenue" -> "Total revenue" */
export function columnLabel(name: string): string {
  // OpenPages: "OPSS-Ctl:Control Type" -> "Control Type", "Count_Resource ID" -> "Count".
  if (/^Count_/.test(name)) return "Count";
  const op = /^[A-Za-z][\w -]*:(.+)$/.exec(name);
  if (op) name = op[1];
  const s = name.replace(/[_]+/g, " ").trim();
  return s.charAt(0).toUpperCase() + s.slice(1);
}

/** A chart value in the chart's number format: auto (1.2M), full (1,234,567), currency or percent. */
export function formatValue(v: number, style: { format?: string; currency?: string } = {}): string {
  if (!Number.isFinite(v)) return String(v);
  switch (style.format) {
    case "full": return v.toLocaleString(undefined, { maximumFractionDigits: 2 });
    case "currency": {
      const symbol = style.currency || "£";
      const body = Math.abs(v) >= 100_000 ? compact(Math.abs(v)) : Math.abs(v).toLocaleString(undefined, { maximumFractionDigits: 0 });
      return `${v < 0 ? "-" : ""}${symbol}${body}`;
    }
    case "percent": return `${(v * 100).toLocaleString(undefined, { maximumFractionDigits: 1 })}%`;
    default: return compact(v);
  }
}
