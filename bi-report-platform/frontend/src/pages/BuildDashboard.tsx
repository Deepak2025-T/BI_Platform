import { Navigate, useNavigate } from "react-router-dom";
import { ProgressRing, elapsedText } from "../components/BuildProgress";
import Icon from "../components/Icon";
import { BUILD_STAGES, estimatedShare, stageFor, useBuildJob } from "../lib/buildJob";

export type { BuildRequest } from "../lib/buildJob";

/**
 * The dashboard being built, at full size.
 *
 * The work itself lives above the routes (lib/buildJob), not here, so this page only watches it.
 * That is what lets the person walk away mid-build: leaving this page takes the progress with
 * them into the corner of wherever they go, and the report is waiting when it lands.
 */
export default function BuildDashboard() {
  const { job, elapsed, clear } = useBuildJob();
  const navigate = useNavigate();

  // Nothing building and nothing to report: there is no page to show.
  if (!job) return <Navigate to="/" replace />;

  const { request: req } = job;
  const back = () => { clear(); navigate("/", { state: { prompt: req.prompt, mode: "build" } }); };

  if (job.error) {
    return (
      <div className="page narrow">
        <div className="stack">
          <div className="muted small">Building a report</div>
          <div className="question">{req.prompt}</div>
          <div className="alert alert-error">{job.error}</div>
          <div className="row-wrap">
            <button className="btn btn-primary" onClick={back}>Change the request</button>
            <button className="btn btn-ghost" onClick={() => {
              clear();
              navigate("/chat", { state: { source: req.source.id === null ? "builtin" : String(req.source.id),
                                           model: String(req.model.id), question: req.prompt,
                                           dataModel: req.dataModel ?? null } });
            }}>Ask it in chat instead</button>
          </div>
        </div>
      </div>
    );
  }

  const share = estimatedShare(elapsed);
  const stage = stageFor(share);
  const source = req.dataModel
    ? `the ${req.dataModel.split("/").pop()?.toUpperCase()} model on ${req.source.name}`
    : req.source.name;

  return (
    <div className="page narrow">
      <div className="stack">
        <div className="muted small">Building a report</div>
        <div className="question">{req.prompt}</div>

        <div className="card build-card">
          <div className="build-head">
            <ProgressRing share={share} size={76} />
            <div className="grow">
              <h2 className="h2">{stage}…</h2>
              <p className="muted small">
                {req.model.name} is reading {source}. {elapsedText(elapsed)} so far — the share shown is an
                estimate from how long builds usually take, not a count of the work done.
              </p>
            </div>
          </div>

          <ol className="steps" aria-live="polite">
            {BUILD_STAGES.map((s, i) => {
              const reached = share > s.upto;
              const current = s.label === stage;
              const state = reached ? "done" : current ? "active" : "pending";
              return (
                <li key={s.label} className={`step ${state}`}>
                  <div className="step-line">
                    {state === "done" && <Icon name="check" size={20} className="ok" />}
                    {state === "active" && <span className="spinner" aria-hidden="true" />}
                    {state === "pending" && <Icon name="circle" size={20} className="faint" />}
                    <span>{i + 1}. {s.label}</span>
                  </div>
                </li>
              );
            })}
          </ol>
        </div>

        <div className="alert alert-info small alert-icon">
          <Icon name="info" size={16} />
          <span>
            <b>You can carry on working.</b> This keeps running if you go to another page — the progress
            follows you into the corner, and the report opens from there the moment it is ready. Closing the
            browser tab is the one thing that stops it.
          </span>
        </div>

        <div className="row-wrap">
          <button className="btn btn-ghost" onClick={() => navigate("/reports")}>Go to Reports while this runs</button>
          <button className="btn btn-ghost" onClick={back}>Cancel</button>
        </div>
      </div>
    </div>
  );
}
