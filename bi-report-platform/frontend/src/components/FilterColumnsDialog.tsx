import { useEffect, useState } from "react";
import { errorMessage } from "../api/client";
import { type FilterColumns, reportToolsApi } from "../api/reportTools";
import type { DashboardFilter, Widget } from "../api/types";
import { columnLabel } from "../lib/format";
import Modal from "./Modal";

interface Props {
  reportId: number;
  widgets: Widget[];
  /** A filter to change; leave out to add a new one. */
  filter?: DashboardFilter;
  onClose: () => void;
  onSaved: (f: DashboardFilter) => void;
}

const key = (table: string, column: string) => `${table}|${column}`;
const isDateType = (t: string) => /date|time/i.test(t);

/** A dashboard filter whose column you choose for each chart, without AI. */
export default function FilterColumnsDialog({ reportId, widgets, filter, onClose, onSaved }: Props) {
  const [label, setLabel] = useState(filter?.label ?? "");
  const [kind, setKind] = useState<DashboardFilter["kind"]>(filter?.kind ?? "category");
  const [columns, setColumns] = useState<FilterColumns | null>(null);
  const [picks, setPicks] = useState<Record<string, string>>(() => Object.fromEntries(
    Object.entries(filter?.columns ?? {}).map(([wid, c]) => [wid, key(c.table, c.column)])));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    reportToolsApi.filterColumns(reportId, widgets).then(setColumns).catch((e) => { setError(errorMessage(e)); setColumns({}); });
  }, [reportId, widgets]);

  // Choosing a column for one chart fills it in for every other chart that reads the same table.
  function pick(widgetId: string, value: string) {
    setPicks((current) => {
      const next = { ...current, [widgetId]: value };
      if (value) {
        const [table] = value.split("|");
        for (const w of widgets) {
          if (!next[w.id] && columns?.[w.id]?.some((t) => t.table === table)) next[w.id] = value;
        }
      }
      return next;
    });
  }

  async function save() {
    if (!label.trim()) return;
    setBusy(true);
    setError("");
    const chosen = Object.fromEntries(Object.entries(picks).filter(([, v]) => v)
      .map(([wid, v]) => { const [table, column] = v.split("|"); return [wid, { table, column }]; }));
    try {
      const f = await reportToolsApi.manualFilter(reportId, { label: label.trim(), kind, widgets, columns: chosen, id: filter?.id });
      onSaved(f);
    } catch (err) {
      setError(errorMessage(err));
      setBusy(false);
    }
  }

  const chosenCount = Object.values(picks).filter(Boolean).length;

  return (
    <Modal title={filter ? `Edit filter: ${filter.label}` : "Add a custom filter"} onClose={onClose} onSubmit={save} error={error}
      footer={
        <>
          <span className="muted small grow">Filters {chosenCount} of {widgets.length} charts</span>
          <button type="button" className="btn btn-ghost" onClick={onClose}>Cancel</button>
          <button type="submit" className="btn btn-primary" disabled={busy || !label.trim() || chosenCount === 0}>
            {busy ? "Saving…" : "Save filter"}
          </button>
        </>
      }>
      <div className="stack">
        <p className="muted small">Choose the column each chart filters on. Charts set to "Not filtered" ignore this filter.
          Category filters offer the values found in the chosen columns.</p>
        <div className="form-grid">
          <label className="field">Filter name
            <input data-autofocus value={label} maxLength={60} placeholder="e.g. Region, Order date" onChange={(e) => setLabel(e.target.value)} />
          </label>
          <label className="field">Type
            <select value={kind} onChange={(e) => setKind(e.target.value as DashboardFilter["kind"])}>
              <option value="category">Category (pick values)</option>
              <option value="date">Date range</option>
            </select>
          </label>
        </div>

        {columns === null ? <p className="muted">Reading the charts' tables…</p> : (
          <div className="filter-picks">
            {widgets.map((w) => {
              const tables = columns[w.id] ?? [];
              return (
                <label key={w.id} className="filter-pick">
                  <span className="strong">{w.title}</span>
                  <select value={picks[w.id] ?? ""} onChange={(e) => pick(w.id, e.target.value)}>
                    <option value="">Not filtered</option>
                    {tables.map((t) => (
                      <optgroup key={t.table} label={t.table}>
                        {t.columns
                          .filter((c) => kind !== "date" || isDateType(c.type) || picks[w.id] === key(t.table, c.name))
                          .map((c) => <option key={c.name} value={key(t.table, c.name)}>{columnLabel(c.name)} ({c.type.toLowerCase()})</option>)}
                      </optgroup>
                    ))}
                  </select>
                  {tables.length === 0 && <span className="muted small">This chart's query reads no tables that can be filtered.</span>}
                </label>
              );
            })}
          </div>
        )}
      </div>
    </Modal>
  );
}
