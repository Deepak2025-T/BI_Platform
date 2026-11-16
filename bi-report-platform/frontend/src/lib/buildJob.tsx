import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { errorMessage } from "../api/client";
import { assistantApi } from "../api/endpoints";
import { isDashboard, type DashboardParameters } from "../api/types";
import { useToast } from "../components/Toast";

export interface BuildRequest {
  source: { id: number | null; name: string };
  model: { id: number; name: string };
  prompt: string;
  parameters: DashboardParameters;
  /** The OpenPages object model to build against, or null for every shared object type. */
  dataModel?: string | null;
}

export interface BuildResult {
  reportId: number;
  title: string;
  charts: number;
  failed: { title: string; error: string }[];
}

export interface BuildJob {
  /** Tells one run from the next, so a replaced build's answer is dropped rather than shown. */
  id: number;
  request: BuildRequest;
  /** performance.now() when the call went out, for the elapsed time and the estimate. */
  startedAt: number;
  endedAt?: number;
  result?: BuildResult;
  error?: string;
}

/**
 * The stages a build goes through. There is one HTTP call behind all of them, so these are what
 * the server is doing rather than something it reports back; the share of the wait each one tends
 * to take is what moves the label on.
 */
export const BUILD_STAGES = [
  { upto: 0.12, label: "Reading the tables" },
  { upto: 0.55, label: "Planning the charts" },
  { upto: 0.80, label: "Writing the SQL and checking it only reads data" },
  { upto: 1.00, label: "Running each query and fixing any that fail" },
];

/**
 * How long a build usually takes, in seconds. It is only the shape of the estimate: a model twice
 * as slow still gets a bar that keeps moving, because the curve below approaches its ceiling
 * rather than arriving at it.
 */
const TYPICAL_SECONDS = 45;

/**
 * A share of the way through, from the time elapsed.
 *
 * The server sends one answer at the end and nothing in between, so there is no true percentage
 * to show. This is an estimate and is labelled as one everywhere it appears: it eases towards 95%
 * and stops, so a slow model reads as "nearly there, still working" rather than as a bar that
 * filled up and then sat at 100% for a minute.
 */
export function estimatedShare(elapsedSeconds: number): number {
  return Math.min(0.95, 1 - Math.exp(-elapsedSeconds / TYPICAL_SECONDS));
}

export const stageFor = (share: number) =>
  (BUILD_STAGES.find((s) => share <= s.upto) ?? BUILD_STAGES[BUILD_STAGES.length - 1]).label;

interface Value {
  job: BuildJob | null;
  /** Seconds since the build started, ticking while it runs. */
  elapsed: number;
  start: (request: BuildRequest) => void;
  /** Takes a finished or failed job off the screen. */
  clear: () => void;
}

const Ctx = createContext<Value>({ job: null, elapsed: 0, start: () => {}, clear: () => {} });

export const useBuildJob = () => useContext(Ctx);

/**
 * The dashboard being built, held above the pages.
 *
 * A build is one long call to an AI model - half a minute on a hosted model, several on a local
 * one - and it used to live inside the page that started it, so leaving that page threw the work
 * away. Holding it here means the person can go and read something else, or start a different
 * piece of work, and come back to a finished report. Only one build runs at a time, which is also
 * what the AI model behind it can sensibly do.
 */
export function BuildJobProvider({ children }: { children: ReactNode }) {
  const navigate = useNavigate();
  const location = useLocation();
  const toast = useToast();
  const [job, setJob] = useState<BuildJob | null>(null);
  const [elapsed, setElapsed] = useState(0);
  // Only one build runs at a time; starting another replaces it. The number says which run is
  // the current one, so the call that was replaced cannot hand its report to the one that
  // replaced it when it finally answers.
  const runs = useRef(0);
  // Where the reader is when the answer lands, which decides whether to open the report for them
  // or just let them know it is ready. Read through a ref, or the callback would use the page
  // they happened to be on when the build started.
  const here = useRef(location.pathname);
  here.current = location.pathname;
  const running = !!job && !job.result && !job.error;

  useEffect(() => {
    if (!running || !job) return;
    const tick = () => setElapsed((performance.now() - job.startedAt) / 1000);
    tick();
    const timer = window.setInterval(tick, 500);
    return () => window.clearInterval(timer);
  }, [running, job]);

  const start = useCallback((request: BuildRequest) => {
    const id = ++runs.current;
    setJob({ id, request, startedAt: performance.now() });
    setElapsed(0);
    assistantApi.dashboard({
      source_id: request.source.id, model_id: request.model.id, prompt: request.prompt,
      parameters: request.parameters, data_model: request.dataModel ?? null,
    }).then((res) => {
      const result: BuildResult = {
        reportId: res.report.id,
        title: res.report.title,
        charts: isDashboard(res.report.config) ? res.report.config.widgets.length : 0,
        failed: res.failed,
      };
      if (runs.current !== id) return;   // replaced by a later build; this answer is stale
      setJob((j) => (j && j.id === id ? { ...j, endedAt: performance.now(), result } : j));
      // Still watching it build: go straight into the report. Gone off to do something else:
      // say it is ready and leave the choice of when to open it to them.
      if (here.current === "/build") {
        setJob(null);
        toast(`Built "${result.title}" with ${result.charts} charts. Arrange them, then publish.`);
        navigate(`/reports/${result.reportId}/edit`, { replace: true, state: { failed: result.failed } });
      } else {
        toast(`"${result.title}" is ready, with ${result.charts} charts.`,
              { label: "Open", onClick: () => navigate(`/reports/${result.reportId}/edit`, { state: { failed: result.failed } }) });
      }
    }).catch((err) => {
      if (runs.current !== id) return;
      setJob((j) => (j && j.id === id ? { ...j, endedAt: performance.now(), error: errorMessage(err) } : j));
    });
  }, [navigate, toast]);

  const clear = useCallback(() => { runs.current += 1; setJob(null); }, []);

  return <Ctx.Provider value={{ job, elapsed, start, clear }}>{children}</Ctx.Provider>;
}
