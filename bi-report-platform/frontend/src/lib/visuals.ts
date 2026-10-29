import type { Agg, ChartSpec, ChartType, DateBucket, VisualMeasure, VisualSpec, WidgetStyle } from "../api/types";

/**
 * The visual builder's gallery: what you can pick, and what you may drop on each one.
 *
 * A "visual" is not the same as a ChartType. Clustered, stacked and 100% columns are all drawn by
 * the "bar" renderer with different style flags, exactly as the renderer has always worked, so
 * picking one in the gallery sets both the chart type and those flags. That keeps every report
 * saved before the builder existed readable, and keeps one renderer per shape instead of six.
 *
 * `wells` is what makes drag and drop possible: each one says what it accepts and how many fields
 * fit, so the builder can refuse a drop that wouldn't draw, and tell the person why.
 */

/** Where a field can be dropped. */
export type WellId = "axis" | "legend" | "values" | "values2" | "size" | "rows" | "columns";

export interface Well {
  id: WellId;
  label: string;
  /** "dimension" groups rows; "measure" is summarised; "any" takes either (tables). */
  accepts: "dimension" | "measure" | "any";
  /** How many fields fit. */
  max: number;
  /** The chart draws nothing until this well has a field. */
  required?: boolean;
  /** Shown under the well when it is empty. */
  hint?: string;
}

export interface VisualDef {
  id: string;
  label: string;
  /** The renderer, and the style flags that make this shape. */
  chart: ChartType;
  style?: Partial<WidgetStyle>;
  wells: Well[];
  /** Grouped under this heading in the gallery. */
  group: "Bars" | "Lines" | "Parts" | "Points" | "Tables" | "Numbers";
}

const VALUES = (max: number, label = "Values"): Well =>
  ({ id: "values", label, accepts: "measure", max, required: true, hint: "Numbers to show" });
const AXIS = (max = 2): Well =>
  ({ id: "axis", label: "Axis", accepts: "dimension", max, required: true, hint: "What to group by" });
const LEGEND: Well =
  { id: "legend", label: "Legend", accepts: "dimension", max: 1, hint: "Split into one series per value" };

export const VISUALS: VisualDef[] = [
  { id: "column_clustered", label: "Clustered column", group: "Bars", chart: "bar",
    style: { horizontal: false, stackMode: "none" }, wells: [AXIS(), LEGEND, VALUES(8)] },
  { id: "column_stacked", label: "Stacked column", group: "Bars", chart: "bar",
    style: { horizontal: false, stackMode: "stacked" }, wells: [AXIS(), LEGEND, VALUES(8)] },
  { id: "column_100", label: "100% stacked column", group: "Bars", chart: "bar",
    style: { horizontal: false, stackMode: "full" }, wells: [AXIS(), LEGEND, VALUES(8)] },
  { id: "bar_clustered", label: "Clustered bar", group: "Bars", chart: "bar",
    style: { horizontal: true, stackMode: "none" }, wells: [AXIS(), LEGEND, VALUES(8)] },
  { id: "bar_stacked", label: "Stacked bar", group: "Bars", chart: "bar",
    style: { horizontal: true, stackMode: "stacked" }, wells: [AXIS(), LEGEND, VALUES(8)] },

  { id: "line", label: "Line", group: "Lines", chart: "line", wells: [AXIS(1), LEGEND, VALUES(8)] },
  { id: "area", label: "Area", group: "Lines", chart: "area",
    style: { stackMode: "stacked" }, wells: [AXIS(1), LEGEND, VALUES(8)] },
  { id: "combo", label: "Line and column", group: "Lines", chart: "combo", wells: [
    AXIS(1),
    VALUES(4, "Column values"),
    { id: "values2", label: "Line values", accepts: "measure", max: 4, required: true, hint: "Drawn as a line" },
  ] },

  { id: "pie", label: "Pie", group: "Parts", chart: "pie",
    wells: [{ id: "legend", label: "Legend", accepts: "dimension", max: 1, required: true, hint: "One slice per value" },
            VALUES(1)] },
  { id: "donut", label: "Donut", group: "Parts", chart: "donut",
    wells: [{ id: "legend", label: "Legend", accepts: "dimension", max: 1, required: true, hint: "One slice per value" },
            VALUES(1)] },

  { id: "scatter", label: "Scatter", group: "Points", chart: "scatter", wells: [
    { id: "values", label: "X axis", accepts: "measure", max: 1, required: true, hint: "Across" },
    { id: "values2", label: "Y axis", accepts: "measure", max: 1, required: true, hint: "Up" },
    { id: "legend", label: "Details", accepts: "dimension", max: 1, hint: "One point per value" },
    { id: "size", label: "Size", accepts: "measure", max: 1, hint: "Makes points bigger" },
  ] },

  { id: "table", label: "Table", group: "Tables", chart: "table",
    wells: [{ id: "values", label: "Columns", accepts: "any", max: 12, required: true, hint: "Any fields" }] },
  { id: "matrix", label: "Matrix", group: "Tables", chart: "matrix", wells: [
    { id: "rows", label: "Rows", accepts: "dimension", max: 3, required: true, hint: "Down the side" },
    { id: "columns", label: "Columns", accepts: "dimension", max: 1, hint: "Across the top" },
    VALUES(4),
  ] },

  { id: "kpi", label: "Number", group: "Numbers", chart: "kpi", wells: [VALUES(1)] },
  { id: "gauge", label: "Gauge", group: "Numbers", chart: "gauge", wells: [
    VALUES(1),
    { id: "values2", label: "Target", accepts: "measure", max: 1, hint: "What the dial aims at" },
  ] },
];

export const VISUAL_BY_ID: Record<string, VisualDef> = Object.fromEntries(VISUALS.map((v) => [v.id, v]));

/** The gallery's headings, in the order they are shown. */
export const VISUAL_GROUPS: VisualDef["group"][] = ["Bars", "Lines", "Parts", "Points", "Tables", "Numbers"];

/** The visual a saved chart was built as, matching on the style flags that tell the bar shapes apart. */
export function visualOf(chart: ChartSpec, style: WidgetStyle = {}): VisualDef {
  const candidates = VISUALS.filter((v) => v.chart === chart.type);
  if (candidates.length <= 1) return candidates[0] ?? VISUAL_BY_ID.table;
  const mode = style.stackMode ?? (style.stacked ? "stacked" : "none");
  return candidates.find((v) => (v.style?.horizontal ?? false) === !!style.horizontal
                             && (v.style?.stackMode ?? "none") === mode)
      ?? candidates[0];
}

/** What each well currently holds, by well id. Measures live in their own list. */
export interface Wells {
  axis: string[];
  legend: string[];
  values: VisualMeasure[];
  values2: VisualMeasure[];
  size: VisualMeasure[];
  rows: string[];
  columns: string[];
}

export const emptyWells = (): Wells => ({ axis: [], legend: [], values: [], values2: [], size: [], rows: [], columns: [] });

/** Whether a field may be dropped on a well, and why not when it may not. */
export function canDrop(visual: VisualDef, well: WellId, field: { is_number: boolean }, held: number): string | null {
  const def = visual.wells.find((w) => w.id === well);
  if (!def) return `${visual.label} charts have no ${well}.`;
  if (held >= def.max) return `${def.label} takes ${def.max === 1 ? "one field" : `${def.max} fields`}.`;
  if (def.accepts === "measure" && !field.is_number) return `${def.label} needs a number column.`;
  return null;
}

/** How each aggregate reads in a column name. Must match AGGS in backend/app/visual_query.py. */
export const AGG_LABELS: Record<Agg, string> = {
  sum: "Sum", avg: "Average", min: "Minimum", max: "Maximum", count: "Count", count_distinct: "Distinct count",
};

export const defaultDimensionName = (column: string, bucket?: DateBucket) => (bucket ? `${column} (${bucket})` : column);
export const defaultMeasureName = (m: VisualMeasure) =>
  (m.agg === "count" && !m.column ? "Count" : `${AGG_LABELS[m.agg]} of ${m.column}`);

/** The same rule the compiler uses, so two fields never end up sharing a column name. */
function unique(name: string, taken: Set<string>): string {
  const base = name.slice(0, 60) || "value";
  let candidate = base;
  for (let n = 2; taken.has(candidate.toLowerCase()); n++) candidate = `${base} ${n}`;
  taken.add(candidate.toLowerCase());
  return candidate;
}

/**
 * The spec to compile and the chart spec to draw it with, built together.
 *
 * They have to agree on what each result column is called, so both are produced here and every
 * field is given an explicit name. Dimensions come first because the compiler selects them first,
 * and the chart then points at those names rather than guessing them.
 */
export function buildSpec(visual: VisualDef, wells: Wells, buckets: Record<string, DateBucket | undefined>,
                          base: Pick<VisualSpec, "table" | "filters" | "order" | "limit">):
                          { spec: VisualSpec; chart: ChartSpec } {
  const taken = new Set<string>();
  // Rows and axis share a well in the data, so a matrix and a bar chart compile the same way.
  const axisColumns = [...wells.rows, ...wells.axis];
  const legendColumns = [...wells.columns, ...wells.legend];

  const named = (column: string) => {
    const bucket = buckets[column];
    return { column, bucket, alias: unique(defaultDimensionName(column, bucket), taken) };
  };
  const dimensions = [...axisColumns, ...legendColumns].map(named);
  const nameOfAxis = dimensions.slice(0, axisColumns.length).map((d) => d.alias);
  const nameOfLegend = dimensions.slice(axisColumns.length).map((d) => d.alias);

  const measure = (m: VisualMeasure) => ({ ...m, alias: unique(m.alias?.trim() || defaultMeasureName(m), taken) });
  const values = wells.values.map(measure);
  const values2 = wells.values2.map(measure);
  const size = wells.size.map(measure);

  return {
    spec: { ...base, dimensions, measures: [...values, ...values2, ...size] },
    chart: {
      type: visual.chart,
      x: nameOfAxis[0] ?? "",
      y: values.map((m) => m.alias),
      y2: values2.length ? values2.map((m) => m.alias) : undefined,
      extra: size.length ? size[0].alias : undefined,
      legend: nameOfLegend[0],
    },
  };
}

/** Whether the chosen visual has everything it needs to draw. */
export function missingWell(visual: VisualDef, wells: Wells): Well | null {
  return visual.wells.find((w) => w.required && wells[w.id].length === 0) ?? null;
}
