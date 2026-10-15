import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api.js'

const EXAMPLES = [
  'Finance overview for the last 12 months: revenue, expenses, profit and top customers',
  'Sales performance by region and product for FY 2025-26',
  'Receivables aging and overdue customers as of today',
  'Monthly expense breakdown by category with trend',
]

function TemplateThumb({ t }) {
  return (
    <div className="thumb">
      {t.slots.map((s) => (
        <div key={s.slot} className={`thumb-cell t-${s.type}`}
          style={{ gridColumn: `${s.layout.x + 1} / span ${s.layout.w}`, gridRow: `${s.layout.y + 1} / span ${s.layout.h}` }} />
      ))}
    </div>
  )
}

export default function Builder() {
  const nav = useNavigate()
  const [conns, setConns] = useState([])
  const [templates, setTemplates] = useState([])
  const [connId, setConnId] = useState('')
  const [tpl, setTpl] = useState('executive')
  const [prompt, setPrompt] = useState('')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')
  const [llm, setLlm] = useState(null)

  useEffect(() => {
    api.get('/api/connections').then((c) => { setConns(c); if (c[0]) setConnId(c[0].id) })
    api.get('/api/templates').then(setTemplates)
    api.get('/api/settings/llm').then(setLlm)
  }, [])

  async function generate() {
    setBusy(true); setErr('')
    try {
      const spec = await api.post('/api/reports/generate', { connection_id: +connId, prompt, template_id: tpl })
      nav('/designer', { state: { spec } })
    } catch (e) { setErr(e.message) }
    setBusy(false)
  }

  const conn = conns.find((c) => c.id === +connId)
  return (
    <div className="page">
      <h1>Report Builder</h1>
      <p className="lead">Describe the report you need. The AI plans each widget, writes and validates the SQL, runs it, and lays the results into a template you can then customize.</p>

      <div className="card">
        <div className="row">
          <label>Data source
            <select value={connId} onChange={(e) => setConnId(e.target.value)}>
              {conns.map((c) => <option key={c.id} value={c.id}>{c.name} · {c.dialect}</option>)}
            </select>
          </label>
          {llm && <div className="pill">Model: {llm.provider === 'claude' ? `Claude · ${llm.claude_model}` : `Ollama · ${llm.ollama_model}`}</div>}
          {conn && !conn.indexed_at && <div className="warn">This connection's schema is not indexed yet — index it under Connections first.</div>}
        </div>
        <textarea className="prompt" rows={3} value={prompt} onChange={(e) => setPrompt(e.target.value)}
          placeholder="e.g. Show monthly revenue vs expense for the last 12 months, expense mix by category and top 10 customers" />
        <div className="examples">{EXAMPLES.map((e) => <button key={e} className="chip" onClick={() => setPrompt(e)}>{e}</button>)}</div>
      </div>

      <h3>Template</h3>
      <div className="templates">
        {templates.map((t) => (
          <div key={t.id} className={`template ${tpl === t.id ? 'active' : ''}`} onClick={() => setTpl(t.id)}>
            <TemplateThumb t={t} />
            <div className="t-name">{t.name}</div>
            <div className="t-desc">{t.description}</div>
          </div>
        ))}
      </div>

      <div className="actions">
        <button className="primary big" disabled={!prompt || !connId || busy} onClick={generate}>{busy ? 'Generating report…' : 'Generate report'}</button>
        <button onClick={() => nav('/designer', { state: { spec: { title: 'Blank report', widgets: [], connection_id: +connId } } })}>Start blank</button>
      </div>
      {err && <div className="error">{err}</div>}
    </div>
  )
}
