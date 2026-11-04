import { useEffect, useRef, useState } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import { errorMessage } from "../api/client";
import { assistantApi } from "../api/endpoints";
import { type DashboardParameters, isDashboard } from "../api/types";
import Icon from "../components/Icon";
import { useToast } from "../components/Toast";

export interface BuildRequest {
  source: { id: number | null; name: string };
  model: { id: number; name: string };
  prompt: string;
  parameters: DashboardParameters;
}

/** Builds a dashboard with the AI model, then opens it for arranging and publishing. */
export default function BuildDashboard() {
  const location = useLocation();
  const navigate = useNavigate();
  const toast = useToast();
  const req = location.state as BuildRequest | null;
  const [step, setStep] = useState(0);
  const [error, setError] = useState("");
  const started = useRef(false); // StrictMode runs effects twice in development; build once

  const steps = req ? [
    `Reading the tables in ${req.source.name}`,
    `Planning the charts with ${req.model.name}`,
    "Writing the SQL and checking it only reads data",
    "Running each query and fixing any that fail",
  ] : [];

  useEffect(() => {
    if (!req || started.current) return;
    started.current = true;
    const timer = window.setInterval(() => setStep((s) => Math.min(s + 1, 3)), 4000);
    assistantApi.dashboard({ source_id: req.source.id, model_id: req.model.id, prompt: req.prompt, parameters: req.parameters })
      .then((res) => {
        toast(`Built "${res.report.title}" with ${isDashboard(res.report.config) ? res.report.config.widgets.length : 0} charts. Arrange them, then publish.`);
        navigate(`/reports/${res.report.id}/edit`, { replace: true, state: { failed: res.failed } });
      })
      .catch((err) => setError(errorMessage(err)))
      .finally(() => window.clearInterval(timer));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (!req) return <Navigate to="/" replace />;

  const back = () => navigate("/", { state: { prompt: req.prompt, mode: "build" } });

  return (
    <div className="page narrow">
      <div className="stack">
        <div className="muted small">Building a dashboard</div>
        <div className="question">{req.prompt}</div>
        {error ? (
          <>
            <div className="alert alert-error">{error}</div>
            <div className="row-wrap">
              <button className="btn btn-primary" onClick={back}>Change the request</button>
              <button className="btn btn-ghost" onClick={() => navigate("/chat", { state: { source: req.source.id === null ? "builtin" : String(req.source.id), model: String(req.model.id), question: req.prompt } })}>
                Ask it in chat instead
              </button>
            </div>
          </>
        ) : (
          <>
            <ol className="steps card" aria-live="polite">
              {steps.map((label, i) => {
                const state = i < step ? "done" : i === step ? "active" : "pending";
                return (
                  <li key={label} className={`step ${state}`}>
                    <div className="step-line">
                      {state === "done" && <Icon name="check" size={20} className="ok" />}
                      {state === "active" && <span className="spinner" aria-hidden="true" />}
                      {state === "pending" && <Icon name="circle" size={20} className="faint" />}
                      <span>{label}</span>
                    </div>
                  </li>
                );
              })}
            </ol>
            <p className="muted small">This usually takes 20 to 60 seconds, depending on the model.</p>
            <button className="btn btn-ghost self-start" onClick={back}>Cancel</button>
          </>
        )}
      </div>
    </div>
  );
}
