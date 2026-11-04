import ReactEChartsCore from "echarts-for-react/lib/core";
import { BarChart, LineChart, PieChart } from "echarts/charts";
import { GridComponent, LegendComponent, TooltipComponent } from "echarts/components";
import * as echarts from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";
import type { Cell, ChartSpec, WidgetStyle } from "../api/types";
import { isDark } from "../lib/cardColors";
import { columnLabel, formatValue } from "../lib/format";
import { delta, tone } from "../lib/history";
import ResultTable from "./ResultTable";

echarts.use([BarChart, LineChart, PieChart, GridComponent, LegendComponent, TooltipComponent, CanvasRenderer]);

export const CHART_COLORS = ["#00B4D8", "#0D3B66", "#F5A623", "#7A8BA3", "#2A9D8F", "#A63D40", "#6D597A", "#1E7F4F"];

interface Props {
  columns: string[];
  rows: Cell[][];
  chart: ChartSpec;
  style?: WidgetStyle;
  height?: number;
  /** Tables: scroll inside this height (default: show every row). */
  tableHeight?: number;
  truncated?: boolean;
  /** The same chart at an earlier refresh: number tiles show the change, charts show it alongside. */
  compare?: { label: string; columns: string[]; rows: Cell[][] };
  /** Number tiles: the value at each kept refresh, oldest first, drawn as a small line. */
  spark?: number[];
  /** Fit the value axis to the data instead of starting at 0 (history lines, where small changes matter). */
  fitAxis?: boolean;
}

/** A small line of a number tile's history. */
function Sparkline({ values, color }: { values: number[]; color: string }) {
  const min = Math.min(...values), max = Math.max(...values), span = max - min || 1;
  const points = values.map((v, i) => `${(i / (values.length - 1)) * 100},${22 - ((v - min) / span) * 20}`).join(" ");
  return (
    <svg className="sparkline" viewBox="0 0 100 24" preserveAspectRatio="none" role="img"
      aria-label={`Trend over ${values.length} refreshes, from ${values[0]} to ${values[values.length - 1]}`}>
      <polyline points={points} fill="none" stroke={color} strokeWidth="2" vectorEffect="non-scaling-stroke" strokeLinejoin="round" />
    </svg>
  );
}

/** Draws any query result from a chart spec: KPI tile, bar, line, area, pie or table, styled by `style`. */
export default function DataChart({ columns, rows, chart, style = {}, height = 280, tableHeight, truncated, compare, spark, fitAxis }: Props) {
  const xi = columns.indexOf(chart.x);
  const ys = chart.y.filter((c) => columns.includes(c));
  const fmt = (v: number) => formatValue(v, style);
  const colors = style.color ? [style.color, ...CHART_COLORS.filter((c) => c.toUpperCase() !== style.color!.toUpperCase())] : CHART_COLORS;
  // Text and lines that read on the card's background.
  const dark = isDark(style.cardBg);
  const ink = dark ? "#D6E2EE" : "#4A5568", strong = dark ? "#FFFFFF" : "#1A2332";
  const gridLine = dark ? "rgba(255,255,255,.12)" : "#EDF2F7", axisLine = dark ? "rgba(255,255,255,.28)" : "#CFDCE8";
  const AXIS = { axisLabel: { color: ink }, axisLine: { lineStyle: { color: axisLine } }, axisTick: { show: false } };

  if (chart.type === "kpi") {
    const col = ys[0] ?? columns.find((_, i) => typeof rows[0]?.[i] === "number");
    const value = col ? rows[0]?.[columns.indexOf(col)] : null;
    const thenIndex = compare && col ? compare.columns.indexOf(col) : -1;
    const then = thenIndex >= 0 ? compare!.rows[0]?.[thenIndex] : null;
    const change = typeof value === "number" && typeof then === "number" ? delta(value, then, fmt) : null;
    return (
      <div className="kpi-tile">
        <span className="kpi-value" style={style.color ? { color: style.color } : undefined}>
          {typeof value === "number" ? fmt(value) : value ?? "–"}
        </span>
        {col && columnLabel(col) !== "Count" && <span className="kpi-label">{columnLabel(col)}</span>}
        {change && (
          <span className={`kpi-delta ${tone(change.dir, style.goodWhen)}`} title={`${fmt(then as number)} on ${compare!.label}`}>
            {change.text} <span className="muted">since {compare!.label}</span>
          </span>
        )}
        {spark && spark.length > 1 && <Sparkline values={spark} color={style.color ?? CHART_COLORS[0]} />}
      </div>
    );
  }

  // Sort by the first value column when asked (bars, pies and tables read better ranked).
  const sortIndex = ys.length ? columns.indexOf(ys[0]) : -1;
  const sorted = style.sort && style.sort !== "none" && sortIndex >= 0
    ? [...rows].sort((a, b) => (Number(a[sortIndex]) - Number(b[sortIndex])) * (style.sort === "desc" ? -1 : 1))
    : rows;

  // A chart needs a category column and at least one number; otherwise show the rows.
  if (chart.type === "table" || xi < 0 || ys.length === 0) {
    const table = <ResultTable columns={columns} rows={sorted} truncated={truncated} limit={50} />;
    return tableHeight ? <div className="table-scroll" style={{ maxHeight: tableHeight }}>{table}</div> : table;
  }

  const labels = sorted.map((r) => String(r[xi] ?? ""));
  const values = (y: string) => sorted.map((r) => {
    const v = r[columns.indexOf(y)];
    return typeof v === "number" ? v : Number(v);
  });
  const legend = style.legend !== false;
  // The earlier refresh's value per category, for each value column.
  const thenOf = (y: string) => {
    const cx = compare ? compare.columns.indexOf(chart.x) : -1, cy = compare ? compare.columns.indexOf(y) : -1;
    if (cx < 0 || cy < 0) return null;
    return new Map(compare!.rows.map((r) => [String(r[cx] ?? ""), typeof r[cy] === "number" ? r[cy] as number : Number(r[cy])]));
  };
  const label = (position: string) => ({ show: !!style.showValues, position, fontSize: 11, color: strong,
                                         formatter: (p: { value: number }) => fmt(p.value) });

  let option;
  let changes: string[] = [];
  if (chart.type === "pie") {
    const before = thenOf(ys[0]);
    if (before) {
      const now = values(ys[0]);
      changes = labels.map((l, i) => ({ l, d: now[i] - (before.get(l) ?? 0) })).filter((x) => x.d !== 0)
        .sort((a, b) => Math.abs(b.d) - Math.abs(a.d)).slice(0, 4)
        .map((x) => `${x.l} ${x.d > 0 ? "▲" : "▼"} ${fmt(Math.abs(x.d))}`);
      for (const l of before.keys()) if (!labels.includes(l) && changes.length < 4) changes.push(`${l} gone`);
    }
    option = {
      color: colors,
      tooltip: { trigger: "item", valueFormatter: fmt },
      legend: legend ? { bottom: 0, left: "center", type: "scroll", textStyle: { color: ink } } : undefined,
      series: [{
        type: "pie", radius: ["38%", "62%"], top: -10, bottom: legend ? 24 : 0, itemStyle: { borderColor: "#fff", borderWidth: 2 },
        // Whole percents and short lines keep labels inside narrow tiles.
        label: { formatter: style.showValues ? (p: { value: number; percent: number }) => `${fmt(p.value)} (${Math.round(p.percent)}%)`
                                             : (p: { percent: number }) => `${Math.round(p.percent)}%`, fontSize: 11, color: ink },
        labelLine: { length: 6, length2: 6 },
        labelLayout: { hideOverlap: true },
        data: labels.map((name, i) => ({ name, value: values(ys[0])[i] })),
      }],
    };
  } else {
    const horizontal = chart.type === "bar" && !!style.horizontal;
    // A few categories: show every name, wrapped; many: hide the ones that would overlap.
    // Horizontal bars: long names are cut at 160 px instead of pushing the bars aside.
    const few = labels.length <= 8;
    const axisLabel = horizontal ? { ...AXIS.axisLabel, width: 160, overflow: "truncate" }
      : few ? { ...AXIS.axisLabel, interval: 0, width: 80, overflow: "break", lineHeight: 13 }
      : { ...AXIS.axisLabel, hideOverlap: true };
    const category = { type: "category", data: labels, ...AXIS, axisLabel, inverse: horizontal }; // horizontal: first row on top
    const value = { type: "value", scale: !!fitAxis, axisLabel: { color: ink, formatter: fmt, hideOverlap: true },
                    splitLine: { lineStyle: { color: gridLine } } };
    const compared = ys.map((y) => [y, thenOf(y)] as const).filter(([, m]) => m);
    const showLegend = legend && (ys.length > 1 || compared.length > 0);
    option = {
      color: colors,
      textStyle: { fontFamily: "Inter, system-ui, sans-serif" },
      tooltip: { trigger: "axis", valueFormatter: fmt },
      legend: showLegend ? { top: 0, left: 0, right: 0, icon: "roundRect", type: "scroll", textStyle: { color: ink } } : undefined,  // one row, scrolls
      grid: { left: 8, right: style.showValues && horizontal ? 48 : 12, top: showLegend ? 36 : style.showValues ? 22 : 12,
              bottom: 8, containLabel: true },
      xAxis: horizontal ? value : category,
      yAxis: horizontal ? category : value,
      series: ys.map((y) => ({
        name: columnLabel(y),
        type: chart.type === "bar" ? "bar" : "line",
        data: values(y),
        smooth: chart.type !== "bar",
        stack: style.stacked && ys.length > 1 ? "total" : undefined,
        areaStyle: chart.type === "area" ? { opacity: style.stacked ? 0.5 : 0.18 } : undefined,
        barMaxWidth: 32,
        itemStyle: chart.type === "bar" ? { borderRadius: style.stacked ? 0 : horizontal ? [0, 4, 4, 0] : [4, 4, 0, 0] } : undefined,
        label: label(horizontal ? "right" : style.stacked ? "inside" : "top"),
      })).concat(compared.map(([y, then]) => ({
        // Same colour as the value it shadows, faded.
        color: colors[ys.indexOf(y) % colors.length],
        // The earlier refresh, beside each bar or as a dashed line.
        name: `${columnLabel(y)} (${compare!.label})`,
        type: chart.type === "bar" ? "bar" : "line",
        data: labels.map((l) => then!.get(l) ?? null),
        smooth: chart.type !== "bar",
        barMaxWidth: 32,
        itemStyle: chart.type === "bar" ? { opacity: 0.35, borderRadius: horizontal ? [0, 4, 4, 0] : [4, 4, 0, 0] } : { opacity: 0.6 },
        lineStyle: { type: "dashed", width: 1.5 },
        symbol: "none",
      })) as never[]),
    };
  }

  const alt = `${chart.type} chart of ${ys.map(columnLabel).join(", ")} by ${columnLabel(chart.x)}`;
  return (
    <>
      <div role="img" aria-label={alt}>
        <ReactEChartsCore echarts={echarts} option={option} notMerge style={{ height, width: "100%" }} />
      </div>
      {compare && chart.type === "pie" && (
        <p className="chart-changes small muted">Since {compare.label}: {changes.length ? changes.join(" · ") : "no change"}</p>
      )}
    </>
  );
}
