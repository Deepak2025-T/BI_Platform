import type { ClassicLayout, TemplateCategory, NumberFormat, PaletteId, QueryParams, QueryResult, ReportConfig, SectionId, TemplateLayout } from "../api/types";
import { money, pct } from "./format";

export const SECTION_LABELS: Record<SectionId, string> = {
  kpis: "Headline numbers",
  revenue: "Revenue by region",
  products: "Top products",
  insights: "What stands out",
};

export const PALETTES: Record<PaletteId, { label: string; colors: string[] }> = {
  ocean: { label: "Ocean", colors: ["#00B4D8", "#0D3B66", "#F5A623", "#7A8BA3"] },
  warm: { label: "Warm", colors: ["#F3A712", "#A63D40", "#E9C46A", "#5C3D2E"] },
  slate: { label: "Slate", colors: ["#1A2332", "#5B6B80", "#9AA8B8", "#CBD5E0"] },
};

export const PERIOD_OPTIONS = [
  { id: "q1_2024", label: "Q1 2024" },
  { id: "q4_2023", label: "Q4 2023" },
] as const;

export const MEASURE_OPTIONS = [
  { id: "net", label: "Net revenue", hint: "after discounts and refunds" },
  { id: "gross", label: "Gross revenue", hint: "before discounts and refunds" },
] as const;

export const ALL_REGIONS = ["All", "East", "North", "South", "West"];

const REGION_ORDER = ["East", "North", "South", "West"];
export function regionColor(region: string, colors: string[]) {
  const i = REGION_ORDER.indexOf(region);
  return colors[(i < 0 ? 0 : i) % colors.length];
}

/** The domains templates are filed under, in the order the Templates page lists them. */
export const TEMPLATE_CATEGORIES: TemplateCategory[] = ["ERP", "GRC", "Common", "Uncategorised"];

export const CATEGORY_BLURBS: Record<TemplateCategory, string> = {
  ERP: "Sales, CRM, helpdesk, learning and finance, built on your ERP tables",
  GRC: "Risk, controls, audit and compliance, for IBM OpenPages connections",
  Common: "General starting points that work on the sample data",
  Uncategorised: "Not filed under a domain yet",
};

export const ALL_SECTIONS: SectionId[] = ["kpis", "revenue", "products", "insights"];

/** The standard layout. A template's layout is applied on top of it. */
export const DEFAULT_LAYOUT: Required<ClassicLayout> = {
  sections: ALL_SECTIONS,
  chart: "grouped",
  palette: "ocean",
  fmt: "short",
  showValues: false,
  topN: 5,
};

export function defaultConfig(params: QueryParams, layout?: TemplateLayout): ReportConfig {
  return { params: { ...params, region: "All" }, ...DEFAULT_LAYOUT, ...layout };
}

/** The layout part of a report config, for saving it as a template. */
export function layoutOf(c: ReportConfig): TemplateLayout {
  return { sections: c.sections, chart: c.chart, palette: c.palette, fmt: c.fmt, showValues: c.showValues, topN: c.topN };
}

export function monthTotals(r: QueryResult) {
  return r.months.map((_, i) => r.regions.reduce((a, reg) => a + (r.series[reg]?.[i] ?? 0), 0));
}

/** Insights computed from the numbers only, each with the figures it is based on. */
export function buildInsights(r: QueryResult, fmt: NumberFormat) {
  const out: { text: string; basis: string }[] = [];
  const n = r.months.length;
  if (n < 2) return out;
  const first = r.months[0], last = r.months[n - 1];
  const growth = r.regions
    .map((reg) => ({ reg, a: r.series[reg][0], b: r.series[reg][n - 1] }))
    .filter((g) => g.a > 0)
    .map((g) => ({ ...g, g: (g.b - g.a) / g.a }))
    .sort((x, y) => y.g - x.g);

  if (growth.length >= 2) {
    const f = growth[0], s = growth[growth.length - 1];
    out.push({ text: `${f.reg} grew fastest, up ${pct(f.g)} from ${first} to ${last}.`,
      basis: `${f.reg} ${first} ${money(f.a, fmt)} and ${last} ${money(f.b, fmt)}` });
    out.push({ text: `${s.reg} grew slowest, ${s.g >= 0 ? "up" : "down"} ${pct(Math.abs(s.g))}. Worth a closer look.`,
      basis: `${s.reg} ${first} ${money(s.a, fmt)} and ${last} ${money(s.b, fmt)}` });
  }
  const t = monthTotals(r);
  if (t[0] > 0) {
    const ch = (t[n - 1] - t[0]) / t[0];
    out.push({ text: `${last} was ${pct(Math.abs(ch))} ${ch >= 0 ? "higher" : "lower"} than ${first}${r.regions.length > 1 ? " across all regions" : ""}.`,
      basis: `monthly totals ${money(t[0], fmt)} and ${money(t[n - 1], fmt)}` });
  }
  return out;
}
