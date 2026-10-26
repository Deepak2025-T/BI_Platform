import { useEffect, useState } from "react";
import { errorMessage } from "../api/client";
import { aiModelsApi } from "../api/endpoints";
import type { AIModel, AIModelInput, AIModelTestResult, AIProviderInfo } from "../api/types";
import { PROVIDER_INFO } from "../lib/aiModels";
import Modal from "./Modal";

interface Props {
  providers: AIProviderInfo[];
  /** Model to edit. Leave out to add a new one. */
  model?: AIModel;
  onClose: () => void;
  onSaved: (m: AIModel, isNew: boolean) => void;
}

export default function AIModelForm({ providers, model, onClose, onSaved }: Props) {
  const [form, setForm] = useState<AIModelInput>(() => model
    ? { name: model.name, provider: model.provider, model: model.model, base_url: model.base_url, api_key: "",
        is_active: model.is_active, is_default: model.is_default }
    : { name: "", provider: "ollama", model: "", base_url: providers.find((p) => p.id === "ollama")?.default_base_url ?? "",
        api_key: "", is_active: true, is_default: false });
  const [found, setFound] = useState<string[]>([]);
  const [finding, setFinding] = useState(false);
  const [findError, setFindError] = useState("");
  const [testing, setTesting] = useState(false);
  const [test, setTest] = useState<AIModelTestResult | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const provider = providers.find((p) => p.id === form.provider)!;
  const info = PROVIDER_INFO[form.provider];
  const keyGiven = !!form.api_key || (!!model?.has_api_key && model.provider === form.provider);
  const ready = form.name.trim() && form.model.trim() && (!provider.needs_base_url || form.base_url.trim())
    && (!provider.needs_key || keyGiven);
  // Blank key on an existing model means "keep the saved one".
  const key = model && !form.api_key ? null : form.api_key;

  const set = <K extends keyof AIModelInput>(k: K, v: AIModelInput[K]) => {
    setForm((f) => ({ ...f, [k]: v }));
    if (k !== "name" && k !== "is_active" && k !== "is_default") setTest(null);
  };

  function pickProvider(p: AIProviderInfo) {
    setForm((f) => ({ ...f, provider: p.id, base_url: p.default_base_url, model: p.suggested_models[0] ?? "" }));
    setFound([]);
    setFindError("");
    setTest(null);
  }

  async function findModels() {
    setFinding(true);
    setFindError("");
    try {
      const ids = await aiModelsApi.discover({ provider: form.provider, base_url: form.base_url, api_key: key, id: model?.id });
      setFound(ids);
      if (ids.length === 0) setFindError("The server has no models yet.");
      else if (!form.model) set("model", ids[0]);
    } catch (err) {
      setFindError(errorMessage(err));
    } finally {
      setFinding(false);
    }
  }

  // Ollama on this machine: list its models straight away.
  useEffect(() => {
    if (!model && form.provider === "ollama") findModels();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function runTest() {
    setTesting(true);
    setTest(null);
    setError("");
    try {
      setTest(await aiModelsApi.testDraft({ provider: form.provider, model: form.model, base_url: form.base_url, api_key: key, id: model?.id }));
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setTesting(false);
    }
  }

  async function save() {
    if (!ready) return;
    setSaving(true);
    setError("");
    const body = { ...form, base_url: provider.needs_base_url ? form.base_url : "", api_key: key };
    try {
      onSaved(model ? await aiModelsApi.update(model.id, body) : await aiModelsApi.create(body), !model);
    } catch (err) {
      setError(errorMessage(err));
      setSaving(false);
    }
  }

  const choices = [...new Set([...provider.suggested_models, ...found])];

  return (
    <Modal title={model ? `Edit ${model.name}` : "Add an AI model"} onClose={onClose} onSubmit={save} error={error}
      footer={
        <>
          <button type="button" className="btn btn-ghost" onClick={runTest} disabled={!ready || testing}>
            {testing ? "Testing…" : "Test model"}
          </button>
          <span className="grow" />
          <button type="button" className="btn btn-ghost" onClick={onClose}>Cancel</button>
          <button type="submit" className="btn btn-primary" disabled={!ready || saving}>
            {saving ? "Saving…" : model ? "Save changes" : "Save model"}
          </button>
        </>
      }>
      <div className="stack">
        <fieldset className="group">
          <legend>Where the model runs</legend>
          <div className="provider-cards">
            {providers.map((p) => (
              <button key={p.id} type="button" className={"provider-card" + (form.provider === p.id ? " on" : "")}
                aria-pressed={form.provider === p.id} onClick={() => pickProvider(p)}>
                <span className="db-badge" style={{ background: PROVIDER_INFO[p.id].color }}>{PROVIDER_INFO[p.id].short}</span>
                <span className="strong">{PROVIDER_INFO[p.id].title}</span>
                <span className="muted small">{PROVIDER_INFO[p.id].blurb}</span>
              </button>
            ))}
          </div>
        </fieldset>

        <label className="field">Display name
          <input data-autofocus value={form.name} maxLength={80} required placeholder="e.g. Qwen 14B (local), Claude Opus"
            onChange={(e) => set("name", e.target.value)} />
          <span className="hint">People see this name in the model picker when they ask a question.</span>
        </label>

        {provider.needs_base_url && (
          <label className="field">Server address
            <input value={form.base_url} required onChange={(e) => { set("base_url", e.target.value); setFound([]); }} />
            <span className="hint">{info.baseUrlHint}</span>
          </label>
        )}

        {(provider.needs_key || form.provider === "openai_compatible") && (
          <label className="field">API key{provider.needs_key ? "" : " (optional)"}
            <input type="password" value={form.api_key ?? ""} autoComplete="new-password"
              placeholder={model?.has_api_key ? "Saved. Leave blank to keep it." : ""}
              onChange={(e) => set("api_key", e.target.value)} />
            <span className="hint">{info.keyHint}</span>
          </label>
        )}

        <div className="field">
          <label htmlFor="ai-model-id">Model</label>
          <div className="row-wrap model-row">
            <input id="ai-model-id" className="grow" list="ai-model-choices" value={form.model} required
              placeholder={info.modelHint} onChange={(e) => set("model", e.target.value)} />
            <datalist id="ai-model-choices">{choices.map((c) => <option key={c} value={c} />)}</datalist>
            <button type="button" className="btn btn-ghost btn-sm" onClick={findModels}
              disabled={finding || (provider.needs_base_url && !form.base_url.trim()) || (provider.needs_key && !keyGiven)}>
              {finding ? "Looking…" : form.provider === "ollama" ? "Find installed models" : "Find models"}
            </button>
          </div>
          {choices.length > 0 && (
            <div className="chip-row">
              {choices.slice(0, 8).map((c) => (
                <button key={c} type="button" className={"chip-btn sm" + (form.model === c ? " on" : "")} onClick={() => set("model", c)}>{c}</button>
              ))}
            </div>
          )}
          <span className="hint">{findError || info.modelHint}</span>
        </div>

        <div className="form-grid">
          <label className="check">
            <input type="checkbox" checked={form.is_active}
              onChange={(e) => setForm((f) => ({ ...f, is_active: e.target.checked, is_default: e.target.checked && f.is_default }))} />
            <span>On<br /><span className="hint">People can pick it when they ask.</span></span>
          </label>
          <label className="check">
            <input type="checkbox" checked={form.is_default} disabled={!form.is_active}
              onChange={(e) => set("is_default", e.target.checked)} />
            <span>Default<br /><span className="hint">Preselected in the Ask box.</span></span>
          </label>
        </div>

        {test && (
          <div className={"alert " + (test.ok ? "alert-ok" : "alert-error")} role="status">
            <div className="strong">{test.ok ? "The model works" : "The model didn't answer"}</div>
            <div>{test.message}</div>
          </div>
        )}
      </div>
    </Modal>
  );
}
