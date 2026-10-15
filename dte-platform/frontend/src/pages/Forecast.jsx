import { useEffect, useMemo, useState } from 'react'
import { api } from '../api.js'
import Chart from '../charts/Chart.jsx'
import { formatNumber } from '../charts/buildOption.js'

export default function Forecast() {
  const [conns, setConns] = useState([])
  const [metrics, setMetrics] = useState([])
  const [connId, setConnId] = useState('')
  const [metric, setMetric] = useState('revenue')
  const [horizon, setHorizon] = useState(6)
  const [res, setRes] = useState(null)
  const [err, setErr] = useState('')

  useEffect(() => {
    api.get('/api/connections').then((c) => { setConns(c); if (c[0]) setConnId(c[0].id) })
    api.get('/api/forecast/metrics').then(setMetrics)
  }, [])

  async function run() {
    setErr('')
    try { setRes(await api.post('/api/forecast', { connection_id: +connId, metric, horizon: +horizon })) } catch (e) { setErr(e.message) }
  }

  const option = useMemo(() => {
    if (!res) return null
    const nf = { style: 'compact' }
    const cats = [...res.history.map((h) => h.period), ...res.forecast.map((f) => f.period)].map((p) => new Date(p + 'T00:00:00').toLocaleString('en', { month: 'short', year: '2-digit' }))
    const n = res.history.length
    const pad = (arr) => [...new Array(n - 1).fill(null), res.history[n - 1].value, ...arr]
    return {
      color: ['#2a78d6', '#eb6834'],
      tooltip: { trigger: 'axis', valueFormatter: (v) => (v == null ? '—' : formatNumber(v, { decimals: 0 })) },
      legend: { top: 0, data: ['Actual', 'Forecast'] },
      grid: { left: 8, right: 16, top: 36, bottom: 8, containLabel: true },
      xAxis: { type: 'category', data: cats, axisTick: { show: false } },
      yAxis: { type: 'value', axisLabel: { formatter: (v) => formatNumber(v, nf) }, splitLine: { lineStyle: { color: '#ebeae6' } } },
      series: [
        { name: 'Actual', type: 'line', data: [...res.history.map((h) => h.value), ...new Array(res.forecast.length).fill(null)], lineStyle: { width: 2 }, symbolSize: 6 },
        { name: 'Forecast', type: 'line', data: pad(res.forecast.map((f) => f.value)), lineStyle: { width: 2, type: 'dashed' }, symbolSize: 6 },
        { name: 'lower', type: 'line', data: pad(res.forecast.map((f) => f.lower)), lineStyle: { opacity: 0 }, stack: 'band', symbol: 'none', tooltip: { show: false } },
        { name: 'band', type: 'line', data: [...new Array(n - 1).fill(null), 0, ...res.forecast.map((f) => f.upper - f.lower)], lineStyle: { opacity: 0 }, stack: 'band', symbol: 'none', areaStyle: { color: '#eb6834', opacity: 0.12 }, tooltip: { show: false } },
      ],
    }
  }, [res])

  return (
    <div className="page">
      <h1>Finance forecasting</h1>
      <p className="lead">Holt-Winters exponential smoothing (seasonal once 24+ months exist) with a 95% band. Results are also written to the <code>forecasts</code> table so reports can query them.</p>
      <div className="card row">
        <label>Database<select value={connId} onChange={(e) => setConnId(e.target.value)}>{conns.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</select></label>
        <label>Metric<select value={metric} onChange={(e) => setMetric(e.target.value)}>{metrics.map((m) => <option key={m.key} value={m.key}>{m.label}</option>)}</select></label>
        <label>Months ahead<input type="number" min={1} max={24} value={horizon} onChange={(e) => setHorizon(e.target.value)} /></label>
        <button className="primary" onClick={run}>Run forecast</button>
      </div>
      {err && <div className="error">{err}</div>}
      {res && (
        <div className="card">
          <h3>{res.label} <span className="tag">{res.model}</span></h3>
          <div style={{ height: 380 }}><Chart option={option} /></div>
          <table className="list">
            <thead><tr><th>Month</th><th className="num">Forecast</th><th className="num">Low (95%)</th><th className="num">High (95%)</th></tr></thead>
            <tbody>{res.forecast.map((f) => <tr key={f.period}><td>{f.period}</td><td className="num">{formatNumber(f.value)}</td><td className="num">{formatNumber(f.lower)}</td><td className="num">{formatNumber(f.upper)}</td></tr>)}</tbody>
          </table>
        </div>
      )}
    </div>
  )
}
