import { useEffect, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { errorMessage } from "../api/client";
import { aiModelsApi, assistantApi, dataModelsApi, reportsApi, templatesApi } from "../api/endpoints";
import type { AIModelPublic, DataModelSummary, DataSourceInfo, PlannedChart, Report, ReportTemplate, TemplateCategory } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import CategoryBadge from "../components/CategoryBadge";
import FlowDiagram, { type FlowStep } from "../components/FlowDiagram";
import Icon from "../components/Icon";
import TemplateCard from "../components/TemplateCard";
import TemplateForm from "../components/TemplateForm";
import { useToast } from "../components/Toast";
import { type AskModel, rememberModel, rememberedModel } from "../lib/aiModels";
import { bySolution, rememberModel as rememberDataModel, rememberedModel as rememberedDataModel } from "../lib/dataModel";
import { shortDate } from "../lib/format";
import { useCountUp, useReveal } from "../lib/motion";
import { TEMPLATE_CATEGORIES } from "../lib/report";
import { rememberSource, rememberedSource, sourceIdOf, sourceValue } from "../lib/sources";
import type { BuildRequest } from "./BuildDashboard";

/** Shown until the chosen database suggests its own, and if it has nothing to suggest. */
const SUGGESTIONS = [
  "Show monthly revenue by region for Q1 2024 and the top 5 products",
  "Gross revenue by region for Q4 2023",
  "Show customer churn by signup cohort",
];

/** The chart shapes an AI-planned dashboard can be held to. */
const CHARTS: [PlannedChart, string][] = [
  ["kpi", "Number"], ["bar", "Bars"], ["line", "Line"], ["area", "Area"], ["pie", "Pie"], ["table", "Table"],
];

const HOME_TEMPLATES = 7; // plus the "New template" card
const RECENT_SHOWN = 4;

type Mode = "chat" | "build";

/** One animated number in the strip under the hero. */
function Stat({ icon, value, label }: { icon: string; value: number; label: string }) {
  const shown = useCountUp(value);
  return (
    <div className="stat">
      <span className="stat-icon" aria-hidden="true"><Icon name={icon} size={16} /></span>
      <span className="stat-value">{shown}</span>
      <span className="stat-label">{label}</span>
    </div>
  );
}

export default function Home() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const toast = useToast();
  const state = location.state as { prompt?: string; template?: ReportTemplate; model?: AskModel | null;
                                   mode?: Mode; dataModel?: string; source?: string } | null;
  const [prompt, setPrompt] = useState(state?.prompt ?? state?.template?.prompt ?? "");
  const [template, setTemplate] = useState<ReportTemplate | null>(state?.template ?? null);
  const [reports, setReports] = useState<Report[]>([]);
  const [templates, setTemplates] = useState<ReportTemplate[]>([]);
  const [creating, setCreating] = useState(false);
  const [models, setModels] = useState<AIModelPublic[]>([]);
  // "builtin" or a model id. Coming back from a question keeps the model it used.
  const [modelChoice, setModelChoice] = useState<string>(state?.model ? String(state.model.id) : "");
  const [mode, setMode] = useState<Mode>(state?.mode ?? (state?.template ? "build" : "chat"));
  const [sources, setSources] = useState<DataSourceInfo[]>([]);
  const [sourceChoice, setSourceChoice] = useState(state?.source ?? "builtin");
  // The OpenPages object model to build against: which object types exist, and how they join.
  // Only OpenPages connections have one, so the picker only appears for those.
  const [dataModels, setDataModels] = useState<DataModelSummary[]>([]);
  const [dataModel, setDataModel] = useState(state?.dataModel ?? "");
  const [params, setParams] = useState({ date_from: "", date_to: "", filters: "" });
  // Chart shapes to hold the model to; empty lets it pick whatever fits each chart.
  const [charts, setCharts] = useState<PlannedChart[]>([]);
  // Questions this database can answer, from its own columns.
  const [ideas, setIdeas] = useState<string[]>([]);
  const [building, setBuilding] = useState(false);
  // Templates are chosen in two steps: the domain first, then the templates filed under it.
  const [domain, setDomain] = useState<TemplateCategory | "">("");
  const [tplSection, tplShown] = useReveal<HTMLElement>();
  const [recentSection, recentShown] = useReveal<HTMLElement>();

  useEffect(() => {
    reportsApi.list().then(setReports).catch(() => setReports([]));
    // Your own templates first, then shared, then built-in.
    const rank = (t: ReportTemplate) => (t.is_builtin ? 2 : t.owner_id === user?.id ? 0 : 1);
    templatesApi.list()
      .then((t) => setTemplates(t.sort((a, b) => rank(a) - rank(b))))
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
      const last = state?.source ?? rememberedSource();
      if (last && list.some((x) => sourceValue(x) === last)) setSourceChoice(last);
    }).catch(() => setSources([]));
    dataModelsApi.list().then(setDataModels).catch(() => setDataModels([]));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user?.id]);

  // Every database suggests its own questions, so the chips are never about someone else's data.
  useEffect(() => {
    let current = true;
    assistantApi.promptIdeas(sourceIdOf(sourceChoice))
      .then((list) => { if (current) setIdeas(list); })
      .catch(() => { if (current) setIdeas([]); });
    return () => { current = false; };
  }, [sourceChoice]);

  const recent = reports.slice(0, RECENT_SHOWN);
  // The templates the Template picker offers: all of them, or one category's.
  const inDomain = domain ? templates.filter((t) => t.category === domain) : templates;

  const chosenModel = models.find((m) => String(m.id) === modelChoice) ?? null;
  const chooseModel = (v: string) => { setModelChoice(v); rememberModel(v); };

  const chosenSource = sources.find((x) => sourceValue(x) === sourceChoice) ?? null;
  const isOpenPages = chosenSource?.db_type === "openpages";
  const chooseSource = (v: string) => {
    setSourceChoice(v);
    rememberSource(v);
    // Each database remembers its own model; a model from another one would name types this
    // database has never heard of.
    setDataModel(rememberedDataModel(v));
  };
  const chooseDataModel = (v: string) => { setDataModel(v); rememberDataModel(sourceChoice, v); };
  // A model only applies where there is one, so it is never sent for a plain SQL database.
  const dataModelSent = isOpenPages && dataModel ? dataModel : null;

  /**
   * Choosing a template. There are two kinds, and they behave differently:
   *  - a dashboard template brings its own ready-written charts, and builds on the database
   *    chosen below, with no AI model involved;
   *  - a question template fills the box. One that also carries a classic layout (sections,
   *    palette) only applies to the sample data, which is the only thing that layout draws.
   */
  const pick = (t: ReportTemplate | null) => {
    if (!t || template?.id === t.id) { setTemplate(null); return; }
    setTemplate(t);
    setDomain(t.category);
    setPrompt(t.prompt);
    setMode("build");
    if (t.layout.kind !== "dashboard" && Object.keys(t.layout).length > 0) chooseSource("builtin");
    document.getElementById("ask")?.focus();
  };

  // A dashboard template is built from its own SQL, so it needs neither the model nor the prompt.
  const readyMade = template?.layout.kind === "dashboard" ? template : null;
  // A question template with a layout, or no AI model at all, makes the classic sales report.
  // Otherwise the AI model plans a dashboard from the chosen database.
  const hasLayout = !!template && !readyMade && Object.keys(template.layout).length > 0;
  const classic = mode === "build" && !readyMade && (hasLayout || !chosenModel);
  const needsModel = !readyMade && !chosenModel && (mode === "chat" || sourceChoice !== "builtin");
  const plan = readyMade
    ? `Builds ${readyMade.name.split(": ").pop()} on ${chosenSource?.name ?? "the database"} from its own queries. No AI model is used.`
    : needsModel
    ? (mode === "chat" ? "Chat needs an AI model. Pick one above." : "Pick an AI model to build a dashboard from this database.")
    : mode === "chat" ? `${chosenModel?.name} answers from ${chosenSource?.name ?? "the database"}, with the query and the rows.`
    : classic ? "Builds the standard sales report from the sample data."
    : `${chosenModel?.name} plans a dashboard of 4 to 6 charts from ${chosenSource?.name ?? "the database"}.`;

  const ready = (!!readyMade || prompt.trim().length >= 3) && !needsModel && !building;

  // The diagram mirrors the choices above it, so the picture is never out of date.
  const words = prompt.trim() ? prompt.trim().split(/\s+/).length : 0;
  const steps: FlowStep[] = [
    { icon: "question", label: "Your question", sub: words ? `${words} word${words === 1 ? "" : "s"}` : "Waiting for you" },
    {
      icon: "spark",
      label: "AI model",
      sub: classic || readyMade ? "Not used" : chosenModel?.name ?? "None picked",
      dim: classic || !!readyMade || !chosenModel,
    },
    { icon: "database", label: "Database", sub: classic ? "Sample sales data" : chosenSource?.name ?? "Sample sales data" },
    mode === "chat"
      ? { icon: "chat", label: "Answer", sub: "Query and rows shown" }
      : {
          icon: "grid", label: "Dashboard",
          sub: readyMade ? `${(readyMade.layout.widgets ?? []).filter((w) => w.kind !== "text").length} ready-made charts`
            : classic ? "Standard sales report"
            : charts.length ? `4 to 6 charts, ${charts.length === 1 ? CHARTS.find(([c]) => c === charts[0])?.[1].toLowerCase() : "chosen shapes"}`
            : "4 to 6 charts",
        },
  ];

  /** Builds a ready-made dashboard template on the chosen database, then opens it. */
  async function buildTemplate(t: ReportTemplate) {
    setBuilding(true);
    try {
      const { report, skipped } = await templatesApi.build(t.id, sourceIdOf(sourceChoice));
      toast(skipped.length
        ? `Built, without ${skipped.length} chart${skipped.length === 1 ? "" : "s"} this database can't answer.`
        : "Built. Arrange it, then publish.");
      navigate(`/reports/${report.id}/edit`);
    } catch (err) {
      toast(errorMessage(err));
    } finally {
      setBuilding(false);
    }
  }

  function ask() {
    if (readyMade) { buildTemplate(readyMade); return; }
    const text = prompt.trim();
    if (text.length < 3 || needsModel) return;
    if (mode === "chat" && chosenModel) {
      navigate("/chat", { state: { source: sourceChoice, model: String(chosenModel.id), question: text,
                                   dataModel: dataModelSent } });
    } else if (classic || !chosenModel) {
      navigate("/ask", { state: { prompt: text, template: template ?? undefined,
                                  model: chosenModel ? { id: chosenModel.id, name: chosenModel.name } : null } });
    } else {
      const req: BuildRequest = {
        source: { id: sourceIdOf(sourceChoice), name: chosenSource?.name ?? "" },
        model: { id: chosenModel.id, name: chosenModel.name },
        prompt: text,
        parameters: { date_from: params.date_from || null, date_to: params.date_to || null,
                      filters: params.filters.trim(), charts },
        dataModel: dataModelSent,
      };
      navigate("/build", { state: req });
    }
  }

  return (
    <div className="page narrow-wide home">
      <div className="stack-lg">
        <div className="hero">
          <div className="hero-glow" aria-hidden="true" />
          <div className="stack">
            <h1 className="display rise">What do you want to know, {user?.full_name.split(" ")[0]}?</h1>
            <p className="muted lead rise rise-1">Ask in plain English. You'll see how the question was understood before anything is built.</p>

            <div className="flow-wrap rise rise-2">
              <FlowDiagram steps={steps} live={ready} />
            </div>

            <div className="stat-strip rise rise-3">
              <Stat icon="reports" value={reports.length} label={reports.length === 1 ? "report" : "reports"} />
              <Stat icon="template" value={templates.length} label={templates.length === 1 ? "template" : "templates"} />
              <Stat icon="spark" value={models.length} label={models.length === 1 ? "AI model" : "AI models"} />
              <Stat icon="database" value={sources.length} label={sources.length === 1 ? "database" : "databases"} />
            </div>

            <div className={"ask-box rise rise-4" + (ready ? " ready" : "")}>
              <div className="pills mode-pills" role="group" aria-label="What to do">
                <button className={"pill" + (mode === "chat" ? " on" : "")} aria-pressed={mode === "chat"}
                  onClick={() => { setMode("chat"); setTemplate(null); }}>
                  <Icon name="chat" size={15} />Chat with the data
                </button>
                <button className={"pill" + (mode === "build" ? " on" : "")} aria-pressed={mode === "build"}
                  onClick={() => setMode("build")}>
                  <Icon name="grid" size={15} />Build a report
                </button>
              </div>
              {template && (
                <div className="ask-template">
                  <span className="tpl-dot" style={{ background: template.color }} aria-hidden="true" />
                  <span className="small">
                    Using template <b>{template.name}</b>
                    {readyMade ? ", with its own charts" : hasLayout ? ", with its layout" : ""}
                  </span>
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
                  <div className="field grow">
                    <span>Charts</span>
                    <div className="chip-row tight" role="group" aria-label="Chart types to use">
                      {CHARTS.map(([id, label]) => {
                        const on = charts.includes(id);
                        return (
                          <button key={id} type="button" className={"chip-btn sm" + (on ? " on" : "")} aria-pressed={on}
                            onClick={() => setCharts(on ? charts.filter((c) => c !== id) : [...charts, id])}>
                            {label}
                          </button>
                        );
                      })}
                      {charts.length > 0 && (
                        <button type="button" className="link-btn small" onClick={() => setCharts([])}>Any</button>
                      )}
                    </div>
                    <span className="hint">{charts.length ? "Only these shapes are used." : "The model picks what fits."}</span>
                  </div>
                </fieldset>
              )}
              <div className="ask-foot">
                <div className="row-wrap">
                  {mode === "build" && templates.length > 0 && (
                    <>
                      <label className="model-picker">
                        <span className="muted small">Category</span>
                        <select value={domain} aria-label="Template category"
                          onChange={(e) => { setDomain(e.target.value as TemplateCategory | ""); pick(null); }}>
                          <option value="">All categories</option>
                          {TEMPLATE_CATEGORIES.filter((c) => templates.some((t) => t.category === c))
                            .map((c) => (
                              <option key={c} value={c}>
                                {c} ({templates.filter((t) => t.category === c).length})
                              </option>
                            ))}
                        </select>
                      </label>
                      <label className="model-picker">
                        <span className="muted small">Template</span>
                        <select value={template?.id ?? ""} aria-label="Template to build from"
                          onChange={(e) => pick(inDomain.find((t) => String(t.id) === e.target.value) ?? null)}>
                          <option value="">{inDomain.length ? "No template" : "None in this category"}</option>
                          <optgroup label="Ready-made dashboards">
                            {inDomain.filter((t) => t.layout.kind === "dashboard")
                              .map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
                          </optgroup>
                          <optgroup label="Questions">
                            {inDomain.filter((t) => t.layout.kind !== "dashboard")
                              .map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
                          </optgroup>
                        </select>
                      </label>
                    </>
                  )}
                  <label className="model-picker">
                    <span className="muted small">Database</span>
                    <select value={sourceChoice} onChange={(e) => chooseSource(e.target.value)} aria-label="Database" disabled={classic}>
                      {sources.map((x) => <option key={sourceValue(x)} value={sourceValue(x)}>{x.name}</option>)}
                      {sources.length === 0 && <option value="builtin">Sample sales data</option>}
                    </select>
                  </label>
                  {isOpenPages && dataModels.length > 0 && (
                    <label className="model-picker">
                      <span className="muted small">Data model</span>
                      <select value={dataModel} onChange={(e) => chooseDataModel(e.target.value)}
                        aria-label="OpenPages data model" disabled={!!readyMade}>
                        <option value="">Every shared object type</option>
                        {bySolution(dataModels).map(([solution, list]) => (
                          <optgroup key={solution} label={solution}>
                            {list.map((m) => (
                              <option key={m.key} value={m.key}>
                                {m.namespace}{m.is_default ? " (default)" : ""} &middot; {m.entity_count} types
                              </option>
                            ))}
                          </optgroup>
                        ))}
                      </select>
                    </label>
                  )}
                  <label className="model-picker">
                    <span className="muted small">AI model</span>
                    <select value={modelChoice} onChange={(e) => chooseModel(e.target.value)}
                      aria-label="AI model for this question" disabled={!!readyMade}>
                      {models.map((m) => (
                        <option key={m.id} value={m.id} title={m.provider_label}>{m.name}{m.is_default ? " (default)" : ""}</option>
                      ))}
                      <option value="builtin">Built-in engine (no AI)</option>
                    </select>
                  </label>
                </div>
                <button className="btn btn-primary btn-lg btn-go" onClick={ask} disabled={!ready}>
                  {building ? "Building…" : mode === "chat" ? "Ask" : readyMade ? "Build this template" : "Build my report"}
                  <Icon name="arrow" size={17} className="go-arrow" />
                </button>
              </div>
              <div className="ask-plan muted small">{plan} Ctrl+Enter to send.</div>
            </div>

            <div className="chip-row rise rise-5">
              <span className="muted small">Try</span>
              {(ideas.length ? ideas : SUGGESTIONS).map((s) => (
                <button key={s} className="chip-btn" onClick={() => setPrompt(s)}>{s}</button>
              ))}
            </div>
          </div>
        </div>

        <section ref={tplSection} className={"stack reveal" + (tplShown ? " in" : "")} aria-labelledby="tpl-h">
          <div className="row-between">
            <h2 id="tpl-h" className="h2 head-icon"><Icon name="template" size={17} />Or start from a template</h2>
            <Link to="/templates" className="small">Manage templates</Link>
          </div>
          <div className="tpl-grid stagger">
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

        <section ref={recentSection} className={"card stack-sm reveal" + (recentShown ? " in" : "")} aria-labelledby="rec-h">
          <div className="row-between">
            <h2 id="rec-h" className="h2 head-icon"><Icon name="clock" size={17} />Recent reports</h2>
            <Link to="/reports" className="small">See all</Link>
          </div>
          {recent.length === 0 && <p className="muted">No reports yet. Ask a question above to build your first one.</p>}
          {recent.map((r) => (
            <div key={r.id} className="list-row lift">
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
