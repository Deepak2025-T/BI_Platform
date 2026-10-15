import { useEffect, useState } from 'react'
import { api } from '../api.js'

const CLAUDE_MODELS = ['claude-sonnet-4-5', 'claude-opus-4-1', 'claude-haiku-4-5']
const OLLAMA_SUGGESTED = ['qwen2.5-coder:7b', 'qwen2.5-coder:14b', 'sqlcoder:7b', 'llama3.1:8b', 'deepseek-coder-v2:16b']

export default function Settings() {
  const [cfg, setCfg] = useState(null)
  const [models, setModels] = useState([])
  const [msg, setMsg] = useState('')
  useEffect(() => {
    api.get('/api/settings/llm').then(setCfg)
    api.get('/api/settings/ollama/models').then((r) => setModels(r.models || []))
  }, [])
  if (!cfg) return <div className="page">Loading…</div>
  const set = (k) => (e) => setCfg({ ...cfg, [k]: e.target.type === 'number' ? +e.target.value : e.target.value })
  const ollamaOptions = [...new Set([...models, ...OLLAMA_SUGGESTED])]

  return (
    <div className="page">
      <h1>Model configuration</h1>
      <p className="lead">Choose which LLM writes SQL, maps ETL columns and writes insights. Embeddings for RAG always run locally on Ollama (pgvector stores them).</p>
      <div className="modes">
        <div className={`mode ${cfg.provider === 'ollama' ? 'active' : ''}`} onClick={() => setCfg({ ...cfg, provider: 'ollama' })}>
          <b>Open source (Ollama)</b><p>Self-hosted, data never leaves your network. No per-token cost.</p>
        </div>
        <div className={`mode ${cfg.provider === 'claude' ? 'active' : ''}`} onClick={() => setCfg({ ...cfg, provider: 'claude' })}>
          <b>Claude (Anthropic API)</b><p>Higher SQL accuracy on complex joins. Billed per token to the client's API key.</p>
        </div>
      </div>

      <div className="grid2">
        <div className="card">
          <h3>Ollama</h3>
          <label>Server URL<input value={cfg.ollama_url} onChange={set('ollama_url')} /></label>
          <label>SQL / reasoning model
            <input list="ollama-models" value={cfg.ollama_model} onChange={set('ollama_model')} />
            <datalist id="ollama-models">{ollamaOptions.map((m) => <option key={m} value={m} />)}</datalist>
          </label>
          <label>Embedding model<input value={cfg.ollama_embed_model} onChange={set('ollama_embed_model')} /></label>
          <div className="hint">{models.length ? `Installed: ${models.join(', ')}` : 'Ollama not reachable — run `ollama pull qwen2.5-coder:7b` and `ollama pull nomic-embed-text`.'}</div>
        </div>
        <div className="card">
          <h3>Claude</h3>
          <label>API key<input type="password" value={cfg.anthropic_api_key} onChange={set('anthropic_api_key')} placeholder="sk-ant-…" /></label>
          <label>SQL model (strong)
            <input list="claude-models" value={cfg.claude_model} onChange={set('claude_model')} />
          </label>
          <label>Fast model (intent, insights)
            <input list="claude-models" value={cfg.claude_fast_model} onChange={set('claude_fast_model')} />
          </label>
          <datalist id="claude-models">{CLAUDE_MODELS.map((m) => <option key={m} value={m} />)}</datalist>
        </div>
      </div>
      <div className="card">
        <label>Temperature<input type="number" step="0.1" min="0" max="1" value={cfg.temperature} onChange={set('temperature')} /></label>
        <div className="actions">
          <button onClick={async () => { setMsg('Testing…'); const r = await api.post('/api/settings/llm/test', cfg); setMsg(r.ok ? `✓ ${cfg.provider} replied: ${r.reply}` : `✗ ${r.error}`) }}>Test model</button>
          <button className="primary" onClick={async () => { setCfg(await api.put('/api/settings/llm', cfg)); setMsg('Saved') }}>Save</button>
        </div>
        {msg && <div className="msg">{msg}</div>}
      </div>
    </div>
  )
}
