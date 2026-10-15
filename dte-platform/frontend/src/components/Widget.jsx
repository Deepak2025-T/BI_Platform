import { useMemo, useState } from 'react'
import Chart from '../charts/Chart.jsx'
import { buildOption, formatNumber, prettify } from '../charts/buildOption.js'

export function KpiTile({ widget }) {
  const nf = widget.style?.numberFormat || {}
  const k = widget.kpis?.[0]
  if (!k) return <div className="empty">No value</div>
  const up = k.change_pct > 0
  return (
    <div className="kpi">
      <div className="kpi-value">{formatNumber(k.value, nf)}</div>
      <div className="kpi-sub">
        {prettify(k.measure)}{k.period ? ` · ${k.period}` : ''}
        {k.change_pct !== undefined && k.change_pct !== null && (
          <span className={up ? 'delta up' : 'delta down'}>{up ? '▲' : '▼'} {Math.abs(k.change_pct).toFixed(1)}% vs prev.</span>
        )}
      </div>
    </div>
  )
}

export function DataTable({ widget, max = 500 }) {
  const nf = widget.style?.numberFormat || {}
  const measures = new Set(widget.roles?.measures || widget.chart?.y || [])
  const cols = widget.columns || Object.keys(widget.rows?.[0] || {})
  return (
    <div className="table-wrap">
      <table>
        <thead><tr>{cols.map((c) => <th key={c} className={measures.has(c) ? 'num' : ''}>{prettify(c)}</th>)}</tr></thead>
        <tbody>
          {(widget.rows || []).slice(0, max).map((r, i) => (
            <tr key={i}>{cols.map((c) => <td key={c} className={measures.has(c) ? 'num' : ''}>{measures.has(c) ? formatNumber(r[c], nf) : String(r[c] ?? '')}</td>)}</tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export default function Widget({ widget, selected, onSelect, onRemove, editable }) {
  const [showSql, setShowSql] = useState(false)
  const [showTable, setShowTable] = useState(false)
  const type = widget.chart?.type
  const option = useMemo(() => (['kpi', 'table'].includes(type) ? null : buildOption(widget)), [widget, type])
  return (
    <div className={`widget ${selected ? 'selected' : ''}`} onMouseDown={() => onSelect && onSelect(widget.id)}>
      <div className="widget-head drag-handle">
        <span className="widget-title">{widget.title}</span>
        <span className="widget-actions" onMouseDown={(e) => e.stopPropagation()}>
          {type !== 'table' && type !== 'kpi' && <button className="icon" title="Show data table" onClick={() => setShowTable(!showTable)}>☷</button>}
          {widget.sql && <button className="icon" title="Show SQL" onClick={() => setShowSql(!showSql)}>{'</>'}</button>}
          {editable && <button className="icon" title="Remove" onClick={() => onRemove(widget.id)}>✕</button>}
        </span>
      </div>
      <div className="widget-body">
        {widget.error ? <div className="error">⚠ {widget.error}</div>
          : showSql ? <pre className="sql">{widget.sql}</pre>
          : type === 'kpi' ? <KpiTile widget={widget} />
          : type === 'table' || showTable ? <DataTable widget={widget} />
          : !widget.rows?.length ? <div className="empty">No rows returned</div>
          : <Chart option={option} />}
      </div>
      {widget.insights?.length > 0 && widget.style?.showInsights !== false && type !== 'kpi' && (
        <ul className="insights">{widget.insights.map((s, i) => <li key={i}>{s}</li>)}</ul>
      )}
    </div>
  )
}
