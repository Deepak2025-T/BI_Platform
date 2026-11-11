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

/**
 * The currencies a chart can be shown in. `symbol` goes in front of the number; a code such as AED
 * is written as the code because that is how people there write it.
 */
export const CURRENCIES: { symbol: string; label: string }[] = [
  { symbol: "$", label: "US dollar ($)" },
  { symbol: "₹", label: "Indian rupee (₹)" },
  { symbol: "€", label: "Euro (€)" },
  { symbol: "£", label: "Pound sterling (£)" },
  { symbol: "AED ", label: "UAE dirham (AED)" },
  { symbol: "SAR ", label: "Saudi riyal (SAR)" },
  { symbol: "¥", label: "Yen / yuan (¥)" },
];

export type NumberScale = "auto" | "none" | "thousand" | "lakh" | "crore" | "million" | "billion";

/** How much to divide by, and what to call the result. */
const UNITS: Record<Exclude<NumberScale, "auto" | "none">, [number, string]> = {
  thousand: [1e3, "K"],
  lakh: [1e5, " L"],
  crore: [1e7, " Cr"],
  million: [1e6, "M"],
  billion: [1e9, "B"],
};

export const SCALES: [NumberScale, string][] = [
  ["auto", "Automatic"], ["none", "Full digits (1,234,567)"], ["thousand", "Thousands (1.2K)"],
  ["lakh", "Lakh (12.3 L)"], ["crore", "Crore (1.2 Cr)"], ["million", "Millions (1.2M)"], ["billion", "Billions (1.2B)"],
];

/** The number to show and the unit to put after it. */
function scaled(v: number, scale: NumberScale, indian: boolean): [number, string] {
  if (scale === "none") return [v, ""];
  if (scale !== "auto") {
    const [divisor, suffix] = UNITS[scale];
    return [v / divisor, suffix];
  }
  // Automatic: the largest unit the number fills, counting the way the digits are grouped.
  // Below ten thousand nothing is shortened, because "1.2K" hides more than it saves.
  const abs = Math.abs(v);
  if (abs < 10_000) return [v, ""];
  for (const step of indian ? (["crore", "lakh", "thousand"] as const) : (["billion", "million", "thousand"] as const)) {
    const [divisor, suffix] = UNITS[step];
    if (abs >= divisor) return [v / divisor, suffix];
  }
  return [v, ""];
}

/**
 * A chart value in the chart's number format.
 *
 * `format` is what the number means (a plain count, money, a proportion), `scale` is how far it is
 * shortened, and `numerals` is how the digits are grouped: "indian" writes 1,23,45,678 and shortens
 * to lakh and crore, which is what a reader in India expects of a rupee figure.
 */
export function formatValue(
  v: number,
  style: { format?: string; currency?: string; scale?: NumberScale; numerals?: string } = {},
): string {
  if (!Number.isFinite(v)) return String(v);
  const indian = style.numerals === "indian";
  const locale = indian ? "en-IN" : undefined;
  if (style.format === "percent") {
    return `${(v * 100).toLocaleString(locale, { maximumFractionDigits: 1 })}%`;
  }
  // "Full" means every digit unless the chart asks for a unit; everything else shortens by itself.
  const scale = style.scale ?? (style.format === "full" ? "none" : "auto");
  const [shown, suffix] = scaled(v, scale, indian);
  // A unit someone chose is worth two decimals (1.23 Cr says more than 1.2 Cr); one the chart chose
  // for itself keeps the one decimal these charts have always shown.
  const digits = !suffix ? 2 : scale === "auto" ? 1 : Math.abs(shown) < 100 ? 2 : 1;
  const body = Math.abs(shown).toLocaleString(locale, { maximumFractionDigits: digits });
  const symbol = style.format === "currency" ? style.currency || "£" : "";
  return `${v < 0 ? "-" : ""}${symbol}${body}${suffix}`;
}
