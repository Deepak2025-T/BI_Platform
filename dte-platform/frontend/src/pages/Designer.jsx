import { useEffect, useRef, useState } from 'react'
import { useLocation, useNavigate, useParams } from 'react-router-dom'
import GridLayout, { WidthProvider } from 'react-grid-layout'
import { api } from '../api.js'
import Widget from '../components/Widget.jsx'
import { CHART_TYPES, DEFAULT_PALETTE, prettify } from '../charts/buildOption.js'

const Grid = WidthProvider(GridLayout)
const SIZE = { kpi: { w: 3, h: 2 }, table: { w: 6, h: 4 } }
const newId = () => 'w' + Math.random().toString(36).slice(2, 8)

export default function Designer() {
  const { id } = useParams()
  const { state } = useLocation()
  const nav = useNavigate()
  const [report, setReport] = useState(null)
  const [sel, setSel] = useState(null)
  const [busy, setBusy] = useState('')
  const [msg, setMsg] = useState('')
  const dragType = useRef('column')
  const savedId = useRef(null)

  useEffect(() => {
    if (id && String(savedId.current) === id) return  // just saved here — keep in-memory state
    if (id) api.get(`/api/reports/${id}`).then((r) => setReport({ ...r.spec, id: r.id, title: r.title, connection_id: r.connection_id, template_id: r.template_id, prompt: r.prompt, published: r.published }))
    else if (state?.spec) setReport(state.spec)
    else setReport({ title: 'Untitled report', widgets: [], connection_id: state?.connection_id })
  }, [id])

  if (!report) return <div className="page">Loading…</div>
  const widgets = report.widgets || []
  const selected = widgets.find((w) => w.id === sel)

  const patch = (wid, fn) => setReport((r) => ({ ...r, widgets: r.widgets.map((w) => (w.id === wid ? { ...w, ...fn(w) } : w)) }))
  const patchStyle = (wid, s) => patch(wid, (w) => ({ style: { ...(w.style || {}), ...s } }))
  const patchChart = (wid, c) => patch(wid, (w) => ({ chart: { ...(w.chart || {}), ...c } }))

  const onLayout = (layout) => setReport((r) => ({
    ...r, widgets: r.widgets.map((w) => { const l = layout.find((x) => x.i === w.id); return l ? { ...w, layout: { x: l.x, y: l.y, w: l.w, h: l.h } } : w }),
  }))

  const onDrop = (_layout, item) => {
    const type = dragType.current
    const w = { id: newId(), title: `New ${prettify(type)}`, chart: { type }, rows: [], columns: [], layout: { x: item.x, y: item.y, ...(SIZE[type] || { w: 6, h: 4 }) },
      style: { palette: report.theme?.palette || DEFAULT_PALETTE, numberFormat: { style: 'number', decimals: 0 }, showLegend: true }, question: '', sql: '' }
    setReport((r) => ({ ...r, widgets: [...r.widgets, w] }))
    setSel(w.id)
  }

  async function ask(w) {
    if (!report.connection_id) return setMsg('Pick a connection in Report Builder first')
    setBusy('Asking AI…')
    try {
      const r = await api.post('/api/query', { connection_id: report.connection_id, question: w.question, chart: w.chart?.type })
      patch(w.id, () => ({ sql: r.sql, rows: r.rows, columns: r.columns, kpis: r.kpis, roles: r.roles, chart: r.chart, error: r.error }))
    } catch (e) { patch(w.id, () => ({ error: e.message })) }
    setBusy('')
  }

  async function runSql(w) {
    setBusy('Running SQL…')
    try {
      const r = await api.post('/api/query/sql', { connection_id: report.connection_id, sql: w.sql, chart: w.chart })
      patch(w.id, () => ({ sql: r.sql, rows: r.rows, columns: r.columns, kpis: r.kpis, roles: r.roles, chart: { ...w.chart, ...r.chart, type: w.chart.type }, error: null }))
    } catch (e) { patch(w.id, () => ({ error: e.message })) }
    setBusy('')
  }

  async function save(publish = false) {
    setBusy('Saving…')
    const body = { title: report.title, prompt: report.prompt, connection_id: report.connection_id, template_id: report.template_id, spec: report }
    try {
      const r = report.id ? await api.put(`/api/reports/${report.id}`, body) : await api.post('/api/reports', body)
      setReport((x) => ({ ...x, id: r.id }))
      if (publish) {
        const p = await api.post(`/api/reports/${r.id}/publish`)
        setMsg(`Published · ${p.examples_saved} verified queries added to RAG memory`)
        setReport((x) => ({ ...x, published: true }))
      } else setMsg('Saved')
      if (!id) { savedId.current = r.id; nav(`/designer/${r.id}`, { replace: true }) }
    } catch (e) { setMsg(e.message) }
    setBusy('')
  }

  return (
    <div className="designer">
      <aside className="palette">
        <h4>Visualizations</h4>
        <p className="hint">Drag onto the canvas</p>
        {CHART_TYPES.map((c) => (
          <div key={c.type} className="palette-item droppable-element" draggable unselectable="on"
            onDragStart={(e) => { dragType.current = c.type; e.dataTransfer.setData('text/plain', '') }}>
            <span className="pi-icon">{c.icon}</span>{c.label}
          </div>
        ))}
      </aside>

      <main className="canvas">
        <div className="toolbar">
          <input className="title-input" value={report.title} onChange={(e) => setReport({ ...report, title: e.target.value })} />
          <span className="spacer" />
          {busy && <span className="busy">{busy}</span>}
          {msg && <span className="msg" onClick={() => setMsg('')}>{msg}</span>}
          <button onClick={() => save(false)}>Save</button>
          <button className="primary" onClick={() => save(true)}>Publish</button>
          {report.id && <button onClick={() => nav(`/view/${report.id}`)}>View</button>}
        </div>
        {report.prompt && <div className="prompt-echo">“{report.prompt}”</div>}
        <Grid className="layout" cols={12} rowHeight={64} margin={[12, 12]} draggableHandle=".drag-handle"
          isDroppable droppingItem={{ i: '__drop__', w: 4, h: 3 }} onDrop={onDrop} onLayoutChange={onLayout}
          layout={widgets.map((w) => ({ i: w.id, ...w.layout, minW: 2, minH: 2 }))}>
          {widgets.map((w) => (
            <div key={w.id}>
              <Widget widget={w} editable selected={w.id === sel} onSelect={setSel}
                onRemove={(wid) => setReport((r) => ({ ...r, widgets: r.widgets.filter((x) => x.id !== wid) }))} />
            </div>
          ))}
        </Grid>
        {!widgets.length && <div className="empty big">Drag a visualization here, or generate a report from a prompt in Report Builder.</div>}
      </main>

      <aside className="props">
        {!selected ? <p className="hint">Select a widget to customize it.</p> : (
          <Props w={selected} patch={patch} patchStyle={patchStyle} patchChart={patchChart} ask={ask} runSql={runSql} />
        )}
      </aside>
    </div>
  )
}

function Section({ title, children, open = true }) {
  return <details className="prop-section" open={open}><summary>{title}</summary>{children}</details>
}

function Props({ w, patch, patchStyle, patchChart, ask, runSql }) {
  const cols = w.columns || []
  const style = w.style || {}
  const nf = style.numberFormat || {}
  const palette = style.palette || DEFAULT_PALETTE
  const isChart = !['kpi', 'table'].includes(w.chart?.type)
  const seriesNames = w.chart?.series ? [...new Set((w.rows || []).map((r) => String(r[w.chart.series])))] : (w.chart?.y || [])
  return (
    <div>
      <Section title="General">
        <label>Title<input value={w.title} onChange={(e) => patch(w.id, () => ({ title: e.target.value }))} /></label>
        <label>Chart type
          <select value={w.chart?.type} onChange={(e) => patchChart(w.id, { type: e.target.value })}>
            {CHART_TYPES.map((c) => <option key={c.type} value={c.type}>{c.label}</option>)}
          </select>
        </label>
      </Section>

      <Section title="Data source">
        <label>Ask in plain English
          <textarea rows={3} value={w.question || ''} onChange={(e) => patch(w.id, () => ({ question: e.target.value }))} placeholder="e.g. monthly revenue for 2026" />
        </label>
        <button className="primary small" disabled={!w.question} onClick={() => ask(w)}>Ask AI</button>
        <label>SQL (editable)
          <textarea className="mono" rows={5} value={w.sql || ''} onChange={(e) => patch(w.id, () => ({ sql: e.target.value }))} />
        </label>
        <button className="small" disabled={!w.sql} onClick={() => runSql(w)}>Run SQL</button>
      </Section>

      {cols.length > 0 && (
        <Section title="Fields">
          <label>Category / X axis
            <select value={w.chart?.x || ''} onChange={(e) => patchChart(w.id, { x: e.target.value || null })}>
              <option value="">—</option>{cols.map((c) => <option key={c}>{c}</option>)}
            </select>
          </label>
          <div className="label">Measures</div>
          <div className="checks">
            {cols.map((c) => (
              <label key={c} className="check"><input type="checkbox" checked={(w.chart?.y || []).includes(c)}
                onChange={(e) => { const y = new Set(w.chart?.y || []); e.target.checked ? y.add(c) : y.delete(c); patchChart(w.id, { y: cols.filter((x) => y.has(x)) }) }} />{c}</label>
            ))}
          </div>
          <label>Split series by
            <select value={w.chart?.series || ''} onChange={(e) => patchChart(w.id, { series: e.target.value || null })}>
              <option value="">— none —</option>{cols.map((c) => <option key={c}>{c}</option>)}
            </select>
          </label>
        </Section>
      )}

      <Section title="Number format">
        <div className="row2">
          <label>Format
            <select value={nf.style || 'number'} onChange={(e) => patchStyle(w.id, { numberFormat: { ...nf, style: e.target.value } })}>
              <option value="number">Number</option><option value="currency">Currency</option><option value="percent">Percent</option><option value="compact">Compact (1.2L / 3.4M)</option>
            </select>
          </label>
          <label>Decimals<input type="number" min={0} max={6} value={nf.decimals ?? 0} onChange={(e) => patchStyle(w.id, { numberFormat: { ...nf, decimals: +e.target.value } })} /></label>
        </div>
        <div className="row3">
          {nf.style === 'currency' && <label>Currency<input value={nf.currency || 'INR'} onChange={(e) => patchStyle(w.id, { numberFormat: { ...nf, currency: e.target.value.toUpperCase().slice(0, 3) } })} /></label>}
          <label>Prefix<input value={nf.prefix || ''} onChange={(e) => patchStyle(w.id, { numberFormat: { ...nf, prefix: e.target.value } })} /></label>
          <label>Suffix<input value={nf.suffix || ''} onChange={(e) => patchStyle(w.id, { numberFormat: { ...nf, suffix: e.target.value } })} /></label>
        </div>
      </Section>

      {isChart && (
        <Section title="Colors">
          <div className="label">Palette (series order)</div>
          <div className="swatches">
            {palette.map((c, i) => (
              <input key={i} type="color" value={c} onChange={(e) => { const p = [...palette]; p[i] = e.target.value; patchStyle(w.id, { palette: p }) }} />
            ))}
            <button className="small" onClick={() => patchStyle(w.id, { palette: DEFAULT_PALETTE, seriesColors: {} })}>Reset</button>
          </div>
          {seriesNames.length > 0 && <div className="label">Per-series override</div>}
          {seriesNames.slice(0, 12).map((s) => (
            <label key={s} className="inline">
              <input type="color" value={style.seriesColors?.[s] || style.seriesColors?.[prettify(s)] || '#888888'}
                onChange={(e) => patchStyle(w.id, { seriesColors: { ...(style.seriesColors || {}), [w.chart?.series ? s : prettify(s)]: e.target.value } })} />
              {w.chart?.series ? s : prettify(s)}
            </label>
          ))}
        </Section>
      )}

      {isChart && (
        <Section title="Display" open={false}>
          <label className="check"><input type="checkbox" checked={style.showLegend !== false} onChange={(e) => patchStyle(w.id, { showLegend: e.target.checked })} />Legend</label>
          <label className="check"><input type="checkbox" checked={!!style.showLabels} onChange={(e) => patchStyle(w.id, { showLabels: e.target.checked })} />Data labels</label>
          <label className="check"><input type="checkbox" checked={!!style.smooth} onChange={(e) => patchStyle(w.id, { smooth: e.target.checked })} />Smooth lines</label>
          <label className="check"><input type="checkbox" checked={!!style.stacked} onChange={(e) => patchStyle(w.id, { stacked: e.target.checked })} />Stack series</label>
          <label className="check"><input type="checkbox" checked={style.showInsights !== false} onChange={(e) => patchStyle(w.id, { showInsights: e.target.checked })} />AI insights</label>
          <label>Value-axis title<input value={style.axisTitle || ''} onChange={(e) => patchStyle(w.id, { axisTitle: e.target.value })} /></label>
        </Section>
      )}
    </div>
  )
}
