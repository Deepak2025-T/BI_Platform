import { useEffect, useMemo, useState } from "react";
import { errorMessage } from "../api/client";
import { assistantApi, reportsApi } from "../api/endpoints";
import type { Report, Widget } from "../api/types";
import { isDashboard } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import Modal from "./Modal";
import { shortDate } from "../lib/format";

interface Props {
  /** The database the charts read. Only reports on the same one can take them. */
  sourceId: number | null;
  sourceName: string;
  widgets: Widget[];
  /** The title to offer when a new report is made. */
  defaultTitle: string;
  /** What the question was, kept on a new report. */
  prompt?: string;
  onClose: () => void;
  /** Called once the charts are somewhere: `created` says whether a report was started for them. */
  onDone: (report: Report, created: boolean) => void;
}

/**
 * Puts charts on a report: one that already exists, or a new one.
 *
 * Only dashboards on the same database are offered. A report's filters, refresh and export all
 * assume one connection, so a chart from somewhere else would quietly read the wrong thing — the
 * server refuses it too, and this keeps it off the list in the first place.
 */
export default function AddToReport({ sourceId, sourceName, widgets, defaultTitle, prompt, onClose, onDone }: Props) {
  const { user, isManager } = useAuth();
  const [reports, setReports] = useState<Report[] | null>(null);
  const [choice, setChoice] = useState<string>("new");
  const [title, setTitle] = useState(defaultTitle);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    reportsApi.list().then(setReports).catch(() => setReports([]));
  }, []);

  const mine = useMemo(() => (reports ?? []).filter((r) =>
    isDashboard(r.config) && (isManager || r.owner_id === user?.id)),
    [reports, isManager, user?.id]);
  const fits = useMemo(() => mine.filter((r) => isDashboard(r.config) && r.config.source_id === sourceId), [mine, sourceId]);
  // Dashboards on another database. They can't take these charts, but they are shown anyway, greyed
  // out and named with the database they read: someone looking at an empty list of 70 reports they
  // know they have assumes the picker is broken, rather than that none of them reads this database.
  const elsewhere = useMemo(() => mine.filter((r) => !fits.includes(r)), [mine, fits]);

  async function go() {
    setBusy(true);
    setError("");
    try {
      if (choice === "new") {
        const report = await assistantApi.save({ source_id: sourceId, title: title.trim() || defaultTitle,
                                                 prompt: prompt ?? "", widgets });
        onDone(report, true);
      } else {
        const report = await assistantApi.addWidgets(Number(choice), { source_id: sourceId, widgets });
        onDone(report, false);
      }
    } catch (err) {
      setError(errorMessage(err));
      setBusy(false);
    }
  }

  const count = widgets.length;
  const what = `${count} chart${count === 1 ? "" : "s"}`;

  return (
    <Modal size="sm" title={`Add ${what} to a report`} onClose={onClose} onSubmit={go} error={error}
      footer={
        <>
          <button type="button" className="btn btn-ghost" onClick={onClose}>Cancel</button>
          <button type="submit" className="btn btn-primary" disabled={busy || (choice === "new" && !title.trim())}>
            {busy ? "Saving…" : choice === "new" ? "Create report" : "Add to this report"}
          </button>
        </>
      }>
      <div className="stack">
        <label className="field">
          Report
          <select value={choice} onChange={(e) => setChoice(e.target.value)} aria-label="Report to add these charts to">
            <option value="new">New report…</option>
            {fits.length > 0 && (
              <optgroup label={`On ${sourceName}`}>
                {fits.map((r) => (
                  <option key={r.id} value={r.id}>
                    {r.title} — {r.status === "published" ? "published" : "draft"}, {shortDate(r.updated_at)}
                  </option>
                ))}
              </optgroup>
            )}
            {elsewhere.length > 0 && (
              <optgroup label="On another database, so they can't take these charts">
                {elsewhere.map((r) => (
                  <option key={r.id} value={r.id} disabled>
                    {r.title} — reads {isDashboard(r.config) ? r.config.source_name || "another database" : ""}
                  </option>
                ))}
              </optgroup>
            )}
          </select>
          {reports !== null && fits.length === 0 && (
            <span className="hint">
              {elsewhere.length === 0
                ? `You have no dashboard yet, so this starts the first one.`
                : `None of your ${elsewhere.length} dashboards reads ${sourceName}, and a report reads one database
                   — its filters, refresh and exports all assume that. This starts the first one on ${sourceName}.`}
            </span>
          )}
        </label>

        {choice === "new" ? (
          <>
            <label className="field">Report title
              <input data-autofocus value={title} maxLength={200} onChange={(e) => setTitle(e.target.value)} />
            </label>
            <p className="muted small">
              {what} saved as a draft dashboard on {sourceName}. Each keeps its own query, so the report shows
              current data every time it opens.
            </p>
          </>
        ) : (
          <p className="muted small">
            {what} added to the end of that report. Nothing already on it changes, and you can arrange and publish
            it afterwards.
          </p>
        )}
      </div>
    </Modal>
  );
}
