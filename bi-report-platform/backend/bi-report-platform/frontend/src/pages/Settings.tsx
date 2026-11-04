import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { adminApi, aiModelsApi, connectionsApi, type Usage } from "../api/endpoints";
import type { AIModel, DataConnection } from "../api/types";
import { PROVIDER_INFO } from "../lib/aiModels";
import { DB_TYPE_INFO, STATUS_INFO } from "../lib/connections";

export default function Settings() {
  const [usage, setUsage] = useState<Usage | null>(null);
  const [connections, setConnections] = useState<DataConnection[]>([]);
  const [models, setModels] = useState<AIModel[]>([]);
  useEffect(() => {
    adminApi.usage().then(setUsage).catch(() => setUsage(null));
    connectionsApi.list().then(setConnections).catch(() => setConnections([]));
    aiModelsApi.list().then(setModels).catch(() => setModels([]));
  }, []);

  const tiles = usage ? [
    { label: "People", value: usage.users, sub: `${usage.active_users} active` },
    { label: "Reports", value: usage.reports, sub: `${usage.published} published` },
    { label: "Templates", value: usage.templates, sub: "built-in, shared and private" },
    { label: "Categories", value: usage.categories, sub: "for grouping reports" },
    { label: "Connections", value: usage.connections, sub: `${usage.connections_ok} connected` },
    { label: "AI models", value: usage.ai_models, sub: `${usage.ai_models_active} turned on` },
  ] : [];

  return (
    <div className="page">
      <div className="stack-lg" style={{ maxWidth: 1100 }}>
        <h1 className="h1">Usage and settings</h1>
        {usage && usage.warnings.length > 0 && (
          <div className="alert alert-warn stack-sm" role="alert">
            <div className="strong">Fix before anyone else uses the app</div>
            <ul className="warn-list">{usage.warnings.map((w) => <li key={w}>{w}</li>)}</ul>
          </div>
        )}
        <div className="kpi-grid">
          {tiles.map((t) => (
            <div key={t.label} className="kpi card"><span className="kpi-label">{t.label}</span><span className="kpi-value">{t.value}</span><span className="kpi-sub">{t.sub}</span></div>
          ))}
        </div>
        <div className="two-col">
          <section className="card stack-sm" aria-labelledby="m-h">
            <div className="row-between">
              <h2 id="m-h" className="h2">AI models</h2>
              <Link to="/manage/ai-models" className="small">Manage AI models</Link>
            </div>
            {models.length === 0 && <p className="muted small">No AI models yet. Questions are read by the built-in keyword engine.</p>}
            {models.map((m) => (
              <div className="list-row" key={m.id}>
                <span className="db-badge" style={{ background: PROVIDER_INFO[m.provider].color }} aria-hidden="true">{PROVIDER_INFO[m.provider].short}</span>
                <div className="grow"><span className="strong">{m.name}</span> <span className="muted">{m.model}</span></div>
                {m.is_default && <span className="badge badge-default">Default</span>}
                <span className={"badge " + (m.is_active ? STATUS_INFO[m.status].badge : "badge-off")}>{m.is_active ? STATUS_INFO[m.status].label : "Off"}</span>
              </div>
            ))}
          </section>
          <section className="card stack-sm" aria-labelledby="c-h">
            <div className="row-between">
              <h2 id="c-h" className="h2">Connections</h2>
              <Link to="/manage/connections" className="small">Manage connections</Link>
            </div>
            {connections.length === 0 && <p className="muted small">No databases connected yet. Reports use the sample sales data until you add one.</p>}
            {connections.map((c) => (
              <div className="list-row" key={c.id}>
                <span className="db-badge" style={{ background: DB_TYPE_INFO[c.db_type].color }} aria-hidden="true">{DB_TYPE_INFO[c.db_type].short}</span>
                <div className="grow"><span className="strong">{c.name}</span> <span className="muted">{c.type_label}</span></div>
                <span className={"badge " + STATUS_INFO[c.status].badge}>{STATUS_INFO[c.status].label}</span>
              </div>
            ))}
          </section>
        </div>
      </div>
    </div>
  );
}
