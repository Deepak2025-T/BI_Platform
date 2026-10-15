import { useEffect, useState } from 'react'
import { NavLink, Route, Routes } from 'react-router-dom'
import Builder from './pages/Builder.jsx'
import Designer from './pages/Designer.jsx'
import { Reports, Viewer } from './pages/Reports.jsx'
import Connections from './pages/Connections.jsx'
import Etl from './pages/Etl.jsx'
import Forecast from './pages/Forecast.jsx'
import Settings from './pages/Settings.jsx'

const NAV = [
  ['/', 'Report Builder', '✦'], ['/reports', 'Reports', '▦'], ['/designer', 'Designer', '✎'],
  ['/etl', 'AI ETL', '⇄'], ['/forecast', 'Forecast', '↗'], ['/connections', 'Connections', '⛁'], ['/settings', 'Model config', '⚙'],
]

export default function App() {
  const [theme, setTheme] = useState(() => { try { return localStorage.getItem('theme') || 'light' } catch { return 'light' } })
  useEffect(() => {
    document.documentElement.dataset.theme = theme
    try { localStorage.setItem('theme', theme) } catch { /* private mode */ }
  }, [theme])
  return (
    <div className="app">
      <nav className="sidebar">
        <div className="brand">DTE<span>AI ETL · BI</span></div>
        {NAV.map(([to, label, icon]) => (
          <NavLink key={to} to={to} end={to === '/'} className={({ isActive }) => (isActive ? 'nav active' : 'nav')}>
            <span className="nav-icon">{icon}</span>{label}
          </NavLink>
        ))}
        <span className="spacer" />
        <button className="theme" onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}>{theme === 'dark' ? '☀ Light' : '☾ Dark'}</button>
      </nav>
      <div className="content">
        <Routes>
          <Route path="/" element={<Builder />} />
          <Route path="/reports" element={<Reports />} />
          <Route path="/designer/:id?" element={<Designer />} />
          <Route path="/view/:id" element={<Viewer />} />
          <Route path="/etl" element={<Etl />} />
          <Route path="/forecast" element={<Forecast />} />
          <Route path="/connections" element={<Connections />} />
          <Route path="/settings" element={<Settings />} />
        </Routes>
      </div>
    </div>
  )
}
