import ReactEChartsCore from "echarts-for-react/lib/core";
import { BarChart } from "echarts/charts";
import { GridComponent, LegendComponent, TooltipComponent } from "echarts/components";
import * as echarts from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";
import type { ChartKind, NumberFormat, PaletteId, QueryResult } from "../api/types";
import { money } from "../lib/format";
import { PALETTES, regionColor } from "../lib/report";
import DataTable from "./DataTable";

// Register only what we use, so the bundle stays small.
echarts.use([BarChart, GridComponent, LegendComponent, TooltipComponent, CanvasRenderer]);

interface Props {
  result: QueryResult;
  kind: ChartKind;
  palette: PaletteId;
  fmt: NumberFormat;
  showValues: boolean;
  /** Chart height in pixels; the table scrolls inside it. */
  height?: number;
}

export default function RevenueChart({ result, kind, palette, fmt, showValues, height = 320 }: Props) {
  if (kind === "table") return <div style={{ maxHeight: height, overflow: "auto" }}><DataTable result={result} fmt={fmt} /></div>;

  const colors = PALETTES[palette].colors;
  const stacked = kind === "stacked";
  const option = {
    textStyle: { fontFamily: "Inter, system-ui, sans-serif" },
    tooltip: { trigger: "axis", valueFormatter: (v: number) => money(v, fmt) },
    legend: { top: 0, left: 0, icon: "roundRect", textStyle: { color: "#1A2332" } },
    grid: { left: 8, right: 8, top: 40, bottom: 8, containLabel: true },
    xAxis: { type: "category", data: result.months, axisTick: { show: false }, axisLine: { lineStyle: { color: "#CFDCE8" } }, axisLabel: { color: "#4A5568" } },
    yAxis: { type: "value", axisLabel: { color: "#4A5568", formatter: (v: number) => money(v, "short") }, splitLine: { lineStyle: { color: "#EDF2F7" } } },
    series: result.regions.map((reg) => ({
      name: reg,
      type: "bar",
      stack: stacked ? "total" : undefined,
      barMaxWidth: stacked ? 56 : 28,
      // Each region keeps the same colour whatever the filter
      itemStyle: { color: regionColor(reg, colors), borderRadius: stacked ? 0 : [4, 4, 0, 0] },
      label: {
        show: showValues,
        position: stacked ? "inside" : "top",
        fontSize: 11,
        color: stacked ? "#FFFFFF" : "#1A2332",
        formatter: (p: { value: number }) => money(p.value, "short"),
      },
      data: result.series[reg],
    })),
  };

  const alt = `${result.measure_label} by region and month, ${result.period_short}.`;
  return (
    <div role="img" aria-label={alt}>
      <ReactEChartsCore echarts={echarts} option={option} notMerge style={{ height, width: "100%" }} />
    </div>
  );
}
