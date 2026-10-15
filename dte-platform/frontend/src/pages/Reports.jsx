import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import GridLayout, { WidthProvider } from 'react-grid-layout'
import { api } from '../api.js'
import Widget from '../components/Widget.jsx'

const Grid = WidthProvider(GridLayout)

export function Reports() {
  const [list, setList] = useState([])
  const load = () => api.get('/api/reports').then(setList)
  useEffect(() => { load() }, [])
  return (
    <div className="page">
      <h1>Reports</h1>
      {!list.length && <p className="lead">No saved reports yet. Generate one in <Link to="/">Report Builder</Link>.</p>}
      <table className="list">
        <thead><tr><th>Title</th><th>Template</th><th>Status</th><th>Updated</th><th /></tr></thead>
        <tbody>
          {list.map((r) => (
            <tr key={r.id}>
              <td><Link to={`/view/${r.id}`}>{r.title}</Link><div className="muted">{r.prompt}</div></td>
              <td>{r.template_id || '—'}</td>
              <td>{r.published ? <span className="badge ok">Published</span> : <span className="badge">Draft</span>}</td>
              <td>{new Date(r.updated_at).toLocaleString()}</td>
              <td className="right">
                <Link className="btn" to={`/designer/${r.id}`}>Edit</Link>{' '}
                <button onClick={async () => { await api.del(`/api/reports/${r.id}`); load() }}>Delete</button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export function Viewer() {
  const { id } = useParams()
  const [r, setR] = useState(null)
  const [err, setErr] = useState('')
  useEffect(() => { api.get(`/api/reports/${id}`).then(setR).catch((e) => setErr(e.message)) }, [id])
  if (err) return <div className="page error">{err}</div>
  if (!r) return <div className="page">Loading live data…</div>
  return (
    <div className="page viewer">
      <div className="toolbar">
        <h1>{r.title}</h1><span className="spacer" />
        <Link className="btn" to={`/designer/${r.id}`}>Edit</Link>
        <button onClick={() => window.print()}>Print / PDF</button>
      </div>
      {r.prompt && <div className="prompt-echo">“{r.prompt}”</div>}
      <Grid cols={12} rowHeight={64} margin={[12, 12]} isDraggable={false} isResizable={false}
        layout={r.spec.widgets.map((w) => ({ i: w.id, ...w.layout }))}>
        {r.spec.widgets.map((w) => <div key={w.id}><Widget widget={w} /></div>)}
      </Grid>
    </div>
  )
}
