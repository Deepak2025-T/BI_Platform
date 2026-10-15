import { useEffect, useState } from 'react'
import { api } from '../api.js'

const EMPTY = { name: '', dialect: 'postgres', host: 'localhost', port: 5432, database: '', username: '', password: '', schema_name: '' }

export default function Connections() {
  const [dialects, setDialects] = useState([])
  const [list, setList] = useState([])
  const [form, setForm] = useState(EMPTY)
  const [editing, setEditing] = useState(null)
  const [status, setStatus] = useState({})
  const [msg, setMsg] = useState('')

  const load = () => api.get('/api/connections').then(setList)
  useEffect(() => { api.get('/api/dialects').then(setDialects); load() }, [])

  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value })
  const d = dialects.find((x) => x.key === form.dialect)

  async function test() {
    setMsg('Testing…')
    const r = await api.post('/api/connections/test', { ...form, port: form.port ? +form.port : null })
    setMsg(r.ok ? '✓ Connection OK' : '✗ ' + r.error)
  }
  async function save() {
    try {
      const body = { ...form, port: form.port ? +form.port : null }
      editing ? await api.put(`/api/connections/${editing}`, body) : await api.post('/api/connections', body)
      setForm(EMPTY); setEditing(null); setMsg('Saved'); load()
    } catch (e) { setMsg(e.message) }
  }
  async function index(c) {
    setStatus({ ...status, [c.id]: 'Indexing schema into pgvector…' })
    try {
      const r = await api.post(`/api/connections/${c.id}/index`, {})
      setStatus({ ...status, [c.id]: `✓ ${r.tables_indexed} tables indexed` }); load()
    } catch (e) { setStatus({ ...status, [c.id]: '✗ ' + e.message }) }
  }

  return (
    <div className="page">
      <h1>Connections</h1>
      <p className="lead">Connect any relational database. PostgreSQL is fully supported today; the other dialects are wired through SQLAlchemy and work once their driver is installed.</p>
      <div className="grid2">
        <div className="card">
          <h3>{editing ? 'Edit connection' : 'New connection'}</h3>
          <div className="dialects">
            {dialects.map((x) => (
              <button key={x.key} className={`dialect ${form.dialect === x.key ? 'active' : ''}`}
                onClick={() => setForm({ ...form, dialect: x.key, port: x.default_port || '' })}>
                {x.label}{x.status !== 'active' && <span className="tag">beta</span>}
              </button>
            ))}
          </div>
          {d && d.status !== 'active' && <div className="hint">Requires driver: <code>{d.driver}</code></div>}
          <label>Name<input value={form.name} onChange={set('name')} placeholder="Finance ERP (prod)" /></label>
          {form.dialect === 'sqlite' ? (
            <label>Database file path<input value={form.database} onChange={set('database')} /></label>
          ) : (<>
            <div className="row2">
              <label>Host<input value={form.host} onChange={set('host')} /></label>
              <label>Port<input value={form.port} onChange={set('port')} /></label>
            </div>
            <label>{form.dialect === 'oracle' ? 'Service name' : 'Database'}<input value={form.database} onChange={set('database')} /></label>
            <div className="row2">
              <label>Username<input value={form.username} onChange={set('username')} /></label>
              <label>Password<input type="password" value={form.password} onChange={set('password')} placeholder={editing ? '(unchanged)' : ''} /></label>
            </div>
            <label>Schema (optional)<input value={form.schema_name} onChange={set('schema_name')} placeholder={form.dialect === 'postgres' ? 'public' : ''} /></label>
          </>)}
          <div className="actions">
            <button onClick={test}>Test</button>
            <button className="primary" onClick={save} disabled={!form.name || !form.database}>Save</button>
            {editing && <button onClick={() => { setEditing(null); setForm(EMPTY) }}>Cancel</button>}
          </div>
          {msg && <div className="msg">{msg}</div>}
        </div>

        <div>
          {list.map((c) => (
            <div key={c.id} className="card conn">
              <div className="conn-head"><b>{c.name}</b><span className="tag">{c.dialect}</span></div>
              <div className="muted">{c.username}@{c.host}:{c.port}/{c.database}</div>
              <div className="muted">{c.indexed_at ? `Schema indexed ${new Date(c.indexed_at).toLocaleString()}` : 'Not indexed — RAG has no schema yet'}</div>
              <div className="actions">
                <button onClick={() => index(c)}>{c.indexed_at ? 'Re-index schema' : 'Index schema'}</button>
                <button onClick={async () => { const r = await api.post(`/api/connections/${c.id}/test`); setStatus({ ...status, [c.id]: r.ok ? '✓ OK' : '✗ ' + r.error }) }}>Test</button>
                <button onClick={() => { setEditing(c.id); setForm({ ...EMPTY, ...c, password: '' }) }}>Edit</button>
                <button onClick={async () => { await api.del(`/api/connections/${c.id}`); load() }}>Delete</button>
              </div>
              {status[c.id] && <div className="msg">{status[c.id]}</div>}
              <Glossary conn={c} />
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

function Glossary({ conn }) {
  const [term, setTerm] = useState('')
  const [def, setDef] = useState('')
  const [ok, setOk] = useState('')
  return (
    <details className="glossary">
      <summary>Business glossary (improves SQL accuracy)</summary>
      <div className="row2">
        <input placeholder="Term, e.g. Net profit" value={term} onChange={(e) => setTerm(e.target.value)} />
        <input placeholder="Definition, e.g. revenue − expense from journal_lines" value={def} onChange={(e) => setDef(e.target.value)} />
      </div>
      <button className="small" disabled={!term || !def} onClick={async () => { await api.post(`/api/connections/${conn.id}/glossary`, { term, definition: def }); setTerm(''); setDef(''); setOk('Added') }}>Add term</button> {ok}
    </details>
  )
}
