import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { errorMessage } from "../api/client";
import { assistantApi, templatesApi } from "../api/endpoints";
import type { DataSourceInfo, ReportTemplate } from "../api/types";
import Modal from "./Modal";
import { useToast } from "./Toast";

interface Props {
  template: ReportTemplate;
  onClose: () => void;
}

/** Builds a draft dashboard from a dashboard template on a connection of the right type. */
export default function BuildFromTemplate({ template, onClose }: Props) {
  const navigate = useNavigate();
  const toast = useToast();
  const [sources, setSources] = useState<DataSourceInfo[] | null>(null);
  const [sourceId, setSourceId] = useState<number | null>(null);
  const [building, setBuilding] = useState(false);
  const [error, setError] = useState("");
  const wanted = template.layout.source_type;
  const charts = (template.layout.widgets ?? []).filter((w) => w.kind !== "text");

  useEffect(() => {
    assistantApi.sources()
      .then((list) => {
        const fit = list.filter((s) => s.id !== null && (!wanted || s.db_type === wanted));
        setSources(fit);
        setSourceId(fit[0]?.id ?? null);
      })
      .catch((e) => { setError(errorMessage(e)); setSources([]); });
  }, [wanted]);

  async function build() {
    if (sourceId === null) return;
    setBuilding(true);
    setError("");
    try {
      const { report, skipped } = await templatesApi.build(template.id, sourceId);
      toast(skipped.length
        ? `Built with ${charts.length - skipped.length} of ${charts.length} charts. Left out: ${skipped.map((s) => s.title).join(", ")}.`
        : `Built "${report.title}" with ${charts.length} charts.`);
      navigate(`/reports/${report.id}/edit`, { state: skipped.length ? { failed: skipped.map((s) => ({ title: s.title, error: s.reason })) } : null });
    } catch (err) {
      setError(errorMessage(err));
      setBuilding(false);
    }
  }

  const typeName = wanted === "openpages" ? "IBM OpenPages" : "database";
  return (
    <Modal title={`Build "${template.name}"`} onClose={onClose} onSubmit={build} error={error} size="sm"
      footer={
        <>
          <span className="grow" />
          <button type="button" className="btn btn-ghost" onClick={onClose}>Cancel</button>
          <button type="submit" className="btn btn-primary" disabled={sourceId === null || building}>
            {building ? "Running the charts…" : "Build dashboard"}
          </button>
        </>
      }>
      <div className="stack">
        <p className="muted small">{template.description} {charts.length} ready-made charts; no AI model is used. You get a
          draft dashboard to change, filter and publish.</p>
        {sources === null ? <p className="muted">Finding connections…</p> : sources.length === 0 ? (
          <div className="alert alert-warn small">
            No {typeName} connection with shared {wanted === "openpages" ? "object types" : "tables"} yet. A manager can add one on
            the Connections page and choose its {wanted === "openpages" ? "object types" : "tables"}.
          </div>
        ) : (
          <label className="field">{wanted === "openpages" ? "OpenPages connection" : "Connection"}
            <select data-autofocus value={sourceId ?? ""} onChange={(e) => setSourceId(Number(e.target.value))}>
              {sources.map((s) => <option key={s.id} value={s.id!}>{s.name}</option>)}
            </select>
          </label>
        )}
        {wanted === "openpages" && (
          <p className="hint">Charts need their object types shared on the connection (for example SOXControl, SOXIssue, Finding,
            AuditProgram). Charts that can't run are left out, and you're told which.</p>
        )}
      </div>
    </Modal>
  );
}
