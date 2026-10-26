import { useState } from "react";
import { errorMessage } from "../api/client";
import { connectionsApi } from "../api/endpoints";
import type { ConnectionInput, ConnectionOptions, ConnectionTestResult, DataConnection, DbType } from "../api/types";
import { DB_TYPE_INFO, OPENPAGES_AUTH } from "../lib/connections";
import Modal from "./Modal";

interface Props {
  /** Connection to edit. Leave out to add a new one. */
  connection?: DataConnection;
  onClose: () => void;
  onSaved: (c: DataConnection, isNew: boolean) => void;
}

const EMPTY: ConnectionInput = {
  name: "", db_type: "postgresql", host: "", port: null, database: "", username: "", password: "",
  schemas: [], options: { ssl: false, trust_server_certificate: false },
};

export default function ConnectionForm({ connection, onClose, onSaved }: Props) {
  const [form, setForm] = useState<ConnectionInput>(() => connection
    ? { name: connection.name, db_type: connection.db_type, host: connection.host, port: connection.port,
        database: connection.database, username: connection.username, password: "", schemas: connection.schemas,
        options: connection.options }
    : EMPTY);
  const [schemasText, setSchemasText] = useState(form.schemas.join(", "));
  const [testing, setTesting] = useState(false);
  const [test, setTest] = useState<ConnectionTestResult | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const info = DB_TYPE_INFO[form.db_type];
  const isFile = form.db_type === "sqlite";
  const isOP = form.db_type === "openpages";
  const auth = form.options.auth_type ?? "basic";
  const opt = (patch: Partial<ConnectionOptions>) => set("options", { ...form.options, ...patch });
  const [clientKey, setClientKey] = useState("");
  const set = <K extends keyof ConnectionInput>(k: K, v: ConnectionInput[K]) => {
    setForm((f) => ({ ...f, [k]: v }));
    setTest(null); // the old result no longer applies
  };

  // An empty password field on an existing connection means "keep the saved one".
  const body = (): ConnectionInput => ({
    ...form,
    host: isFile ? "" : form.host,
    port: isFile ? null : form.port,
    username: isFile ? "" : form.username,
    password: connection && !form.password ? null : isFile ? "" : form.password,
    schemas: info.hasSchemas ? schemasText.split(",").map((s) => s.trim()).filter(Boolean) : [],
    database: isOP ? "" : form.database,
    client_key: isOP && auth === "mtls" && clientKey.trim() ? clientKey : null,
  });
  const ready = form.name.trim() && (isOP ? form.host.trim() : form.database.trim() && (isFile || form.host.trim()));
  // What the secret field holds for each OpenPages sign-in type.
  const secretLabel = { basic: "Password", oauth2: "Client secret", mpjwt: "MP-JWT token", iam: "IBM Cloud API key", mtls: "Password (optional)" }[auth];

  async function runTest() {
    setTesting(true);
    setTest(null);
    setError("");
    try {
      const { name: _name, ...draft } = body();
      setTest(await connectionsApi.testDraft({ ...draft, id: connection?.id }));
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setTesting(false);
    }
  }

  async function save() {
    if (!ready) return;
    setSaving(true);
    setError("");
    try {
      const saved = connection ? await connectionsApi.update(connection.id, body()) : await connectionsApi.create(body());
      onSaved(saved, !connection);
    } catch (err) {
      setError(errorMessage(err));
      setSaving(false);
    }
  }

  return (
    <Modal title={connection ? `Edit ${connection.name}` : "Add a database connection"} onClose={onClose} onSubmit={save}
      error={error}
      footer={
        <>
          <button type="button" className="btn btn-ghost" onClick={runTest} disabled={!ready || testing}>
            {testing ? "Testing…" : "Test connection"}
          </button>
          <span className="grow" />
          <button type="button" className="btn btn-ghost" onClick={onClose}>Cancel</button>
          <button type="submit" className="btn btn-primary" disabled={!ready || saving}>
            {saving ? "Saving…" : connection ? "Save changes" : "Save connection"}
          </button>
        </>
      }>
      <div className="stack">
        <fieldset className="group">
          <legend>Database type</legend>
          <div className="db-types">
            {(Object.keys(DB_TYPE_INFO) as DbType[]).map((t) => (
              <button key={t} type="button" className={"db-type" + (form.db_type === t ? " on" : "")} aria-pressed={form.db_type === t}
                onClick={() => { set("db_type", t); set("port", null); }}>
                <span className="db-badge" style={{ background: DB_TYPE_INFO[t].color }}>{DB_TYPE_INFO[t].short}</span>
                {DB_TYPE_INFO[t].label}
              </button>
            ))}
          </div>
        </fieldset>

        <label className="field">Connection name
          <input data-autofocus value={form.name} maxLength={80} required placeholder="e.g. Sales DB, Finance ERP"
            onChange={(e) => set("name", e.target.value)} />
          <span className="hint">Users see only this name, never the server, account or password.</span>
        </label>

        {isOP ? (
          <>
            <label className="field">OpenPages API URL
              <input value={form.host} required placeholder="https://openpages.company.com/grc/api"
                onChange={(e) => set("host", e.target.value)} />
              <span className="hint">The server address or its /grc/api URL. Questions run through the Query Service (GET /grc/api/query).</span>
            </label>
            <label className="field">Sign-in type
              <select value={auth} onChange={(e) => opt({ auth_type: e.target.value as ConnectionOptions["auth_type"] })}>
                {Object.entries(OPENPAGES_AUTH).map(([k, l]) => <option key={k} value={k}>{l}</option>)}
              </select>
            </label>
            {auth === "oauth2" && (
              <div className="form-grid">
                <label className="field">Token URL
                  <input value={form.options.token_url ?? ""} placeholder="https://openpages.company.com/.../token"
                    onChange={(e) => opt({ token_url: e.target.value })} />
                </label>
                <label className="field">Client ID
                  <input value={form.options.client_id ?? ""} autoComplete="off" onChange={(e) => opt({ client_id: e.target.value })} />
                </label>
              </div>
            )}
            {auth === "iam" && (
              <label className="field">IAM token URL (optional)
                <input value={form.options.token_url ?? ""} placeholder="https://iam.cloud.ibm.com/identity/token"
                  onChange={(e) => opt({ token_url: e.target.value })} />
              </label>
            )}
            {(auth === "basic" || auth === "mtls") && (
              <label className="field">Username{auth === "mtls" ? " (optional)" : ""}
                <input value={form.username} autoComplete="off" placeholder="e.g. bi_reader" onChange={(e) => set("username", e.target.value)} />
              </label>
            )}
            <label className="field">{secretLabel}
              {auth === "mpjwt" ? (
                <textarea rows={3} value={form.password ?? ""} autoComplete="off" spellCheck={false}
                  placeholder={connection?.has_password ? "Saved. Leave blank to keep it." : "eyJhbGciOi..."}
                  onChange={(e) => set("password", e.target.value)} />
              ) : (
                <input type="password" value={form.password ?? ""} autoComplete="new-password"
                  placeholder={connection?.has_password ? "Saved. Leave blank to keep it." : ""}
                  onChange={(e) => set("password", e.target.value)} />
              )}
              {auth === "mpjwt" && <span className="hint">Tokens expire. Paste a new one here when it does.</span>}
            </label>
            {auth === "mtls" && (
              <>
                <label className="field">Client certificate (PEM)
                  <textarea rows={4} spellCheck={false} value={form.options.client_cert ?? ""}
                    placeholder="-----BEGIN CERTIFICATE-----" onChange={(e) => opt({ client_cert: e.target.value })} />
                </label>
                <label className="field">Private key (PEM)
                  <textarea rows={4} spellCheck={false} value={clientKey} autoComplete="off"
                    placeholder={form.options.has_client_key ? "Saved. Leave blank to keep it." : "-----BEGIN PRIVATE KEY-----"}
                    onChange={(e) => { setClientKey(e.target.value); setTest(null); }} />
                  <span className="hint">Stored encrypted and never shown again.</span>
                </label>
              </>
            )}
            <label className="check">
              <input type="checkbox" checked={form.options.trust_server_certificate}
                onChange={(e) => opt({ trust_server_certificate: e.target.checked })} />
              <span>Trust the server certificate<br /><span className="hint">Only for servers with a self-signed certificate, such as test servers.</span></span>
            </label>
            <fieldset className="group">
              <legend>Default audit (optional)</legend>
              <div className="form-grid">
                <label className="field">Audit ID
                  <input value={form.options.audit_id ?? ""} placeholder="e.g. 12345" onChange={(e) => opt({ audit_id: e.target.value })} />
                </label>
                <label className="field">Audit name
                  <input value={form.options.audit_name ?? ""} placeholder="e.g. Equiti FA 2024" onChange={(e) => opt({ audit_name: e.target.value })} />
                </label>
              </div>
              <span className="hint">When set, questions that don't name an audit are answered for this one.</span>
            </fieldset>
          </>
        ) : isFile ? (
          <label className="field">Database file path on the server
            <input value={form.database} required placeholder="e.g. C:\data\sales.db" onChange={(e) => set("database", e.target.value)} />
          </label>
        ) : (
          <>
            <div className="form-grid host-grid">
              <label className="field">Server name or address
                <input value={form.host} required placeholder="e.g. db-server.company.local" onChange={(e) => set("host", e.target.value)} />
              </label>
              <label className="field">Port
                <input type="number" min={1} max={65535} value={form.port ?? ""} placeholder={String(info.port)}
                  onChange={(e) => set("port", e.target.value ? Number(e.target.value) : null)} />
              </label>
            </div>
            <label className="field">Database name
              <input value={form.database} required placeholder={info.databaseHint} onChange={(e) => set("database", e.target.value)} />
            </label>
            <div className="form-grid">
              <label className="field">Username
                <input value={form.username} autoComplete="off" placeholder="e.g. report_reader" onChange={(e) => set("username", e.target.value)} />
              </label>
              <label className="field">Password
                <input type="password" value={form.password ?? ""} autoComplete="new-password"
                  placeholder={connection?.has_password ? "Saved. Leave blank to keep it." : ""}
                  onChange={(e) => set("password", e.target.value)} />
              </label>
            </div>
            {info.hasSchemas && (
              <label className="field">Schemas to include (optional)
                <input value={schemasText} placeholder={`e.g. ${info.schemaExample}. Leave blank for all.`}
                  onChange={(e) => { setSchemasText(e.target.value); setTest(null); }} />
              </label>
            )}
            {form.db_type === "postgresql" && (
              <label className="check">
                <input type="checkbox" checked={form.options.ssl} onChange={(e) => set("options", { ...form.options, ssl: e.target.checked })} />
                Require an encrypted (SSL) connection
              </label>
            )}
            {form.db_type === "mssql" && (
              <label className="check">
                <input type="checkbox" checked={form.options.trust_server_certificate}
                  onChange={(e) => set("options", { ...form.options, trust_server_certificate: e.target.checked })} />
                <span>Trust the server certificate<br /><span className="hint">Only for servers with a self-signed certificate, such as test servers.</span></span>
              </label>
            )}
          </>
        )}

        {test && (
          <div className={"alert " + (test.ok ? "alert-ok" : "alert-error")} role="status">
            <div className="strong">{test.ok ? "Connection works" : "Couldn't connect"}</div>
            <div>{test.message}</div>
          </div>
        )}

        <div className="alert alert-info small">
          <span className="strong">Use a read-only account.</span> {info.readOnlyTip} The account should not be able
          to change any data.
        </div>
      </div>
    </Modal>
  );
}
