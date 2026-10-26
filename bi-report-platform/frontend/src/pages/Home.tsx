import { useEffect, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { aiModelsApi, assistantApi, reportsApi, templatesApi } from "../api/endpoints";
import type { AIModelPublic, DataSourceInfo, Report, ReportTemplate } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import CategoryBadge from "../components/CategoryBadge";
import Icon from "../components/Icon";
import TemplateCard from "../components/TemplateCard";
import TemplateForm from "../components/TemplateForm";
import { useToast } from "../components/Toast";
import { type AskModel, rememberModel, rememberedModel } from "../lib/aiModels";
import { shortDate } from "../lib/format";
import { rememberSource, rememberedSource, sourceIdOf, sourceValue } from "../lib/sources";
import type { BuildRequest } from "./BuildDashboard";

const SUGGESTIONS = [
  "Show monthly revenue by region for Q1 2024 and the top 5 products",
  "Gross revenue by region for Q4 2023",
  "Show customer churn by signup cohort",
];

const HOME_TEMPLATES = 7; // plus the "New template" card

type Mode = "chat" | "build";

export default function Home() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const toast = useToast();
  const state = location.state as { prompt?: string; template?: ReportTemplate; model?: AskModel | null; mode?: Mode } | null;
  const [prompt, setPrompt] = useState(state?.prompt ?? state?.template?.prompt ?? "");
  const [template, setTemplate] = useState<ReportTemplate | null>(state?.template ?? null);
  const [recent, setRecent] = useState<Report[]>([]);
  const [templates, setTemplates] = useState<ReportTemplate[]>([]);
  const [creating, setCreating] = useState(false);
  const [models, setModels] = useState<AIModelPublic[]>([]);
  // "builtin" or a model id. Coming back from a question keeps the model it used.
  const [modelChoice, setModelChoice] = useState<string>(state?.model ? String(state.model.id) : "");
  const [mode, setMode] = useState<Mode>(state?.mode ?? (state?.template ? "build" : "chat"));
  const [sources, setSources] = useState<DataSourceInfo[]>([]);
  const [sourceChoice, setSourceChoice] = useState("builtin");
  const [params, setParams] = useState({ date_from: "", date_to: "", filters: "" });

  useEffect(() => {
    reportsApi.list().then((r) => setRecent(r.slice(0, 4))).catch(() => setRecent([]));
    // Your own templates first, then shared, then built-in.
    const rank = (t: ReportTemplate) => (t.is_builtin ? 2 : t.owner_id === user?.id ? 0 : 1);
    templatesApi.list()
      // Dashboard templates (e.g. OpenPages) are built from the Templates page, not asked here.
      .then((t) => setTemplates(t.filter((x) => x.layout.kind !== "dashboard").sort((a, b) => rank(a) - rank(b))))
      .catch(() => setTemplates([]));
    aiModelsApi.available().then((list) => {
      setModels(list);
      // Keep the current or last choice if that model is still on, otherwise use the default model.
      setModelChoice((current) => {
        const valid = (v: string | null) => v === "builtin" || list.some((m) => String(m.id) === v);
        if (current && valid(current)) return current;
        const last = rememberedModel();
        if (valid(last)) return last!;
        const preset = list.find((m) => m.is_default);
        return preset ? String(preset.id) : "builtin";
      });
    }).catch(() => { setModels([]); setModelChoice("builtin"); });
    assistantApi.sources().then((list) => {
      setSources(list);
      const last = rememberedSource();
      if (last && list.some((x) => sourceValue(x) === last)) setSourceChoice(last);
    }).catch(() => setSources([]));
  }, [user?.id]);

  const chosenModel = models.find((m) => String(m.id) === modelChoice) ?? null;
  const chooseModel = (v: string) => { setModelChoice(v); rememberModel(v); };

  const chosenSource = sources.find((x) => sourceValue(x) === sourceChoice) ?? null;
  const chooseSource = (v: string) => { setSourceChoice(v); rememberSource(v); };

  const pick = (t: ReportTemplate) => {
    if (template?.id === t.id) { setTemplate(null); return; }
    setTemplate(t);
    setPrompt(t.prompt);
    setMode("build");
    chooseSource("builtin"); // templates are questions about the sample sales data
    document.getElementById("ask")?.focus();
  };

  // "Build a report" with a template, or without an AI model, makes the classic sales report.
  // Otherwise the AI model plans a dashboard from the chosen database.
  const classic = mode === "build" && (!!template || !chosenModel);
  const needsModel = !chosenModel && (mode === "chat" || sourceChoice !== "builtin");
  const plan = needsModel
    ? (mode === "chat" ? "Chat needs an AI model. Pick one above." : "Pick an AI model to build a dashboard from this database.")
    : mode === "chat" ? `${chosenModel?.name} answers from ${chosenSource?.name ?? "the database"}, with the query and the rows.`
    : classic ? "Builds the standard sales report from the sample data."
    : `${chosenModel?.name} plans a dashboard of 4 to 6 charts from ${chosenSource?.name ?? "the database"}.`;

  function ask() {
    const text = prompt.trim();
    if (text.length < 3 || needsModel) return;
    if (mode === "chat" && chosenModel) {
      navigate("/chat", { state: { source: sourceChoice, model: String(chosenModel.id), question: text } });
    } else if (classic || !chosenModel) {
      navigate("/ask", { state: { prompt: text, template: template ?? undefined,
                                  model: chosenModel ? { id: chosenModel.id, name: chosenModel.name } : null } });
    } else {
      const req: BuildRequest = {
        source: { id: sourceIdOf(sourceChoice), name: chosenSource?.name ?? "" },
        model: { id: chosenModel.id, name: chosenModel.name },
        prompt: text,
        parameters: { date_from: params.date_from || null, date_to: params.date_to || null, filters: params.filters.trim() },
      };
      navigate("/build", { state: req });
    }
  }

  return (
    <div className="page narrow-wide">
      <div className="stack-lg">
        <div className="stack">
          <h1 className="display">What do you want to know, {user?.full_name.split(" ")[0]}?</h1>
          <p className="muted lead">Ask in plain English. You'll see how the question was understood before anything is built.</p>
          <div className="ask-box">
            <div className="pills mode-pills" role="group" aria-label="What to do">
              <button className={"pill" + (mode === "chat" ? " on" : "")} aria-pressed={mode === "chat"}
                onClick={() => { setMode("chat"); setTemplate(null); }}>Chat with the data</button>
              <button className={"pill" + (mode === "build" ? " on" : "")} aria-pressed={mode === "build"}
                onClick={() => setMode("build")}>Build a report</button>
            </div>
            {template && (
              <div className="ask-template">
                <span className="tpl-dot" style={{ background: template.color }} aria-hidden="true" />
                <span className="small">Using template <b>{template.name}</b>{Object.keys(template.layout).length > 0 && ", with its layout"}</span>
                <button className="icon-btn sm" aria-label="Stop using this template" onClick={() => setTemplate(null)}>✕</button>
              </div>
            )}
            <label htmlFor="ask" className="sr-only">Your question</label>
            <textarea id="ask" rows={3} value={prompt} onChange={(e) => setPrompt(e.target.value)}
              placeholder={mode === "chat" ? "e.g. Which region grew fastest last quarter?" : "e.g. Sales dashboard for Q1 2024 by region and product"}
              onKeyDown={(e) => { if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) ask(); }} />
            {mode === "build" && !classic && !needsModel && (
              <fieldset className="ask-params">
                <legend className="muted small">Parameters (optional)</legend>
                <label className="field">From
                  <input type="date" value={params.date_from} onChange={(e) => setParams({ ...params, date_from: e.target.value })} />
                </label>
                <label className="field">To
                  <input type="date" value={params.date_to} onChange={(e) => setParams({ ...params, date_to: e.target.value })} />
                </label>
                <label className="field grow">Filter
                  <input value={params.filters} maxLength={300} placeholder="e.g. region = North, status = paid"
                    onChange={(e) => setParams({ ...params, filters: e.target.value })} />
                </label>
              </fieldset>
            )}
            <div className="ask-foot">
              <div className="row-wrap">
                <label className="model-picker">
                  <span className="muted small">Database</span>
                  <select value={sourceChoice} onChange={(e) => chooseSource(e.target.value)} aria-label="Database" disabled={!!template}>
                    {sources.map((x) => <option key={sourceValue(x)} value={sourceValue(x)}>{x.name}</option>)}
                    {sources.length === 0 && <option value="builtin">Sample sales data</option>}
                  </select>
                </label>
                <label className="model-picker">
                  <span className="muted small">AI model</span>
                  <select value={modelChoice} onChange={(e) => chooseModel(e.target.value)} aria-label="AI model for this question">
                    {models.map((m) => (
                      <option key={m.id} value={m.id} title={m.provider_label}>{m.name}{m.is_default ? " (default)" : ""}</option>
                    ))}
                    <option value="builtin">Built-in engine (no AI)</option>
                  </select>
                </label>
              </div>
              <button className="btn btn-primary btn-lg" onClick={ask} disabled={prompt.trim().length < 3 || needsModel}>
                {mode === "chat" ? "Ask" : "Build my report"}
              </button>
            </div>
            <div className="ask-plan muted small">{plan} Ctrl+Enter to send.</div>
          </div>
          <div className="chip-row">
            <span className="muted small">Try</span>
            {SUGGESTIONS.map((s) => (
              <button key={s} className="chip-btn" onClick={() => setPrompt(s)}>{s}</button>
            ))}
          </div>
        </div>

        <section className="stack" aria-labelledby="tpl-h">
          <div className="row-between">
            <h2 id="tpl-h" className="h2">Or start from a template</h2>
            <Link to="/templates" className="small">Manage templates</Link>
          </div>
          <div className="tpl-grid">
            {templates.slice(0, HOME_TEMPLATES).map((t) => (
              <TemplateCard key={t.id} template={t} selected={template?.id === t.id} onUse={() => pick(t)} />
            ))}
            <button className="tpl tpl-new" onClick={() => setCreating(true)}>
              <Icon name="plus" size={22} />
              <span className="strong">New template</span>
              <span className="muted small">Save your own question and layout</span>
            </button>
          </div>
        </section>

        <section className="card stack-sm" aria-labelledby="rec-h">
          <div className="row-between">
            <h2 id="rec-h" className="h2">Recent reports</h2>
            <Link to="/reports" className="small">See all</Link>
          </div>
          {recent.length === 0 && <p className="muted">No reports yet. Ask a question above to build your first one.</p>}
          {recent.map((r) => (
            <div key={r.id} className="list-row">
              <div className="grow">
                <div className="row-wrap"><span className="strong">{r.title}</span>{r.category && <CategoryBadge category={r.category} />}</div>
                <div className="muted small">{r.status === "published" ? "Published" : "Draft"}, updated {shortDate(r.updated_at)}, by {r.owner_name}</div>
              </div>
              <Link className="btn btn-ghost" to={`/reports/${r.id}`}>Open</Link>
            </div>
          ))}
        </section>
      </div>
      {creating && (
        <TemplateForm initial={prompt.trim() ? { prompt: prompt.trim() } : undefined} onClose={() => setCreating(false)}
          onSaved={(t) => {
            setTemplates((list) => [t, ...list]);
            setCreating(false);
            setTemplate(t);
            setPrompt(t.prompt);
            toast("Template created");
          }} />
      )}
    </div>
  );
}
