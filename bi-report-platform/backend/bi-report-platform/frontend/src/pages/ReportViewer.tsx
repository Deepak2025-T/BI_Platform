import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { errorMessage } from "../api/client";
import { reportToolsApi } from "../api/reportTools";
import { type Snapshot, scheduleApi } from "../api/schedule";
import { type QueryParams, type Report, type ReportConfig, isDashboard } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import CategoryBadge from "../components/CategoryBadge";
import Dashboard from "../components/Dashboard";
import FullscreenButton from "../components/FullscreenButton";
import RefreshSchedule from "../components/RefreshSchedule";
import ReportBody from "../components/ReportBody";
import { useToast } from "../components/Toast";
import { shortDate } from "../lib/format";
import { ALL_REGIONS, PERIOD_OPTIONS } from "../lib/report";
import { useQueryResult, useReport } from "../lib/useReport";

export default function ReportViewer() {
  const id = Number(useParams().id);
  const toast = useToast();
  const { user, isManager } = useAuth();
  const { report, error } = useReport(id);
  const [params, setParams] = useState<QueryParams>();
  const [schedOpen, setSchedOpen] = useState(false);
  const [schedule, setSchedule] = useState<Report | null>(null);
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [duplicating, setDuplicating] = useState(false);
  const navigate = useNavigate();

  async function duplicate() {
    setDuplicating(true);
    try {
      const copy = await reportToolsApi.duplicate(id);
      toast(`Made "${copy.title}", your own draft to change.`);
      navigate(`/reports/${copy.id}/edit`);
    } catch (err) {
      toast(errorMessage(err));
      setDuplicating(false);
    }
  }

  // With auto-refresh on and the saved filters, show the latest refresh instead of querying live.
  const saved = report && !isDashboard(report.config) ? report.config.params : undefined;
  const sameAsSaved = (p?: QueryParams | unknown) => !!saved && !!p &&
    (["period", "measure", "date_col", "region"] as const).every((k) => (p as QueryParams)[k] === saved[k]);
  const useSnapshot = !!schedule && schedule.refresh_every !== "off" && sameAsSaved(params)
    && !!snapshot?.data.result && sameAsSaved(snapshot.data.params);
  const live = useQueryResult(useSnapshot ? undefined : params);
  const result = useSnapshot ? snapshot!.data.result! : live.result;
  const { loading, error: qError } = live;

  const loadSnapshot = (reportId: number) => scheduleApi.snapshot(reportId).then(setSnapshot).catch(() => setSnapshot(null));
  useEffect(() => {
    if (!report || isDashboard(report.config)) return;
    setParams(report.config.params);
    setSchedule(report);
    if (report.refresh_every !== "off") loadSnapshot(report.id);
  }, [report]);

  async function refreshNow() {
    if (!report) return;
    setRefreshing(true);
    try {
      const res = await scheduleApi.refresh(report.id);
      setSnapshot(res.snapshot);
      setSchedule(res.report);
      if (saved) setParams(saved); // show what was just refreshed
      toast("Refreshed with the latest data");
    } catch (err) {
      toast(errorMessage(err));
    } finally {
      setRefreshing(false);
    }
  }

  if (error) return <div className="page narrow"><div className="alert alert-error">{error}</div></div>;
  const canEdit = !!report && (isManager || report.owner_id === user?.id);
  if (report && isDashboard(report.config)) {
    return <Dashboard key={report.id} report={{ ...report, config: report.config }} editable={false} canEdit={canEdit} />;
  }
  if (!report || !params) return <div className="page">Loading report…</div>;

  return (
    <div className="viewer">
      <header className="viewer-head">
        <div className="row-between">
          <div>
            <div className="row-wrap">
              <h1 className="h1">{report.title}</h1>
              {report.status === "published" && <CategoryBadge category={report.category} />}
            </div>
            <div className="muted small">
              {report.status === "published" ? "Published" : "Draft, only you and managers can see it"}. By {report.owner_name}, updated {shortDate(report.updated_at)}.
            </div>
            {schedule && (
              <RefreshSchedule report={schedule} canEdit={canEdit} refreshedAt={snapshot?.created_at}
                onChange={(r) => { setSchedule(r); if (r.refresh_every !== "off") loadSnapshot(r.id); else setSnapshot(null); }} />
            )}
          </div>
          <div className="row-wrap no-print">
            <button className="btn btn-ghost" onClick={() => window.print()}>Download PDF</button>
            <button className="btn btn-ghost" aria-expanded={schedOpen} onClick={() => setSchedOpen((s) => !s)}>Email it to me</button>
            <button className="btn btn-ghost" onClick={duplicate} disabled={duplicating}
              title="Copy this report into a new draft of your own">{duplicating ? "Duplicating…" : "Duplicate"}</button>
            <FullscreenButton />
            {canEdit && <Link className="btn btn-primary" to={`/reports/${id}/edit`}>Edit report</Link>}
          </div>
        </div>

        <div className="row-wrap no-print">
          <div className="pills" role="group" aria-label="Period">
            {PERIOD_OPTIONS.map((o) => (
              <button key={o.id} className={"pill" + (params.period === o.id ? " on" : "")} aria-pressed={params.period === o.id}
                onClick={() => setParams({ ...params, period: o.id })}>{o.label}</button>
            ))}
          </div>
          <div className="pills" role="group" aria-label="Region">
            {ALL_REGIONS.map((r) => (
              <button key={r} className={"pill" + (params.region === r ? " on" : "")} aria-pressed={params.region === r}
                onClick={() => setParams({ ...params, region: r })}>{r === "All" ? "All regions" : r}</button>
            ))}
          </div>
          <span className="muted small">
            {loading || refreshing ? "Updating…" : useSnapshot
              ? `Showing the auto-refresh from ${new Date(snapshot!.created_at).toLocaleString([], { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" })}. Changing a filter queries live.`
              : "Filters re-run the saved query. No AI is used."}
          </span>
          {schedule && schedule.refresh_every !== "off" && (
            <button className="btn btn-ghost btn-sm" onClick={refreshNow} disabled={refreshing}
              title="Run the saved query now and save the result for everyone">{refreshing ? "Refreshing…" : "Refresh"}</button>
          )}
        </div>

        {schedOpen && (
          <div className="sched no-print">
            <label className="field"><span>How often</span>
              <select><option>Every Monday</option><option>Every day</option><option>First day of the month</option></select>
            </label>
            <label className="field"><span>Time</span><input defaultValue="08:00" style={{ width: 90 }} /></label>
            <label className="field grow"><span>Send to</span><input defaultValue={user?.email} /></label>
            <button className="btn btn-primary" onClick={() => { setSchedOpen(false); toast("Scheduling arrives in phase 3 (Celery). Saved as a request."); }}>Save schedule</button>
          </div>
        )}
      </header>

      <div className="viewer-body">
        {qError && <div className="alert alert-error">{qError}</div>}
        {result ? <ReportBody title={report.title} result={result} config={{ ...(report.config as ReportConfig), params }} /> : <div className="card">Running the saved query…</div>}
      </div>
    </div>
  );
}
