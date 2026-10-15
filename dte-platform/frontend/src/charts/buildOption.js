// Turn a widget (chart spec + rows + style) into an ECharts option.
// Styling is fully driven by widget.style so the designer can change it live.

export const DEFAULT_PALETTE = ['#2a78d6', '#eb6834', '#1baf7a', '#eda100', '#e87ba4', '#008300', '#6250d6', '#e34948']
// Same eight hues stepped for the dark surface (validated separately)
const DARK_PALETTE = ['#3987e5', '#d95926', '#199e70', '#c98500', '#d55181', '#008300', '#9085e9', '#e66767']

export const CHART_TYPES = [
  { type: 'kpi', label: 'KPI tile', icon: '#' },
  { type: 'line', label: 'Line', icon: '⟋' },
  { type: 'area', label: 'Area', icon: '◭' },
  { type: 'column', label: 'Column', icon: '▮' },
  { type: 'bar', label: 'Bar', icon: '▬' },
  { type: 'stacked_column', label: 'Stacked column', icon: '▤' },
  { type: 'pie', label: 'Pie', icon: '◔' },
  { type: 'donut', label: 'Donut', icon: '◎' },
  { type: 'scatter', label: 'Scatter', icon: '⁘' },
  { type: 'table', label: 'Table', icon: '☷' },
]

export function formatNumber(v, nf = {}) {
  if (v === null || v === undefined || v === '' || isNaN(Number(v))) return v ?? '—'
  const n = Number(v)
  const d = nf.decimals ?? 0
  let s
  switch (nf.style) {
    case 'currency':
      s = new Intl.NumberFormat(nf.locale || 'en-IN', { style: 'currency', currency: nf.currency || 'INR', minimumFractionDigits: d, maximumFractionDigits: d }).format(n)
      break
    case 'percent':
      s = new Intl.NumberFormat(nf.locale || 'en-IN', { maximumFractionDigits: d, minimumFractionDigits: d }).format(n) + '%'
      break
    case 'compact':
      s = new Intl.NumberFormat(nf.locale || 'en-IN', { notation: 'compact', maximumFractionDigits: Math.max(d, 1) }).format(n)
      break
    default:
      s = new Intl.NumberFormat(nf.locale || 'en-IN', { maximumFractionDigits: d, minimumFractionDigits: d }).format(n)
  }
  return `${nf.prefix || ''}${s}${nf.suffix || ''}`
}

export const prettify = (c) => (c || '').replace(/_/g, ' ').replace(/\b\w/g, (m) => m.toUpperCase())

function fmtCategory(v) {
  if (typeof v === 'string' && /^\d{4}-\d{2}-01$/.test(v)) {
    const d = new Date(v + 'T00:00:00')
    return d.toLocaleString('en', { month: 'short', year: '2-digit' })
  }
  return v
}

function themeColors() {
  const dark = typeof window !== 'undefined' && document.documentElement.dataset.theme === 'dark'
  return dark
    ? { text: '#c3c2b7', muted: '#8a8980', grid: '#2e2e2c', surface: '#1a1a19' }
    : { text: '#52514e', muted: '#8a8980', grid: '#ebeae6', surface: '#ffffff' }
}

// Build series either one per measure, or pivoted by a series column.
function seriesData(widget) {
  const { chart = {}, rows = [] } = widget
  const x = chart.x
  const ys = chart.y || []
  if (chart.series && ys.length) {
    const cats = [...new Set(rows.map((r) => r[x]))]
    const groups = [...new Set(rows.map((r) => r[chart.series]))]
    const idx = Object.fromEntries(cats.map((c, i) => [c, i]))
    const series = groups.map((g) => {
      const data = new Array(cats.length).fill(null)
      rows.filter((r) => r[chart.series] === g).forEach((r) => { data[idx[r[x]]] = (data[idx[r[x]]] || 0) + Number(r[ys[0]] || 0) })
      return { name: String(g), data }
    })
    return { cats, series }
  }
  const cats = rows.map((r) => (x ? r[x] : prettify(ys[0] || 'value')))
  return { cats, series: ys.map((m) => ({ name: prettify(m), key: m, data: rows.map((r) => (r[m] === null ? null : Number(r[m]))) })) }
}

export function buildOption(widget) {
  const { chart = {}, rows = [], style = {} } = widget
  const t = themeColors()
  let palette = style.palette?.length ? style.palette : DEFAULT_PALETTE
  if (document.documentElement.dataset.theme === 'dark' && palette.join() === DEFAULT_PALETTE.join()) palette = DARK_PALETTE
  const nf = style.numberFormat || {}
  const overrides = style.seriesColors || {}
  const type = chart.type
  const base = {
    color: palette,
    textStyle: { fontFamily: 'Inter, system-ui, sans-serif', color: t.text },
    animationDuration: 300,
    grid: { left: 8, right: 16, top: style.showLegend !== false ? 36 : 16, bottom: 8, containLabel: true },
    tooltip: { confine: true, valueFormatter: (v) => formatNumber(v, nf), backgroundColor: t.surface, borderColor: t.grid, textStyle: { color: t.text } },
  }

  if (type === 'pie' || type === 'donut') {
    const m = chart.y?.[0]
    const data = rows.map((r) => ({ name: String(fmtCategory(r[chart.x])), value: Number(r[m] || 0) }))
    return {
      ...base,
      tooltip: { ...base.tooltip, trigger: 'item' },
      legend: style.showLegend !== false ? { type: 'scroll', bottom: 0, textStyle: { color: t.text }, icon: 'circle', itemWidth: 10 } : undefined,
      series: [{
        type: 'pie', radius: type === 'donut' ? ['48%', '72%'] : [0, '72%'], center: ['50%', '45%'],
        itemStyle: { borderColor: t.surface, borderWidth: 2, borderRadius: type === 'donut' ? 4 : 0 },
        label: { show: !!style.showLabels, color: t.text, formatter: (p) => `${p.name}\n${p.percent}%` },
        labelLine: { show: !!style.showLabels },
        data: data.map((d) => ({ ...d, itemStyle: overrides[d.name] ? { color: overrides[d.name] } : undefined })),
      }],
    }
  }

  if (type === 'scatter') {
    const [m] = chart.y || []
    return {
      ...base,
      tooltip: { ...base.tooltip, trigger: 'item' },
      xAxis: { type: 'value', name: prettify(chart.x), nameLocation: 'middle', nameGap: 28, axisLabel: { color: t.muted }, splitLine: { lineStyle: { color: t.grid } } },
      yAxis: { type: 'value', axisLabel: { color: t.muted, formatter: (v) => formatNumber(v, { ...nf, style: nf.style === 'currency' ? 'compact' : nf.style }) }, splitLine: { lineStyle: { color: t.grid } } },
      series: [{ type: 'scatter', symbolSize: 10, itemStyle: { borderColor: t.surface, borderWidth: 2 }, data: rows.map((r) => [Number(r[chart.x]), Number(r[m])]) }],
    }
  }

  const { cats, series } = seriesData(widget)
  const horizontal = type === 'bar'
  const isBar = ['column', 'bar', 'stacked_column'].includes(type)
  const stacked = type === 'stacked_column' || (style.stacked && isBar)
  const catAxis = { type: 'category', data: cats.map(fmtCategory), axisLine: { lineStyle: { color: t.grid } }, axisTick: { show: false }, axisLabel: { color: t.muted, hideOverlap: true }, inverse: horizontal }
  const valAxis = {
    type: 'value', name: style.axisTitle || '', nameTextStyle: { color: t.muted },
    axisLabel: { color: t.muted, formatter: (v) => formatNumber(v, { ...nf, style: nf.style === 'currency' || Math.abs(v) >= 1e5 ? 'compact' : nf.style, prefix: nf.style === 'currency' ? '' : nf.prefix }) },
    splitLine: { lineStyle: { color: t.grid } },
  }
  return {
    ...base,
    tooltip: { ...base.tooltip, trigger: 'axis', axisPointer: { type: isBar ? 'shadow' : 'line' } },
    legend: style.showLegend !== false && series.length > 1 ? { top: 0, type: 'scroll', textStyle: { color: t.text }, icon: 'roundRect', itemWidth: 12, itemHeight: 8 } : undefined,
    xAxis: horizontal ? valAxis : catAxis,
    yAxis: horizontal ? catAxis : valAxis,
    series: series.map((s, i) => {
      const color = overrides[s.name] || overrides[s.key]
      const common = {
        name: s.name, data: s.data,
        label: { show: !!style.showLabels, position: isBar ? (stacked ? 'inside' : horizontal ? 'right' : 'top') : 'top', color: t.text, formatter: (p) => formatNumber(p.value, { ...nf, style: 'compact' }) },
        itemStyle: color ? { color } : {},
      }
      if (isBar) {
        const last = !stacked || i === series.length - 1
        return { ...common, type: 'bar', stack: stacked ? 'total' : undefined, barMaxWidth: 36, barGap: '10%',
          itemStyle: { ...common.itemStyle, borderColor: t.surface, borderWidth: stacked ? 1 : 0,
            borderRadius: last ? (horizontal ? [0, 4, 4, 0] : [4, 4, 0, 0]) : 0 } }
      }
      return { ...common, type: 'line', smooth: style.smooth ?? false, showSymbol: cats.length <= 24, symbolSize: 8,
        lineStyle: { width: 2, ...(color ? { color } : {}) },
        areaStyle: type === 'area' ? { opacity: 0.18 } : undefined, stack: type === 'area' && style.stacked ? 'total' : undefined }
    }),
  }
}
