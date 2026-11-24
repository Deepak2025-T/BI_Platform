import { useEffect, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { errorMessage } from "../api/client";
import { aiModelsApi, assistantApi, dataModelsApi, reportsApi, templatesApi } from "../api/endpoints";
import type { AIModelPublic, ClarifyResult, DashboardParameters, DataModelSummary, DataSourceInfo, PlannedChart, Report, ReportIdea, ReportTemplate, TemplateCategory } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import CategoryBadge from "../components/CategoryBadge";
import ClarifyDialog from "../components/ClarifyDialog";
import Dictate from "../components/Dictate";
import DomainTiles from "../components/DomainTiles";
import { PRODUCT_NAME } from "../components/Brand";
import Icon from "../components/Icon";
import ReportIdeas from "../components/ReportIdeas";
import { SuggestionChips } from "../components/Suggestions";
import TemplateForm from "../components/TemplateForm";
import { useToast } from "../components/Toast";
import { type AskModel, rememberedModel } from "../lib/aiModels";
import { bySolution, rememberModel as rememberDataModel, rememberedModel as rememberedDataModel } from "../lib/dataModel";
import { appendSpoken } from "../lib/dictation";
import { shortDate } from "../lib/format";
import { useCountUp, useReveal } from "../lib/motion";
import { TEMPLATE_CATEGORIES } from "../lib/report";
import { rememberSource, rememberedSource, sourceIdOf, sourceValue } from "../lib/sources";
import { type BuildRequest, useBuildJob } from "../lib/buildJob";
import { useSuggestions } from "../lib/suggestions";

/**
 * Shown until the chosen database suggests its own, and if it has nothing to suggest.
 *
 * They are deliberately of different shapes - a trend, a ranking, a comparison, a share of a
 * whole, a question about what is missing - because the first thing someone types tends to be a
 * variation on whatever they were shown, and one shape of example teaches one shape of question.
 */
const SUGGESTIONS = [
  "Show monthly revenue by region for Q1 2024 and the top 5 products",
  "Gross revenue by region for Q4 2023",
  "Show customer churn by signup cohort",
  "Which region grew fastest in the last six months",
  "Top 10 customers by revenue, and what they bought",
  "Revenue this year against last, by month",
  "Which products have not sold at all this quarter",
  "Average order value by channel",
  "Orders by status, and how long each status takes",
  "Where is revenue concentrated: share by customer",
];

/** How many suggestions appear before the rest are folded behind "N more". */
const IDEAS_SHOWN = 4;

/** The chart shapes an AI-planned dashboard can be held to. */
const CHARTS: [PlannedChart, string][] = [
  ["kpi", "Number"], ["bar", "Bars"], ["line", "Line"], ["area", "Area"], ["pie", "Pie"], ["table", "Table"],
];

const RECENT_SHOWN = 4;

type Mode = "chat" | "build";

/**
 * The four ways in, shown where the question → model → database → answer picture used to be.
 *
 * That picture described the controls underneath it rather than doing anything, and it was the
 * first thing on the page. These start the work instead: two of them choose what kind of answer
 * you want, one opens the ready-made dashboards, and one goes to what you have already.
 */
const STARTS: { id: Mode | "template" | "reports"; icon: string; label: string; hint: string }[] = [
  { id: "build", icon: "grid", label: "Build a report", hint: "A page of charts from a sentence" },
  { id: "chat", icon: "chat", label: "Ask one question", hint: "An answer, with the query behind it" },
  { id: "template", icon: "template", label: "Start from a template", hint: "Ready-made dashboards" },
  { id: "reports", icon: "reports", label: "Open what I built", hint: "Your reports and their data" },
];

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
  const { job: buildJob, start: startBuild } = useBuildJob();
  const state = location.state as { prompt?: string; template?: ReportTemplate; model?: AskModel | null;
                                   mode?: Mode; dataModel?: string; source?: string } | null;
  const [prompt, setPrompt] = useState(state?.prompt ?? state?.template?.prompt ?? "");
  // A reference report is shown in the box in ordinary words and sent in the wording written for
  // the query engine. This holds that second wording and the plain text it belongs to, so an
  // edited box is sent as the person wrote it and an untouched one is sent as it was meant.
  const [technical, setTechnical] = useState<{ plain: string; build: string } | null>(null);
  const toSend = (text: string) =>
    technical && text.trim() === technical.plain.trim() ? technical.build : text;
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
  // Whole reports worth building on it, from what it holds and what this person asked for before.
  const [recommended, setRecommended] = useState<ReportIdea[]>([]);
  const [recommending, setRecommending] = useState(false);
  // Hidden once they start typing their own request, and by the panel's own "I'll write my own".
  // Choosing another database brings it back, because the suggestions are then about something
  // else and worth a look again.
  const [hideIdeas, setHideIdeas] = useState(false);
  const [building, setBuilding] = useState(false);
  // Working out what the request leaves open, and the questions it left open. No AI model is used
  // for either, so the wait is a round trip rather than a generation.
  const [checking, setChecking] = useState(false);
  const [clarifying, setClarifying] = useState<
    { prompt: string; parameters: DashboardParameters; result: ClarifyResult } | null>(null);
  // Templates are chosen in two steps: the domain first, then the templates filed under it.
  const [domain, setDomain] = useState<TemplateCategory | "">("");
  // The settings most questions never need. They are folded away so the box reads as a box to
  // type in, and the button says how many are set, because a hidden setting that is doing
  // something is worse than a visible one that isn't.
  const [more, setMore] = useState(false);
  // How many suggested questions are on screen; the rest are one click away.
  const [shownIdeas, setShownIdeas] = useState(IDEAS_SHOWN);
  // Questions this database can answer: the same grounded starters chat offers (a mix of basic,
  // analytical and advanced questions, this person's own recent ones first), worked out from the
  // columns without a model so they arrive with the database. Fetched once per database.
  const starters = useSuggestions(sourceChoice ? `home-starter:${sourceChoice}` : null,
    () => ({ kind: "starter", source_id: sourceIdOf(sourceChoice), limit: 8 }));
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

  // ...and its own reports worth building. A failure here is silent on purpose: suggestions are
  // an offer, and an error about an offer nobody asked for is worse than no offer.
  useEffect(() => {
    let current = true;
    setRecommending(true);
    setHideIdeas(false);
    assistantApi.reportIdeas(sourceIdOf(sourceChoice))
      .then((list) => { if (current) setRecommended(list); })
      .catch(() => { if (current) setRecommended([]); })
      .finally(() => { if (current) setRecommending(false); });
    return () => { current = false; };
  }, [sourceChoice]);

  // A build already running. One AI model answers one of these at a time, so the box points at
  // the one in flight rather than quietly replacing it.
  const buildRunning = !!buildJob && !buildJob.result && !buildJob.error;
  const recent = reports.slice(0, RECENT_SHOWN);
  // The general questions, for when the database has none of its own (or they were hidden).
  const plainIdeas = starters.dismissed || (!starters.loading && !starters.data?.suggestions.length);
  // The templates the Template picker offers: all of them, or one category's.
  const inDomain = domain ? templates.filter((t) => t.category === domain) : templates;

  const chosenModel = models.find((m) => String(m.id) === modelChoice) ?? null;

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
  // What the folded-away settings are doing. The button says the count, because a setting that is
  // quietly changing the result is worse out of sight than a setting that is merely in the way.
  const extrasSet = [template, isOpenPages && dataModel, params.date_from, params.date_to,
                     params.filters.trim(), charts.length].filter(Boolean).length;
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
    : mode === "chat" ? `${PRODUCT_NAME} answers from ${chosenSource?.name ?? "the database"}, with the query and the rows.`
    : classic ? "Builds the standard sales report from the sample data."
    : `${PRODUCT_NAME} plans a dashboard of 4 to 6 charts from ${chosenSource?.name ?? "the database"}.`;

  const ready = (!!readyMade || prompt.trim().length >= 3) && !needsModel && !building && !checking && !buildRunning;


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

  /** Hands the request to the job above the routes, so walking away doesn't cancel it. */
  function startReport(text: string, parameters: DashboardParameters) {
    if (!chosenModel) return;
    setClarifying(null);
    const req: BuildRequest = {
      source: { id: sourceIdOf(sourceChoice), name: chosenSource?.name ?? "" },
      model: { id: chosenModel.id, name: chosenModel.name },
      prompt: toSend(text),
      parameters,
      dataModel: dataModelSent,
    };
    startBuild(req);
    navigate("/build");
  }

  /**
   * Asks what the request leaves open before building it.
   *
   * A request that already says the shape, the measure and the colours gets no questions and goes
   * straight to the build - which is the common case once someone has typed a few of these. The
   * questions are a help and never a gate: if they can't be worked out, the report is built as
   * written rather than held up.
   */
  async function askToClarify(text: string) {
    const parameters: DashboardParameters = {
      date_from: params.date_from || null, date_to: params.date_to || null,
      filters: params.filters.trim(), charts,
    };
    setChecking(true);
    try {
      const result = await assistantApi.clarify({ source_id: sourceIdOf(sourceChoice),
                                                  prompt: toSend(text),
                                                  parameters, data_model: dataModelSent });
      if (result.questions.length) { setClarifying({ prompt: text, parameters, result }); return; }
    } catch {
      // Nothing here is worth stopping a build for.
    } finally {
      setChecking(false);
    }
    startReport(text, parameters);
  }

  function ask() {
    if (buildRunning) { navigate("/build"); return; }
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
      askToClarify(text);
    }
  }

  return (
    <div className="page narrow-wide home">
      <div className="stack-lg">
        <div className="hero">
          <div className="hero-glow" aria-hidden="true" />
          <div className="stack">
            {/* The company's logo over the question, so the first screen after signing in carries
                the same mark the sign-in page did. */}
            <img className="hero-logo rise" src="/timus-logo.png" width={52} height={30}
              alt="Timus Consulting Services - Technology Simplified!" />
            <h1 className="display rise">
              {mode === "build"
                ? <>What report should {PRODUCT_NAME} build, {user?.full_name.split(" ")[0]}?</>
                : <>What do you want to ask, {user?.full_name.split(" ")[0]}?</>}
            </h1>
            <p className="muted lead rise rise-1">
              {mode === "build"
                ? "Describe it in a sentence — the charts, the tabs, the colours. Anything it leaves open you'll be asked about before it is built."
                : "Ask in plain English. You'll see the query and the rows behind every answer."}
            </p>

            {/* Four ways in, instead of a picture of how the tool works. Each one sets something
                up and puts the cursor where the next word goes; the picture only described what
                the controls below already say. */}
            <div className="start-row rise rise-2" role="group" aria-label={`Ways to start with ${PRODUCT_NAME}`}>
              {STARTS.map((s) => (
                <button key={s.id} type="button"
                  className={"start-card" + (s.id === mode ? " on" : "")}
                  onClick={() => {
                    if (s.id === "build" || s.id === "chat") {
                      setMode(s.id);
                      if (s.id === "chat") setTemplate(null);
                      setTimeout(() => document.getElementById("ask")?.focus(), 0);
                    } else if (s.id === "template") {
                      setMode("build");
                      setMore(true);
                      setTimeout(() => document.getElementById("tpl-domain")?.focus(), 0);
                    } else {
                      navigate("/reports");
                    }
                  }}>
                  <span className="start-icon" aria-hidden="true"><Icon name={s.icon} size={18} /></span>
                  <span className="start-label">{s.label}</span>
                  <span className="start-hint">{s.hint}</span>
                </button>
              ))}
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
              <Dictate what={mode === "chat" ? "your question" : "your report request"}
                onPhrase={(said) => setPrompt((p) => appendSpoken(p, said))} />
              {/* Building a report is where the blank box bites hardest: a question is one line,
                  a report is a page of them. So in build mode the database says what it can show
                  before anything is typed, and the one-line questions stay for chat. */}
              {mode === "build" && !hideIdeas && !prompt.trim() && !readyMade && (
                <ReportIdeas ideas={recommended} loading={recommending && !recommended.length}
                  sourceName={chosenSource?.name ?? "this database"}
                  onHide={() => setHideIdeas(true)}
                  onPick={(idea) => {
                    setPrompt(idea.prompt);
                    setTechnical(idea.build_prompt
                      ? { plain: idea.prompt, build: idea.build_prompt } : null);
                    // A reference report is written against one namespace. Selecting it hands the
                    // query writer that namespace's real parent/child pairs; left on "every shared
                    // object type" it has to guess which joins are legal, and the charts whose
                    // guess is wrong are dropped from the report.
                    if (idea.data_model) chooseDataModel(idea.data_model);
                    setHideIdeas(true);
                    document.getElementById("ask")?.focus();
                  }} />
              )}

              {/* Questions to try, against the box they fill: a blank box always has a way in. */}
              {!starters.dismissed && (
                <SuggestionChips title={`Questions to try on ${chosenSource?.name ?? "this database"}`}
                  items={starters.data?.suggestions ?? []} loading={starters.loading} error={starters.error}
                  origin={undefined} pickHint="fills the box"
                  onPick={(x) => { setPrompt(x.text); document.getElementById("ask")?.focus(); }}
                  onRefresh={starters.refresh} onDismiss={starters.dismiss} />
              )}
              {plainIdeas && (
                <div className="chip-row suggest-row">
                  <span className="muted small">Try</span>
                  {SUGGESTIONS.slice(0, shownIdeas).map((idea) => (
                    <button key={idea} className="chip-btn" onClick={() => setPrompt(idea)}>{idea}</button>
                  ))}
                  {SUGGESTIONS.length > shownIdeas && (
                    <button className="link-btn small" onClick={() => setShownIdeas(SUGGESTIONS.length)}>
                      {SUGGESTIONS.length - shownIdeas} more
                    </button>
                  )}
                </div>
              )}

              <div className="ask-foot">
                <div className="row-wrap">
                  <label className="model-picker">
                    <span className="muted small">Database</span>
                    <select value={sourceChoice} onChange={(e) => chooseSource(e.target.value)} aria-label="Database" disabled={classic}>
                      {sources.map((x) => <option key={sourceValue(x)} value={sourceValue(x)}>{x.name}</option>)}
                      {sources.length === 0 && <option value="builtin">Sample sales data</option>}
                    </select>
                  </label>
                  {/* Which model answers is a setting, not a question to put to someone building
                      a report: the name of a model is no help in deciding what to ask for, and in
                      front of a client it is somebody else's brand on your product. The model is
                      chosen under AI models and shown here as this product's own name. Managers
                      who need to compare models can still switch there. */}
                  <label className="model-picker">
                    <span className="muted small">Answered by</span>
                    <span className="model-name">{PRODUCT_NAME}</span>
                  </label>
                  {mode === "build" && (
                    <button type="button" className={"btn btn-ghost btn-sm more-btn" + (more ? " on" : "")}
                      aria-expanded={more} onClick={() => setMore((m) => !m)}
                      title="Start from a template, limit the dates, or choose the chart shapes">
                      <Icon name="settings" size={15} />
                      More options{extrasSet > 0 ? ` · ${extrasSet} set` : ""}
                      <Icon name={more ? "up" : "down"} size={14} />
                    </button>
                  )}
                </div>
                <button className="btn btn-primary btn-lg btn-go" onClick={ask} disabled={!ready}>
                  {building ? "Building…" : checking ? "Checking…" : mode === "chat" ? "Ask"
                    : readyMade ? "Build this template" : "Build my report"}
                  <Icon name="arrow" size={17} className="go-arrow" />
                </button>
              </div>

              {mode === "build" && more && (
                <fieldset className="ask-more">
                  <legend className="sr-only">More options</legend>
                  {templates.length > 0 && (
                    <>
                      <label className="field">Start from
                        <select id="tpl-domain" value={domain} aria-label="Template category"
                          onChange={(e) => { setDomain(e.target.value as TemplateCategory | ""); pick(null); }}>
                          <option value="">All categories</option>
                          {TEMPLATE_CATEGORIES.filter((c) => templates.some((t) => t.category === c))
                            .map((c) => (
                              <option key={c} value={c}>{c} ({templates.filter((t) => t.category === c).length})</option>
                            ))}
                        </select>
                      </label>
                      <label className="field grow">Template
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
                  {isOpenPages && dataModels.length > 0 && (
                    <label className="field grow">Data model
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
                  {!classic && !needsModel && (
                    <>
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
                    </>
                  )}
                </fieldset>
              )}
              <div className="ask-plan muted small">
                {buildRunning ? (
                  <>
                    A report is building now.{" "}
                    <button className="link-btn" onClick={() => navigate("/build")}>Watch it</button>{" "}
                    — it carries on while you work, and this box is free again when it lands.
                  </>
                ) : <>{plan} Ctrl+Enter to send.</>}
              </div>
            </div>
          </div>
        </div>

        <section ref={tplSection} className={"stack reveal" + (tplShown ? " in" : "")} aria-labelledby="tpl-h">
          <div className="row-between">
            <h2 id="tpl-h" className="h2 head-icon"><Icon name="template" size={17} />Or start from a template</h2>
            <Link to="/templates" className="small">Browse all {templates.length}</Link>
          </div>
          <DomainTiles templates={templates} onNew={() => setCreating(true)} />
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
      {clarifying && (
        <ClarifyDialog prompt={clarifying.prompt} parameters={clarifying.parameters} result={clarifying.result}
          onBuild={startReport} onClose={() => setClarifying(null)} />
      )}
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
