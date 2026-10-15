import { useEffect, useState } from 'react'
import { api } from '../api.js'

const STEPS = ['Upload', 'Map', 'Validate', 'Load']
const TRANSFORMS = ['none', 'strip', 'to_date', 'to_number', 'upper', 'lower', 'negate', 'abs']

function Preview({ data }) {
  if (!data) return null
  return (
    <div className="table-wrap small">
      <table>
        <thead><tr>{data.columns.map((c) => <th key={c}>{c}</th>)}</tr></thead>
        <tbody>{data.rows.map((r, i) => <tr key={i}>{data.columns.map((c) => <td key={c}>{String(r[c] ?? '')}</td>)}</tr>)}</tbody>
      </table>
      <div className="muted">{data.row_count} row(s)</div>
    </div>
  )
}

export default function Etl() {
  const [conns, setConns] = useState([])
  const [connId, setConnId] = useState('')
  const [targets, setTargets] = useState([])
  const [step, setStep] = useState(0)
  const [run, setRun] = useState(null)
  const [srcIdx, setSrcIdx] = useState(0)
  const [table, setTable] = useState('')
  const [mapRes, setMapRes] = useState(null)
  const [mapping, setMapping] = useState({})
  const [tx, setTx] = useState(null)
  const [mode, setMode] = useState('append')
  const [method, setMethod] = useState('direct')
  const [apiUrl, setApiUrl] = useState('')
  const [busy, setBusy] = useState('')
  const [err, setErr] = useState('')
  const [runs, setRuns] = useState([])

  useEffect(() => { api.get('/api/connections').then((c) => { setConns(c); if (c[0]) setConnId(c[0].id) }); api.get('/api/etl/runs').then(setRuns) }, [])
  useEffect(() => { if (connId) api.get(`/api/etl/targets/${connId}`).then(setTargets).catch(() => setTargets([])) }, [connId])

  const wrap = (label, fn) => async (...a) => { setBusy(label); setErr(''); try { await fn(...a) } catch (e) { setErr(e.message) } setBusy('') }

  const upload = wrap('Extracting…', async (file) => {
    const fd = new FormData(); fd.append('connection_id', connId); fd.append('file', file)
    const r = await api.form('/api/etl/extract', fd)
    setRun(r); setSrcIdx(r.tables.length ? 0 : 'text'); setStep(1); setMapRes(null); setTx(null)
  })
  const doMap = wrap('AI is mapping columns…', async () => {
    const r = await api.post(`/api/etl/${run.id}/map`, { source_index: srcIdx === 'text' ? null : +srcIdx, table: table || null })
    setMapRes(r); setMapping(r.mapping.columns); setTable(r.target_table)
  })
  const doTransform = wrap('Transforming & validating…', async () => {
    const r = await api.post(`/api/etl/${run.id}/transform`, { mapping })
    setTx(r); setStep(2)
  })
  const doLoad = wrap('Loading…', async (force = false) => {
    const r = await api.post(`/api/etl/${run.id}/load`, { mode, method, api_url: apiUrl || null, force })
    setTx({ ...tx, ...r }); setStep(3); api.get('/api/etl/runs').then(setRuns)
  })

  const errors = (tx?.issues || []).filter((i) => i.severity === 'error')
  const warnings = (tx?.issues || []).filter((i) => i.severity === 'warning')

  return (
    <div className="page">
      <h1>AI ETL · Accounts / Finance</h1>
      <p className="lead">Upload DOCX, PDF, PPTX, images, Excel, CSV, JSON or XML. Tables are extracted (OCR for scans), the AI maps them to your accounting schema, rules are checked, and rows load in one transaction.</p>
      <div className="stepper">{STEPS.map((s, i) => <div key={s} className={`st ${i === step ? 'on' : ''} ${i < step ? 'done' : ''}`}>{i + 1}. {s}</div>)}</div>
      {busy && <div className="busy">{busy}</div>}
      {err && <div className="error">{err}</div>}

      <div className="card">
        <div className="row">
          <label>Target database
            <select value={connId} onChange={(e) => setConnId(e.target.value)}>{conns.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</select>
          </label>
          <label>Source file
            <input type="file" accept=".csv,.xlsx,.xls,.json,.xml,.docx,.pdf,.pptx,.png,.jpg,.jpeg,.tif,.tiff" onChange={(e) => e.target.files[0] && upload(e.target.files[0])} />
          </label>
        </div>
      </div>

      {run && step >= 1 && (
        <div className="card">
          <h3>Extracted from {run.file_name} <span className="tag">{run.file_type}</span></h3>
          {run.change_log?.length > 0 && <ul className="log">{run.change_log.map((l, i) => <li key={i}>{l}</li>)}</ul>}
          <div className="row">
            <label>Source
              <select value={srcIdx} onChange={(e) => setSrcIdx(e.target.value)}>
                {run.tables.map((t) => <option key={t.index} value={t.index}>{t.name} ({t.row_count} rows)</option>)}
                {run.text_preview && <option value="text">Document text → AI field extraction</option>}
              </select>
            </label>
            <label>Target table
              <select value={table} onChange={(e) => setTable(e.target.value)}>
                <option value="">Let AI choose</option>{targets.map((t) => <option key={t.table}>{t.table}</option>)}
              </select>
            </label>
            <button className="primary" onClick={doMap}>Map with AI</button>
          </div>
          {srcIdx !== 'text' && run.tables[srcIdx] && <Preview data={run.tables[srcIdx]} />}
          {srcIdx === 'text' && <pre className="sql">{run.text_preview}</pre>}

          {mapRes && (
            <>
              <h4>Mapping → {mapRes.target_table} <span className="muted">{mapRes.notes}</span></h4>
              <table className="mapping">
                <thead><tr><th>Target column</th><th>Type</th><th>Source column</th><th>Transform</th><th>Confidence</th></tr></thead>
                <tbody>
                  {mapRes.target_columns.filter((c) => !c.pk).map((c) => {
                    const m = mapping[c.name] || {}
                    return (
                      <tr key={c.name} className={!c.nullable && !m.source ? 'req' : ''}>
                        <td>{c.name}{!c.nullable && ' *'}</td><td className="muted">{c.type}</td>
                        <td><select value={m.source || ''} onChange={(e) => setMapping({ ...mapping, [c.name]: { ...m, source: e.target.value || null } })}>
                          <option value="">— skip —</option>{mapRes.source_columns.map((s) => <option key={s}>{s}</option>)}</select></td>
                        <td><select value={m.transform || 'none'} onChange={(e) => setMapping({ ...mapping, [c.name]: { ...m, transform: e.target.value } })}>
                          {TRANSFORMS.map((t) => <option key={t}>{t}</option>)}</select></td>
                        <td>{m.source ? `${Math.round((m.confidence || 0) * 100)}%` : ''}</td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
              <button className="primary" onClick={doTransform}>Transform & validate</button>
            </>
          )}
        </div>
      )}

      {tx && step >= 2 && (
        <div className="card">
          <h3>Validation {tx.status === 'validated' || tx.status === 'loaded' ? <span className="badge ok">passed</span> : <span className="badge bad">needs review</span>}</h3>
          {errors.map((i, k) => <div key={k} className="issue err">✗ {i.column ? `${i.column}: ` : ''}{i.message}</div>)}
          {warnings.map((i, k) => <div key={k} className="issue warn">! {i.column ? `${i.column}: ` : ''}{i.message}</div>)}
          {tx.change_log?.length > 0 && <details><summary>Change log ({tx.change_log.length})</summary><ul className="log">{tx.change_log.map((l, i) => <li key={i}>{l}</li>)}</ul></details>}
          <Preview data={tx.preview} />
          {errors.length > 0 && <p className="hint">Fix the mapping above (or the source file) and run Transform again.</p>}
          {errors.length === 0 && step === 2 && (
            <div className="row">
              <label>Write mode<select value={mode} onChange={(e) => setMode(e.target.value)}><option>append</option><option>upsert</option><option>replace</option></select></label>
              <label>Method<select value={method} onChange={(e) => setMethod(e.target.value)}><option value="direct">Direct SQL</option><option value="api">REST API</option></select></label>
              {method === 'api' && <label>API endpoint<input value={apiUrl} onChange={(e) => setApiUrl(e.target.value)} placeholder="https://erp.example.com/api/import" /></label>}
              <button className="primary" onClick={() => doLoad(warnings.length > 0)}>Load {tx.preview?.row_count} rows</button>
            </div>
          )}
          {step === 3 && <div className="msg">✓ Loaded {tx.rows_loaded} row(s) into {tx.target_table}</div>}
        </div>
      )}

      <h3>Recent runs</h3>
      <table className="list">
        <thead><tr><th>#</th><th>File</th><th>Target</th><th>Status</th><th>Extracted</th><th>Loaded</th><th>When</th></tr></thead>
        <tbody>{runs.map((r) => <tr key={r.id}><td>{r.id}</td><td>{r.file_name}</td><td>{r.target_table || '—'}</td><td><span className={`badge ${r.status === 'loaded' ? 'ok' : r.status === 'failed' ? 'bad' : ''}`}>{r.status}</span></td><td>{r.rows_extracted}</td><td>{r.rows_loaded}</td><td>{new Date(r.created_at).toLocaleString()}</td></tr>)}</tbody>
      </table>
    </div>
  )
}
