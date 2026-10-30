import { useEffect, useMemo, useState } from "react";
import { errorMessage } from "../api/client";
import { connectionsApi } from "../api/endpoints";
import type { DataConnection, SchemaTables } from "../api/types";
import Icon from "./Icon";
import Modal from "./Modal";

interface Props {
  connection: DataConnection;
  onClose: () => void;
  onSaved: (c: DataConnection) => void;
}

const key = (schema: string, table: string) => `${schema}.${table}`;

/** Choose which tables and views users may ask questions about. */
export default function TablePicker({ connection, onClose, onSaved }: Props) {
  const [schemas, setSchemas] = useState<SchemaTables[] | null>(null);
  const [chosen, setChosen] = useState(() => new Set(connection.allowed_tables));
  const [search, setSearch] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    connectionsApi.tables(connection.id).then(setSchemas).catch((e) => { setError(errorMessage(e)); setSchemas([]); });
  }, [connection.id]);

  const shown = useMemo(() => {
    const q = search.trim().toLowerCase();
    return (schemas ?? [])
      .map((s) => ({ ...s, tables: s.tables.filter((t) => !q || t.name.toLowerCase().includes(q)) }))
      .filter((s) => s.tables.length > 0);
  }, [schemas, search]);

  const all = (schemas ?? []).flatMap((s) => s.tables.map((t) => key(s.schema, t.name)));
  // Tables chosen earlier that no longer exist (or the account can't see) are dropped on save.
  const missing = schemas ? connection.allowed_tables.filter((t) => !all.includes(t)) : [];

  const toggle = (k: string) => setChosen((prev) => {
    const next = new Set(prev);
    if (next.has(k)) next.delete(k); else next.add(k);
    return next;
  });
  const setMany = (keys: string[], on: boolean) => setChosen((prev) => {
    const next = new Set(prev);
    keys.forEach((k) => (on ? next.add(k) : next.delete(k)));
    return next;
  });

  async function save() {
    setSaving(true);
    setError("");
    try {
      onSaved(await connectionsApi.update(connection.id, { allowed_tables: [...chosen].filter((k) => all.includes(k)) }));
    } catch (err) {
      setError(errorMessage(err));
      setSaving(false);
    }
  }

  const count = [...chosen].filter((k) => all.includes(k)).length;

  return (
    <Modal title={`${connection.db_type === "openpages" ? "Object types" : "Tables"} in ${connection.name}`} onClose={onClose} onSubmit={save} error={error}
      footer={
        <>
          <span className="muted small grow">{count} of {all.length} chosen</span>
          <button type="button" className="btn btn-ghost" onClick={onClose}>Cancel</button>
          <button type="submit" className="btn btn-primary" disabled={saving || schemas === null}>{saving ? "Saving…" : "Save tables"}</button>
        </>
      }>
      <div className="stack">
        <p className="muted small">{connection.db_type === "openpages" && "In OpenPages, tables are object types (SOXRisk, SOXIssue, Finding…). "}Users can only ask questions about the tables you choose here. Leave out tables with
          personal or sensitive data.</p>
        {missing.length > 0 && (
          <div className="alert alert-warn small">
            {missing.length} table{missing.length === 1 ? " was" : "s were"} chosen before but can't be found now
            ({missing.slice(0, 3).join(", ")}{missing.length > 3 ? ", …" : ""}). Saving removes {missing.length === 1 ? "it" : "them"}.
          </div>
        )}
        <div className="row-between">
          <label className="search grow">
            <Icon name="search" size={16} />
            <span className="sr-only">Search tables</span>
            <input type="search" placeholder="Search tables" value={search} onChange={(e) => setSearch(e.target.value)} />
          </label>
          <div className="row-wrap">
            <button type="button" className="btn btn-ghost btn-sm" onClick={() => setMany(shown.flatMap((s) => s.tables.map((t) => key(s.schema, t.name))), true)}>Select shown</button>
            <button type="button" className="btn btn-ghost btn-sm" onClick={() => setChosen(new Set())}>Clear</button>
          </div>
        </div>

        {schemas === null ? <p className="muted">Reading the tables…</p> : shown.length === 0 ? (
          <p className="muted">{search ? "No tables match." : "The account can't see any tables. Check its permissions."}</p>
        ) : (
          <div className="table-picker">
            {shown.map((s) => {
              const keys = s.tables.map((t) => key(s.schema, t.name));
              const on = keys.filter((k) => chosen.has(k)).length;
              return (
                <fieldset key={s.schema} className="tp-schema">
                  <legend className="tp-head">
                    <label className="check">
                      <input type="checkbox" checked={on === keys.length} ref={(el) => { if (el) el.indeterminate = on > 0 && on < keys.length; }}
                        onChange={(e) => setMany(keys, e.target.checked)} />
                      <span className="strong">{s.schema}</span>
                    </label>
                    <span className="muted small">{on} of {keys.length}</span>
                  </legend>
                  <div className="tp-tables">
                    {s.tables.map((t) => (
                      <label key={t.name} className="check tp-table">
                        <input type="checkbox" checked={chosen.has(key(s.schema, t.name))} onChange={() => toggle(key(s.schema, t.name))} />
                        <span className="grow">{t.name}</span>
                        {t.kind === "view" && <span className="tpl-tag">view</span>}
                      </label>
                    ))}
                  </div>
                </fieldset>
              );
            })}
          </div>
        )}
      </div>
    </Modal>
  );
}
