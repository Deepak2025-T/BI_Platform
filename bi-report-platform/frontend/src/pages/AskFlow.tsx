import axios from "axios";
import { useEffect, useRef, useState } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import { errorMessage } from "../api/client";
import { queryApi, reportsApi } from "../api/endpoints";
import type { Attempt, DateCol, GenerationFailure, MeasureId, PeriodId, QueryParams, QueryResult, ReportTemplate } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import DataTable from "../components/DataTable";
import Icon from "../components/Icon";
import { useToast } from "../components/Toast";
import type { AskModel } from "../lib/aiModels";
import { MEASURE_OPTIONS, PERIOD_OPTIONS, defaultConfig } from "../lib/report";

const STEPS = [
  "Understanding your question",
  "Finding the relevant tables",
  "Writing the SQL",
  "Checking the query is valid and read-only",
  "Running the query",
];
const CHECK_STEP = 3;
const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

type Phase = "working" | "answer" | "failed";

export default function AskFlow() {
  const location = useLocation();
  const navigate = useNavigate();
  const toast = useToast();
  const { isManager } = useAuth();
  const state = location.state as { prompt?: string; template?: ReportTemplate; model?: AskModel | null } | null;
  const prompt = state?.prompt ?? "";
  const template = state?.template;
  const model = state?.model ?? null;
  const backHome = () => navigate("/", { state: { prompt, template, model } });

  const [phase, setPhase] = useState<Phase>("working");
  const [step, setStep] = useState(0);
  const [notes, setNotes] = useState<Attempt[]>([]);
  const [result, setResult] = useState<QueryResult | null>(null);
  const [failure, setFailure] = useState<GenerationFailure | null>(null);
  const [editing, setEditing] = useState<"period" | "measure" | null>(null);
  const [confirmDate, setConfirmDate] = useState<QueryResult["needs_confirmation"]>(null);
  const [showSql, setShowSql] = useState(false);
  const [rerunning, setRerunning] = useState(false);
  const [saving, setSaving] = useState(false);
  // One request per question, shared if React runs the effect twice (StrictMode in development).
  const request = useRef<{ key: string; promise: Promise<QueryResult> } | null>(null);

  useEffect(() => {
    if (!prompt) return;
    let alive = true;
    setPhase("working");
    setStep(0);
    setNotes([]);
    const key = `${model?.id ?? "builtin"}|${prompt}`;
    if (request.current?.key !== key) {
      request.current = { key, promise: queryApi.generate(prompt, model?.id ?? null) };
    }
    const pending = request.current.promise;

    // Move through the first steps while the server works. An AI model can take a while, so stay on
    // "Understanding your question" until it has answered.
    const timer = window.setInterval(() => setStep((s) => Math.min(s + 1, model ? 0 : CHECK_STEP)), 650);

    (async () => {
      const t0 = Date.now();
      try {
        const res = await pending;
        await sleep(Math.max(0, 2000 - (Date.now() - t0)));
        if (!alive) return;
        window.clearInterval(timer);
        setStep(CHECK_STEP);
        for (const a of res.attempts ?? []) { setNotes((n) => [...n, a]); await sleep(550); }
        setStep(4);
        await sleep(450);
        if (!alive) return;
        setResult(res);
        setConfirmDate(res.needs_confirmation ?? null);
        setPhase("answer");
      } catch (err) {
        window.clearInterval(timer);
        if (!alive) return;
        if (axios.isAxiosError(err) && err.response?.status === 422 && err.response.data?.detail?.reason) {
          const f = err.response.data.detail as GenerationFailure;
          setStep(CHECK_STEP);
          for (const a of f.attempts) { setNotes((n) => [...n, a]); await sleep(550); }
          setFailure(f);
        } else {
          setFailure({ reason: errorMessage(err), attempts: [], last_sql: "", can_edit_sql: false });
        }
        setPhase("failed");
      }
    })();

    return () => { alive = false; window.clearInterval(timer); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [prompt, model?.id]);

  if (!prompt) return <Navigate to="/" replace />;

  async function rerun(change: Partial<QueryParams>, message: string) {
    if (!result) return;
    setRerunning(true);
    setEditing(null);
    try {
      const res = await queryApi.run({ ...result.params, ...change });
      setResult(res);
      toast(message);
    } catch (err) {
      toast(errorMessage(err));
    } finally {
      setRerunning(false);
    }
  }

  async function buildReport() {
    if (!result) return;
    setSaving(true);
    try {
      const report = await reportsApi.create(result.title, prompt, defaultConfig(result.params, template?.layout));
      navigate(`/reports/${report.id}/edit`);
    } catch (err) {
      toast(errorMessage(err));
      setSaving(false);
    }
  }

  // ---------- Working ----------
  if (phase === "working") {
    return (
      <div className="page narrow">
        <div className="stack">
          <div className="muted small">Working on</div>
          <div className="question">{prompt}</div>
          <ol className="steps card" aria-live="polite">
            {STEPS.map((label, i) => {
              const state = i < step ? "done" : i === step ? "active" : "pending";
              return (
                <li key={label} className={`step ${state}`}>
                  <div className="step-line">
                    {state === "done" && <Icon name="check" size={20} className="ok" />}
                    {state === "active" && <span className="spinner" aria-hidden="true" />}
                    {state === "pending" && <Icon name="circle" size={20} className="faint" />}
                    <span>{i === 0 && model ? `Understanding your question with ${model.name}` : label}</span>
                  </div>
                  {/* The first note is about understanding the question; the rest are about the query. */}
                  {(i === 0 ? notes.slice(0, 1) : i === CHECK_STEP ? notes.slice(1) : []).map((n, k) => (
                    <div key={k} className={"note " + (n.ok ? "note-ok" : "note-bad")}>{n.message}</div>
                  ))}
                </li>
              );
            })}
          </ol>
          <button className="btn btn-ghost self-start" onClick={backHome}>Cancel</button>
        </div>
      </div>
    );
  }

  // ---------- Failed ----------
  if (phase === "failed" && failure) {
    const lastError = [...failure.attempts].reverse().find((a) => !a.ok)?.message;
    return (
      <div className="page narrow">
        <div className="stack">
          <h1 className="h1">This question can't be answered yet</h1>
          <p className="muted">{failure.reason}</p>
          {failure.last_sql && (
            <div className="card stack-sm">
              <div className="strong">Last attempt</div>
              <pre className="code">{failure.last_sql}</pre>
              {lastError && <div className="note note-bad">{lastError}</div>}
            </div>
          )}
          <div className="row-wrap">
            <button className="btn btn-primary btn-lg" onClick={backHome}>Rephrase the question</button>
            <button className="btn btn-ghost btn-lg" onClick={() => toast("Sent to the analytics team with your question and the failed SQL")}>Send to an analyst</button>
            {isManager && (
              <button className="btn btn-ghost btn-lg" onClick={() => toast("The SQL editor arrives in phase 2")}>Edit the SQL myself</button>
            )}
          </div>
        </div>
      </div>
    );
  }

  if (!result) return null;

  // ---------- Answer review ----------
  const p = result.params;
  return (
    <div className="page">
      <div className="stack-lg" style={{ maxWidth: 1040 }}>
        <div className="stack-sm">
          <div className="muted small">You asked</div>
          <div className="question">{prompt}</div>
        </div>

        <section className="card stack" aria-labelledby="und-h">
          <div className="row-between">
            <h2 id="und-h" className="h2">Here's how I understood it</h2>
            <span className="muted small">Click a highlighted item to change it</span>
          </div>
          <div className="chip-row">
            <button className={"chip chip-edit" + (editing === "period" ? " open" : "")} aria-expanded={editing === "period"}
              onClick={() => setEditing(editing === "period" ? null : "period")}>
              <span className="muted">Period</span> <b>{result.period_label}</b> <Icon name="down" size={14} />
            </button>
            <button className={"chip chip-edit" + (editing === "measure" ? " open" : "")} aria-expanded={editing === "measure"}
              onClick={() => setEditing(editing === "measure" ? null : "measure")}>
              <span className="muted">Measure</span> <b>{result.measure_label}</b> <Icon name="down" size={14} />
            </button>
            <span className="chip"><span className="muted">Split by</span> <b>Region and month</b></span>
            <span className="chip"><span className="muted">Also</span> <b>Top 5 products</b></span>
            <span className="chip"><span className="muted">Date column</span> <b>{p.date_col}</b></span>
            <span className="chip"><span className="muted">From</span> <b>{result.source}</b></span>
            <span className="chip"><span className="muted">Read by</span> <b>{result.model ?? "Built-in engine"}</b></span>
            {template && <span className="chip"><span className="muted">Template</span> <b>{template.name}</b></span>}
          </div>

          {editing === "period" && (
            <div className="option-row">
              <span className="muted small">Which period?</span>
              {PERIOD_OPTIONS.map((o) => (
                <button key={o.id} className={"seg" + (p.period === o.id ? " on" : "")}
                  onClick={() => rerun({ period: o.id as PeriodId }, `Re-ran the query for ${o.label}`)}>{o.label}</button>
              ))}
            </div>
          )}
          {editing === "measure" && (
            <div className="option-row">
              <span className="muted small">Which revenue?</span>
              {MEASURE_OPTIONS.map((o) => (
                <button key={o.id} className={"seg" + (p.measure === o.id ? " on" : "")}
                  onClick={() => rerun({ measure: o.id as MeasureId }, `Re-ran the query using ${o.label.toLowerCase()}`)}>
                  {o.label}, {o.hint}
                </button>
              ))}
            </div>
          )}

          {confirmDate && (
            <div className="alert alert-warn row-between">
              <div className="grow" style={{ flexBasis: 320 }}>{confirmDate.message}</div>
              <div className="row-wrap">
              {confirmDate.options.map((c: DateCol) => (
                <button key={c} className="btn btn-ghost" onClick={() => {
                  setConfirmDate(null);
                  if (c !== p.date_col) rerun({ date_col: c }, `Re-ran the query using ${c}`);
                }}>{c === p.date_col ? `Keep ${c}` : `Use ${c}`}</button>
              ))}
              </div>
            </div>
          )}

          {result.attempts?.[0] && !result.attempts[0].ok && (
            <div className="alert alert-warn small" role="status">{result.attempts[0].message}</div>
          )}
          <p>{result.explanation}</p>
          <div>
            <button className="link-btn" aria-expanded={showSql} onClick={() => setShowSql((s) => !s)}>
              {showSql ? "Hide the SQL" : "Show the SQL"}
            </button>
            {showSql && <pre className="code">{result.sql}</pre>}
          </div>
        </section>

        <section className="card stack-sm" aria-labelledby="res-h" aria-busy={rerunning}>
          <div className="row-between">
            <h2 id="res-h" className="h2">The numbers</h2>
            <span className="muted small">{rerunning ? "Re-running…" : `${result.row_count} rows in ${result.elapsed_ms} ms`}</span>
          </div>
          <DataTable result={result} fmt="short" />
        </section>

        <div className="row-wrap">
          <button className="btn btn-primary btn-lg" onClick={buildReport} disabled={saving || rerunning}>
            {saving ? "Creating report…" : "Looks right, build the report"}
          </button>
          <button className="btn btn-ghost btn-lg" onClick={backHome}>Change the question</button>
        </div>
      </div>
    </div>
  );
}
