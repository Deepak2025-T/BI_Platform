import { useEffect, useState } from "react";
import { errorMessage } from "../api/client";
import { adminApi, connectionsApi } from "../api/endpoints";
import type { DataConnection } from "../api/types";
import ConnectionForm from "../components/ConnectionForm";
import Icon from "../components/Icon";
import TablePicker from "../components/TablePicker";
import { useToast } from "../components/Toast";
import { DB_TYPE_INFO, STATUS_INFO, connectionAddress } from "../lib/connections";
import { shortDate } from "../lib/format";

type Dialog = { kind: "form"; connection?: DataConnection } | { kind: "tables"; connection: DataConnection } | null;

export default function Connections() {
  const toast = useToast();
  const [connections, setConnections] = useState<DataConnection[] | null>(null);
  const [keyWarning, setKeyWarning] = useState("");
  const [dialog, setDialog] = useState<Dialog>(null);
  const [testing, setTesting] = useState<number | null>(null);

  useEffect(() => {
    connectionsApi.list().then(setConnections).catch((e) => { toast(errorMessage(e)); setConnections([]); });
    adminApi.usage().then((u) => setKeyWarning(u.warnings.find((w) => w.includes("CONNECTIONS_KEY")) ?? "")).catch(() => {});
  }, [toast]);

  const replace = (c: DataConnection) =>
    setConnections((list) => [...(list ?? []).filter((x) => x.id !== c.id), c].sort((a, b) => a.name.localeCompare(b.name)));

  async function test(c: DataConnection) {
    setTesting(c.id);
    try {
      const res = await connectionsApi.test(c.id);
      toast(res.ok ? `${c.name}: ${res.message}` : `${c.name} failed: ${res.message}`);
      // The test result is stored on the connection, so reload it.
      const fresh = (await connectionsApi.list()).find((x) => x.id === c.id);
      if (fresh) replace(fresh);
    } catch (err) {
      toast(errorMessage(err));
    } finally {
      setTesting(null);
    }
  }

  async function remove(c: DataConnection) {
    if (!window.confirm(`Delete the connection "${c.name}"? Its saved password is deleted too.`)) return;
    try {
      await connectionsApi.remove(c.id);
      setConnections((list) => list?.filter((x) => x.id !== c.id) ?? null);
      toast("Connection deleted");
    } catch (err) { toast(errorMessage(err)); }
  }

  function saved(c: DataConnection, isNew: boolean) {
    replace(c);
    setDialog(null);
    toast(isNew ? `${c.name} saved. Test it, then choose which tables users may query.` : "Connection saved");
  }

  return (
    <div className="page">
      <div className="stack" style={{ maxWidth: 1100 }}>
        <div className="row-between">
          <div>
            <h1 className="h1">Database connections</h1>
            <p className="muted small">The databases reports can read from. Users see connection names only, never servers, accounts or passwords.</p>
          </div>
          <button className="btn btn-primary btn-lg" onClick={() => setDialog({ kind: "form" })}><Icon name="plus" />Add connection</button>
        </div>

        {keyWarning && (
          <div className="alert alert-warn">
            <div className="strong">Set CONNECTIONS_KEY before adding connections</div>
            <div>{keyWarning} Generate one in the backend folder with:</div>
            <pre className="code">python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"</pre>
            <div className="small">Add it to backend\.env as CONNECTIONS_KEY=…, restart the backend, and keep a copy somewhere safe.</div>
          </div>
        )}

        {connections === null ? <div className="card">Loading…</div> : connections.length === 0 ? (
          <div className="card empty-state stack">
            <h2 className="h2">No connections yet</h2>
            <p className="muted">Add your first database. Ask its owner for a read-only account first.</p>
            <div className="row-wrap">
              {Object.entries(DB_TYPE_INFO).map(([t, info]) => (
                <span key={t} className="db-chip"><span className="db-badge" style={{ background: info.color }}>{info.short}</span>{info.label}</span>
              ))}
            </div>
            <button className="btn btn-primary self-start" onClick={() => setDialog({ kind: "form" })}><Icon name="plus" />Add connection</button>
          </div>
        ) : (
          <div className="conn-list">
            {connections.map((c) => {
              const info = DB_TYPE_INFO[c.db_type];
              const status = STATUS_INFO[c.status];
              return (
                <article key={c.id} className="card conn-card" aria-label={c.name}>
                  <div className="conn-main">
                    <span className="db-badge lg" style={{ background: info.color }} aria-hidden="true">{info.short}</span>
                    <div className="grow">
                      <div className="row-wrap">
                        <h2 className="h2">{c.name}</h2>
                        <span className={"badge " + status.badge}>{status.label}</span>
                      </div>
                      <div className="muted small">{c.type_label}, {connectionAddress(c)}{c.username && `, as ${c.username}`}</div>
                      <div className="small">
                        {c.allowed_tables.length > 0
                          ? <span>{c.allowed_tables.length} table{c.allowed_tables.length === 1 ? "" : "s"} shared with users</span>
                          : <span className="warn-text">No tables chosen yet, so users can't query this connection</span>}
                        {c.last_tested_at && <span className="muted">, tested {shortDate(c.last_tested_at)}</span>}
                      </div>
                      {c.status === "error" && c.last_error && <div className="note note-bad conn-error">{c.last_error}</div>}
                    </div>
                  </div>
                  <div className="conn-actions">
                    <button className="btn btn-ghost btn-sm" onClick={() => test(c)} disabled={testing === c.id}>{testing === c.id ? "Testing…" : "Test"}</button>
                    <button className="btn btn-ghost btn-sm" onClick={() => setDialog({ kind: "tables", connection: c })}>Choose tables</button>
                    <button className="btn btn-ghost btn-sm" onClick={() => setDialog({ kind: "form", connection: c })}>Edit</button>
                    <button className="icon-btn danger" aria-label={`Delete ${c.name}`} title="Delete" onClick={() => remove(c)}><Icon name="trash" size={16} /></button>
                  </div>
                </article>
              );
            })}
          </div>
        )}
      </div>

      {dialog?.kind === "form" && <ConnectionForm connection={dialog.connection} onClose={() => setDialog(null)} onSaved={saved} />}
      {dialog?.kind === "tables" && (
        <TablePicker connection={dialog.connection} onClose={() => setDialog(null)}
          onSaved={(c) => { replace(c); setDialog(null); toast(`${c.allowed_tables.length} tables shared with users`); }} />
      )}
    </div>
  );
}
