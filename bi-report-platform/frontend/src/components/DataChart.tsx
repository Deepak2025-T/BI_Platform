import ReactEChartsCore from "echarts-for-react/lib/core";
import { BarChart, HeatmapChart, LineChart, PieChart } from "echarts/charts";
import { GridComponent, LegendComponent, TooltipComponent, VisualMapComponent } from "echarts/components";
import * as echarts from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";
import type { Cell, ChartSpec, WidgetStyle } from "../api/types";
import { isDark } from "../lib/cardColors";
import { meaningColor, normalizeColor, ruleColor, worthColoringByMeaning } from "../lib/colors";
import { columnLabel, formatValue } from "../lib/format";
import { delta, tone } from "../lib/history";
import ResultTable from "./ResultTable";

echarts.use([BarChart, HeatmapChart, LineChart, PieChart, GridComponent, LegendComponent, TooltipComponent,
             VisualMapComponent, CanvasRenderer]);

/** Figures are set in a monospaced face so columns of them line up, matching the app's CSS. */
export const NUMERALS = "'IBM Plex Mono', ui-monospace, 'SFMono-Regular', Menlo, Consolas, monospace";

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
  /** Called with the category that was clicked, when the chart can be drilled into. */
  onPoint?: (name: string) => void;
  /** Tables: given when the person may set column widths, take a column off, or number the rows. */
  onColumns?: (patch: { widths?: Record<string, number>; hiddenColumns?: string[]; rowNumbers?: boolean;
                        wrapText?: boolean }) => void;
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
export default function DataChart({ columns, rows, chart, style = {}, height = 280, tableHeight, truncated, compare, spark, fitAxis, onPoint, onColumns }: Props) {
  const xi = columns.indexOf(chart.x);
  const ys = chart.y.filter((c) => columns.includes(c));
  const fmt = (v: number) => formatValue(v, style);
  // A colour typed as rgb() or a name is stored as it was typed; the chart library wants hex.
  const main = normalizeColor(style.color);
  // The chart's palette, else the one the dashboard set, else the built-in list. A chart colour
  // still wins over the palette's first entry: it is the more specific choice of the two.
  const base = (style.palette?.length ? style.palette.map(normalizeColor).filter(Boolean) : null) ?? CHART_COLORS;
  const colors = main ? [main, ...base.filter((c) => c.toUpperCase() !== main.toUpperCase())] : base;
  // Text and lines that read on the card's background.
  //
  // The chart's own writing - legend, axis labels, slice labels - follows the CARD's colour and
  // nothing else, so that colouring a tile's header band leaves the chart exactly as it was.
  // `legendColor` overrides it outright for anyone who wants the two chosen separately.
  const dark = isDark(style.cardBg);
  const chosen = normalizeColor(style.legendColor);
  const ink = chosen || (dark ? "#D6E2EE" : "#4A5568");
  const strong = chosen || (dark ? "#FFFFFF" : "#1A2332");
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
        <span className="kpi-value" style={main ? { color: main } : undefined}>
          {typeof value === "number" ? fmt(value) : value ?? "–"}
        </span>
        {col && columnLabel(col) !== "Count" && <span className="kpi-label">{columnLabel(col)}</span>}
        {change && (
          <span className={`kpi-delta ${tone(change.dir, style.goodWhen)}`} title={`${fmt(then as number)} on ${compare!.label}`}>
            {change.text} <span className="muted">since {compare!.label}</span>
          </span>
        )}
        {spark && spark.length > 1 && <Sparkline values={spark} color={main || CHART_COLORS[0]} />}
      </div>
    );
  }

  // Shapes the visual builder can save but this renderer doesn't draw yet. They fall back to the
  // rows rather than being drawn as something else, which is what the "else" below would do.
  const notDrawnYet = chart.type === "combo" || chart.type === "scatter" || chart.type === "gauge";

  // Sort by the first value column when asked (bars, pies and tables read better ranked).
  const sortIndex = ys.length ? columns.indexOf(ys[0]) : -1;
  const sorted = style.sort && style.sort !== "none" && sortIndex >= 0
    ? [...rows].sort((a, b) => (Number(a[sortIndex]) - Number(b[sortIndex])) * (style.sort === "desc" ? -1 : 1))
    : rows;

  // A heatmap needs a second field for its columns; without one there is no grid to colour in.
  const gridIndex = chart.type === "heatmap" ? columns.indexOf(chart.legend ?? "") : -1;

  // A chart needs a category column and at least one number; otherwise show the rows.
  // A matrix is a table until pivoting is built.
  if (chart.type === "table" || chart.type === "matrix" || notDrawnYet || xi < 0 || ys.length === 0
      || (chart.type === "heatmap" && gridIndex < 0)) {
    const table = (
      <ResultTable columns={columns} rows={sorted} truncated={truncated} limit={50}
        widths={style.columnWidths} hiddenColumns={style.hiddenColumns}
        rowNumbers={style.rowNumbers !== false} wrapText={!!style.wrapText} onColumns={onColumns} />
    );
    return tableHeight ? <div className="table-scroll" style={{ maxHeight: tableHeight }}>{table}</div> : table;
  }

  const labels = sorted.map((r) => String(r[xi] ?? ""));

  // One series, many categories: give each category its own colour, so a chart of risk ratings
  // reads the way it would on paper instead of as one block of blue. Several series keep the
  // palette per series, because there the colour already tells the series apart.
  const colorMode = style.colorMode ?? "auto";
  const pie = chart.type === "pie" || chart.type === "donut";
  const useMeanings = colorMode === "auto" && worthColoringByMeaning(labels);
  const perCategory = ys.length === 1 && colorMode !== "single"
    && (colorMode === "palette" || useMeanings || !!style.colorRules?.length);
  /** The colour for one category: the person's rules, then what the name means, then the palette. */
  const categoryColor = (label: string, i: number) =>
    ruleColor(label, style.colorRules) || (useMeanings ? meaningColor(label) : "")
    || (colorMode === "palette" || pie ? colors[i % colors.length] : colors[0]);
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
  const label = (position: string, as: (v: number) => string = fmt) =>
    ({ show: !!style.showValues, position, fontSize: 11, color: strong,
       formatter: (p: { value: number }) => as(p.value) });

  // Clicking a bar, slice or cell asks for that category; the caller decides what to do with it.
  const clicks = onPoint ? { click: (p: { name?: string }) => p?.name && onPoint(String(p.name)) } : undefined;

  let option;
  let changes: string[] = [];
  if (chart.type === "heatmap") {
    // One cell per pair of values: rows down the side, columns across the top, colour for the
    // number. Rows arrive one per pair, so they are laid out onto the grid by name.
    const down = [...new Set(labels)];
    const across = [...new Set(sorted.map((r) => String(r[gridIndex] ?? "")))];
    const vi = columns.indexOf(ys[0]);
    // The query only returns the pairs that have something in them, so a grid drawn straight from
    // the rows has holes in it - and a hole reads as "no data here" when what it means is "none".
    // Every pair is laid out, and one that never came back counts as zero.
    const counted = new Map<string, number>();
    for (const r of sorted) {
      const value = typeof r[vi] === "number" ? r[vi] as number : Number(r[vi]);
      if (Number.isFinite(value)) counted.set(`${String(r[gridIndex] ?? "")}\u0000${String(r[xi] ?? "")}`, value);
    }
    const cells = across.flatMap((col, ax) =>
      down.map((row, dy) => [ax, dy, counted.get(`${col}\u0000${row}`) ?? 0]));
    const numbers = cells.map((c) => c[2] as number);
    const low = Math.min(0, ...numbers), high = Math.max(...numbers, 1);
    const main = colors[0];
    // A count sitting on a deep cell has to be read off it, so past the middle of the scale the
    // figure turns white. It is set per cell rather than on the series, because the series' own
    // colour is only decided by the visual map after that.
    const shaded = cells.map((c) => ({
      value: c, label: { color: (c[2] as number) - low > (high - low) * 0.55 ? "#FFFFFF" : strong },
    }));
    return (
      <div role="img" aria-label={`Heatmap of ${columnLabel(ys[0])} by ${columnLabel(chart.x)} and ${columnLabel(chart.legend!)}`}>
        <ReactEChartsCore echarts={echarts} notMerge style={{ height, width: "100%" }}
          onEvents={onPoint ? { click: (p: { value: [number, number, number] }) => onPoint(down[p.value[1]]) } : undefined}
          option={{
          tooltip: {
            // The axes hold positions, so the tooltip puts the names back.
            formatter: (p: { value: [number, number, number] }) =>
              `${across[p.value[0]]} · ${down[p.value[1]]}<br/><b>${fmt(p.value[2])}</b>`,
          },
          grid: { left: 8, right: 12, top: 12, bottom: legend ? 48 : 12, containLabel: true },
          xAxis: { type: "category", data: across, ...AXIS, splitArea: { show: true },
                   axisLabel: { ...AXIS.axisLabel, hideOverlap: true } },
          yAxis: { type: "category", data: down, ...AXIS, splitArea: { show: true },
                   axisLabel: { ...AXIS.axisLabel, width: 150, overflow: "truncate" } },
          visualMap: {
            // The scale is what colours the cells; the bar showing it is only drawn when the chart
            // is set to show a legend, because the counts are written in the cells anyway.
            show: legend,
            min: low, max: high, calculable: true, orient: "horizontal", left: "center", bottom: 4,
            textStyle: { color: ink }, formatter: fmt,
            // Pale to the card's own colour, so a heatmap matches the rest of the dashboard.
            inRange: { color: [dark ? "#1B2A38" : "#F2F7FB", main] },
          },
          series: [{
            type: "heatmap", data: shaded,
            label: {
              show: !!style.showValues, fontSize: 11, fontWeight: 600,
              formatter: (p: { value: [number, number, number] }) => fmt(p.value[2]),
            },
            // Rounded cells with the card showing between them, rather than a ruled table.
            itemStyle: { borderColor: "transparent", borderWidth: 3, borderRadius: 6 },
            emphasis: { itemStyle: { borderColor: strong, borderWidth: 1.5, borderRadius: 6 } },
          }],
        }} />
      </div>
    );
  }
  if (chart.type === "pie" || chart.type === "donut") {
    const before = thenOf(ys[0]);
    if (before) {
      const now = values(ys[0]);
      changes = labels.map((l, i) => ({ l, d: now[i] - (before.get(l) ?? 0) })).filter((x) => x.d !== 0)
        .sort((a, b) => Math.abs(b.d) - Math.abs(a.d)).slice(0, 4)
        .map((x) => `${x.l} ${x.d > 0 ? "▲" : "▼"} ${fmt(Math.abs(x.d))}`);
      for (const l of before.keys()) if (!labels.includes(l) && changes.length < 4) changes.push(`${l} gone`);
    }
    // A ring reads its slices down the side rather than off the chart: the name, the figure and
    // its share, one per line, with the total in the hole. It carries more in a narrow tile than
    // labels on leader lines, which overlap as soon as a slice is thin.
    const ringLegend = !!style.ringLegend && legend;
    const slices = values(ys[0]);
    const whole = slices.reduce((a, b) => a + (Number.isFinite(b) ? b : 0), 0);
    option = {
      color: colors,
      tooltip: { trigger: "item", valueFormatter: fmt },
      legend: !legend ? undefined
        : ringLegend
          ? {
            orient: "vertical", right: 0, top: "middle", type: "scroll", itemWidth: 8, itemHeight: 8,
            icon: "circle", itemGap: 7, textStyle: { color: ink, fontSize: 12, rich: {} },
            formatter: (name: string) => {
              const v = slices[labels.indexOf(name)] ?? 0;
              return `${name}  ${fmt(v)}  ${whole ? Math.round((v / whole) * 100) : 0}%`;
            },
          }
          : { bottom: 0, left: "center", type: "scroll", textStyle: { color: ink } },
      // The total sits in the hole, under the word for what is being counted.
      ...(ringLegend ? {
        title: {
          text: fmt(whole), subtext: (columnLabel(chart.x || "") || "total").toUpperCase(),
          left: "24%", top: "center", textAlign: "center",
          textStyle: { fontSize: 19, fontWeight: 600, color: strong, fontFamily: NUMERALS },
          subtextStyle: { fontSize: 9, color: ink, fontWeight: 600 }, itemGap: 4,
        },
      } : {}),
      series: [{
        // A donut has a wider hole than the default pie.
        type: "pie", radius: chart.type === "donut" ? ["55%", "76%"] : ["38%", "62%"],
        ...(ringLegend ? { center: ["24%", "50%"] } : {}),
        top: -10, bottom: legend && !ringLegend ? 24 : 0, itemStyle: { borderColor: "#fff", borderWidth: 2 },
        // Whole percents and short lines keep labels inside narrow tiles. A ring that lists its
        // slices beside it needs no labels on the slices themselves.
        label: ringLegend ? { show: false }
          : { formatter: style.showValues ? (p: { value: number; percent: number }) => `${fmt(p.value)} (${Math.round(p.percent)}%)`
                                          : (p: { percent: number }) => `${Math.round(p.percent)}%`, fontSize: 11, color: ink },
        labelLine: ringLegend ? { show: false } : { length: 6, length2: 6 },
        labelLayout: { hideOverlap: true },
        data: labels.map((name, i) => ({
          name, value: slices[i],
          ...(perCategory ? { itemStyle: { color: categoryColor(name, i) } } : {}),
        })),
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
    // The builder saves stackMode; charts from before it only have `stacked`.
    const stackMode = style.stackMode ?? (style.stacked ? "stacked" : "none");
    const stacked = stackMode !== "none" && ys.length > 1;
    // 100% stacked: ECharts stacks the numbers it is given, so each bar is turned into a share of
    // its own total first. The axis, tooltips and labels then read as percentages.
    const full = stacked && stackMode === "full";
    const totals = full ? labels.map((_, i) => ys.reduce((sum, y) => sum + Math.abs(values(y)[i] || 0), 0)) : null;
    const seriesData = (y: string) =>
      totals ? values(y).map((v, i) => (totals[i] ? v / totals[i] : 0)) : values(y);
    const valueFmt = full ? (v: number) => `${Math.round(v * 100)}%` : fmt;
    const value = { type: "value", scale: !full && !!fitAxis, max: full ? 1 : undefined,
                    axisLabel: { color: ink, formatter: valueFmt, hideOverlap: true },
                    splitLine: { lineStyle: { color: gridLine } } };
    // An earlier refresh can't be shown beside shares: its numbers are on a different scale.
    const compared = full ? [] : ys.map((y) => [y, thenOf(y)] as const).filter(([, m]) => m);
    const showLegend = legend && (ys.length > 1 || compared.length > 0);
    option = {
      color: colors,
      textStyle: { fontFamily: "Inter, system-ui, sans-serif" },
      tooltip: { trigger: "axis", valueFormatter: valueFmt },
      legend: showLegend ? { top: 0, left: 0, right: 0, icon: "roundRect", type: "scroll", textStyle: { color: ink } } : undefined,  // one row, scrolls
      grid: { left: 8, right: style.showValues && horizontal ? 48 : 12, top: showLegend ? 36 : style.showValues ? 22 : 12,
              bottom: 8, containLabel: true },
      xAxis: horizontal ? value : category,
      yAxis: horizontal ? category : value,
      series: ys.map((y) => ({
        name: columnLabel(y),
        type: chart.type === "bar" ? "bar" : "line",
        // Bars can differ per category; a line is one shape, so it keeps one colour.
        data: perCategory && chart.type === "bar"
          ? seriesData(y).map((v, i) => ({ value: v, itemStyle: { color: categoryColor(labels[i], i) } }))
          : seriesData(y),
        smooth: chart.type !== "bar",
        stack: stacked ? "total" : undefined,
        areaStyle: chart.type === "area" ? { opacity: stacked ? 0.5 : 0.18 } : undefined,
        barMaxWidth: 32,
        itemStyle: chart.type === "bar" ? { borderRadius: stacked ? 0 : horizontal ? [0, 4, 4, 0] : [4, 4, 0, 0] } : undefined,
        label: label(horizontal ? "right" : stacked ? "inside" : "top", valueFmt),
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
        <ReactEChartsCore echarts={echarts} option={option} notMerge style={{ height, width: "100%" }} onEvents={clicks} />
      </div>
      {compare && (chart.type === "pie" || chart.type === "donut") && (
        <p className="chart-changes small muted">Since {compare.label}: {changes.length ? changes.join(" · ") : "no change"}</p>
      )}
    </>
  );
}
