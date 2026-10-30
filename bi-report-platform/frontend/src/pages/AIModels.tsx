import { useEffect, useState } from "react";
import { errorMessage } from "../api/client";
import { adminApi, aiModelsApi } from "../api/endpoints";
import type { AIModel, AIProviderInfo } from "../api/types";
import AIModelForm from "../components/AIModelForm";
import Icon from "../components/Icon";
import { useToast } from "../components/Toast";
import { PROVIDER_INFO } from "../lib/aiModels";
import { STATUS_INFO } from "../lib/connections";
import { shortDate } from "../lib/format";

export default function AIModels() {
  const toast = useToast();
  const [models, setModels] = useState<AIModel[] | null>(null);
  const [providers, setProviders] = useState<AIProviderInfo[]>([]);
  const [keyWarning, setKeyWarning] = useState("");
  const [form, setForm] = useState<{ model?: AIModel } | null>(null);
  const [testing, setTesting] = useState<number | null>(null);

  const reload = () => aiModelsApi.list().then(setModels);

  useEffect(() => {
    reload().catch((e) => { toast(errorMessage(e)); setModels([]); });
    aiModelsApi.providers().then(setProviders).catch(() => setProviders([]));
    adminApi.usage().then((u) => setKeyWarning(u.warnings.find((w) => w.includes("CONNECTIONS_KEY")) ?? "")).catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [toast]);

  async function test(m: AIModel) {
    setTesting(m.id);
    try {
      const res = await aiModelsApi.test(m.id);
      toast(res.ok ? `${m.name}: ${res.message}` : `${m.name} failed: ${res.message}`);
      await reload();
    } catch (err) {
      toast(errorMessage(err));
    } finally {
      setTesting(null);
    }
  }

  async function change(m: AIModel, body: { is_active?: boolean; is_default?: boolean }, message: string) {
    try {
      await aiModelsApi.update(m.id, body);
      await reload(); // turning one model on as default turns the others off
      toast(message);
    } catch (err) { toast(errorMessage(err)); }
  }

  async function remove(m: AIModel) {
    if (!window.confirm(`Delete "${m.name}"? People won't be able to pick it any more. Its saved API key is deleted too.`)) return;
    try {
      await aiModelsApi.remove(m.id);
      setModels((list) => list?.filter((x) => x.id !== m.id) ?? null);
      toast("Model deleted");
    } catch (err) { toast(errorMessage(err)); }
  }

  async function saved(m: AIModel, isNew: boolean) {
    setForm(null);
    await reload();
    toast(isNew ? `${m.name} added. Click Test to check it answers.` : "Model saved");
  }

  const canAdd = providers.length > 0;

  return (
    <div className="page">
      <div className="stack" style={{ maxWidth: 1100 }}>
        <div className="row-between">
          <div>
            <h1 className="h1">AI models</h1>
            <p className="muted small">The models people can pick when they ask a question: local models on your own server, or hosted APIs.</p>
          </div>
          <button className="btn btn-primary btn-lg" disabled={!canAdd} onClick={() => setForm({})}><Icon name="plus" />Add model</button>
        </div>

        {keyWarning && (
          <div className="alert alert-warn">
            <div className="strong">Set CONNECTIONS_KEY to save API keys</div>
            <div>{keyWarning} Local Ollama models without a key still work.</div>
          </div>
        )}

        <div className="alert alert-info small">
          <span className="strong">What the model does today:</span> it reads the question and picks the period, measure and
          date column for the sales report. It never writes or runs SQL, so it can't change data. Writing SQL for your own
          database connections is week 2 of the build plan.
        </div>

        {models === null ? <div className="card">Loading…</div> : models.length === 0 ? (
          <div className="card empty-state stack">
            <h2 className="h2">No AI models yet</h2>
            <p className="muted">Questions are read by the built-in keyword engine until you add a model. Pick where it runs:</p>
            <div className="provider-cards">
              {Object.entries(PROVIDER_INFO).map(([id, p]) => (
                <div key={id} className="provider-card static">
                  <span className="db-badge" style={{ background: p.color }}>{p.short}</span>
                  <span className="strong">{p.title}</span>
                  <span className="muted small">{p.blurb}</span>
                </div>
              ))}
            </div>
            <button className="btn btn-primary self-start" disabled={!canAdd} onClick={() => setForm({})}><Icon name="plus" />Add model</button>
          </div>
        ) : (
          <div className="conn-list">
            {models.map((m) => {
              const p = PROVIDER_INFO[m.provider];
              const status = STATUS_INFO[m.status];
              return (
                <article key={m.id} className={"card conn-card" + (m.is_active ? "" : " is-off")} aria-label={m.name}>
                  <div className="conn-main">
                    <span className="db-badge lg" style={{ background: p.color }} aria-hidden="true">{p.short}</span>
                    <div className="grow">
                      <div className="row-wrap">
                        <h2 className="h2">{m.name}</h2>
                        {m.is_default && <span className="badge badge-default">Default</span>}
                        {!m.is_active && <span className="badge badge-off">Off</span>}
                        <span className={"badge " + status.badge}>{status.label}</span>
                      </div>
                      <div className="muted small">{m.provider_label}, {m.model}{m.base_url && ` at ${m.base_url}`}</div>
                      {m.last_tested_at && <div className="muted small">Tested {shortDate(m.last_tested_at)}</div>}
                      {m.status === "error" && m.last_error && <div className="note note-bad conn-error">{m.last_error}</div>}
                    </div>
                  </div>
                  <div className="conn-actions">
                    <button className="btn btn-ghost btn-sm" onClick={() => test(m)} disabled={testing === m.id}>{testing === m.id ? "Testing…" : "Test"}</button>
                    {m.is_active && !m.is_default && (
                      <button className="btn btn-ghost btn-sm" onClick={() => change(m, { is_default: true }, `${m.name} is now the default`)}>Make default</button>
                    )}
                    <button className="btn btn-ghost btn-sm" onClick={() => change(m, { is_active: !m.is_active }, m.is_active ? `${m.name} turned off` : `${m.name} turned on`)}>
                      {m.is_active ? "Turn off" : "Turn on"}
                    </button>
                    <button className="btn btn-ghost btn-sm" onClick={() => setForm({ model: m })}>Edit</button>
                    <button className="icon-btn danger" aria-label={`Delete ${m.name}`} title="Delete" onClick={() => remove(m)}><Icon name="trash" size={16} /></button>
                  </div>
                </article>
              );
            })}
          </div>
        )}
      </div>

      {form && <AIModelForm providers={providers} model={form.model} onClose={() => setForm(null)} onSaved={saved} />}
    </div>
  );
}
