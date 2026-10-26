import { useState } from "react";
import { errorMessage } from "../api/client";
import { scheduleApi } from "../api/schedule";
import type { RefreshEvery, Report } from "../api/types";
import { shortDate } from "../lib/format";
import { Seg } from "./Controls";
import Modal from "./Modal";
import { useToast } from "./Toast";

const OPTIONS: [RefreshEvery, string][] = [
  ["off", "Off"], ["15min", "Every 15 minutes"], ["hourly", "Every hour"], ["6hours", "Every 6 hours"],
  ["daily", "Daily"], ["weekly", "Weekly"],
];
const DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
const KEEP: [number, string][] = [[0, "Only the latest 10 refreshes"], [30, "30 days"], [90, "90 days"], [365, "1 year"]];

/** "Daily at 08:00", "Every hour", ... */
export function scheduleLabel(r: Pick<Report, "refresh_every" | "refresh_at" | "refresh_weekday">): string {
  if (r.refresh_every === "daily") return `Daily at ${r.refresh_at}`;
  if (r.refresh_every === "weekly") return `${DAYS[r.refresh_weekday]}s at ${r.refresh_at}`;
  return OPTIONS.find(([k]) => k === r.refresh_every)?.[1] ?? "Off";
}

interface Props {
  report: Report;
  canEdit: boolean;
  /** Called with the report after its schedule changes or it refreshes. */
  onChange: (r: Report) => void;
  /** When the data on screen was refreshed, if newer than the report says (e.g. after Refresh). */
  refreshedAt?: string | null;
}

/** Shows when the report refreshes, and lets the owner or a manager change it. */
export default function RefreshSchedule({ report, canEdit, onChange, refreshedAt }: Props) {
  const [open, setOpen] = useState(false);
  const on = report.refresh_every !== "off";
  const last = refreshedAt ?? report.last_refreshed_at;

  return (
    <div className="refresh-status row-wrap small">
      <span className={"chip" + (on ? " chip-on" : "")}>
        <span className="muted">Auto-refresh</span> <b>{scheduleLabel(report)}</b>
      </span>
      {on && last && <span className="muted">Last refreshed {shortDate(last)}</span>}
      {on && report.next_refresh_at && <span className="muted">· next {shortDate(report.next_refresh_at)}</span>}
      {on && report.history_days > 0 && <span className="muted">· keeps {KEEP.find(([d]) => d === report.history_days)?.[1] ?? `${report.history_days} days`} of history</span>}
      {on && report.last_refresh_error && <span className="refresh-error">Last refresh had a problem: {report.last_refresh_error}</span>}
      {canEdit && <button className="link-btn no-print" onClick={() => setOpen(true)}>{on ? "Change" : "Set up auto-refresh"}</button>}
      {open && <ScheduleDialog report={report} onClose={() => setOpen(false)} onSaved={(r) => { setOpen(false); onChange(r); }} />}
    </div>
  );
}

function ScheduleDialog({ report, onClose, onSaved }: { report: Report; onClose: () => void; onSaved: (r: Report) => void }) {
  const toast = useToast();
  const [every, setEvery] = useState<RefreshEvery>(report.refresh_every === "off" ? "daily" : report.refresh_every);
  const [at, setAt] = useState(report.refresh_at || "08:00");
  const [weekday, setWeekday] = useState(report.refresh_weekday ?? 0);
  const [keep, setKeep] = useState(report.history_days ?? 30);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function save() {
    setBusy(true);
    setError("");
    try {
      const res = await scheduleApi.set(report.id, { every, at, weekday, history_days: keep });
      toast(every === "off" ? "Auto-refresh turned off. The report reads the database each time it opens."
        : res.error ? `Schedule saved, but the first refresh failed: ${res.error}` : `Auto-refresh: ${scheduleLabel(res.report).toLowerCase()}. Refreshed just now.`);
      onSaved(res.report);
    } catch (err) {
      setError(errorMessage(err));
      setBusy(false);
    }
  }

  return (
    <Modal size="sm" title="Auto-refresh" onClose={onClose} onSubmit={save} error={error}
      footer={<><button type="button" className="btn btn-ghost" onClick={onClose}>Cancel</button>
        <button type="submit" className="btn btn-primary" disabled={busy}>{busy ? "Saving…" : "Save"}</button></>}>
      <div className="stack">
        <p className="muted small">
          On a schedule, the report runs its saved queries against the database and keeps the results, so everyone
          sees the same, up-to-date numbers and it opens quickly. No AI is used. Anyone can still press Refresh to get the latest data now.
        </p>
        <fieldset className="group">
          <legend>Refresh</legend>
          <div className="seg-row wide">
            {OPTIONS.map(([k, l]) => <Seg key={k} on={every === k} onClick={() => setEvery(k)}>{l}</Seg>)}
          </div>
        </fieldset>
        {(every === "daily" || every === "weekly") && (
          <div className="form-grid">
            {every === "weekly" && (
              <label className="field">Day
                <select value={weekday} onChange={(e) => setWeekday(Number(e.target.value))}>
                  {DAYS.map((d, i) => <option key={d} value={i}>{d}</option>)}
                </select>
              </label>
            )}
            <label className="field">Time (server time)
              <input type="time" value={at} required onChange={(e) => setAt(e.target.value)} />
            </label>
          </div>
        )}
        {every === "off" ? <p className="muted small">Without a schedule, the report reads the database each time someone opens it.</p> : (
          <label className="field">Keep history for
            <select value={keep} onChange={(e) => setKeep(Number(e.target.value))}>
              {KEEP.map(([d, l]) => <option key={d} value={d}>{l}</option>)}
            </select>
            <span className="hint">Dashboards use it for changes since an earlier refresh, trends on each chart, and what
              changed in tables. Older history is thinned to one refresh per hour after a day, and one per day after a week.</span>
          </label>
        )}
      </div>
    </Modal>
  );
}
