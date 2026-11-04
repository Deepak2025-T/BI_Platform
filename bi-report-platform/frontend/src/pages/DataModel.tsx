import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { errorMessage } from "../api/client";
import { assistantApi, dataModelsApi } from "../api/endpoints";
import type { DataModelDetail, DataModelSummary, DataSourceInfo } from "../api/types";
import Icon from "../components/Icon";
import ModelDiagram from "../components/ModelDiagram";
import { useToast } from "../components/Toast";
import { bySolution, rememberModel, rememberedModel } from "../lib/dataModel";
import { rememberSource, rememberedSource, sourceIdOf, sourceValue } from "../lib/sources";

/**
 * The object model behind a database, the way Power BI shows one: every object type as a box of
 * fields, with a line to each type that sits under it.
 *
 * The shape is shipped with OpenPages and is the same everywhere. The fields are not: they are
 * read from the chosen connection and cached, which is what Refresh clears - so a field added in
 * OpenPages this morning appears without waiting or restarting anything.
 */
export default function DataModel() {
  const toast = useToast();
  const navigate = useNavigate();
  const [models, setModels] = useState<DataModelSummary[]>([]);
  const [sources, setSources] = useState<DataSourceInfo[]>([]);
  const [source, setSource] = useState("builtin");
  const [key, setKey] = useState("");
  const [detail, setDetail] = useState<DataModelDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState("");

  useEffect(() => {
    dataModelsApi.list().then((list) => {
      setModels(list);
      setKey((k) => k || list.find((m) => m.namespace === "SOX1")?.key || list[0]?.key || "");
    }).catch((e) => setError(errorMessage(e)));

    assistantApi.sources().then((list) => {
      // Only OpenPages connections have an object model, so only they are worth offering here.
      const op = list.filter((s) => s.db_type === "openpages");
      setSources(op);
      const last = rememberedSource();
      setSource(op.some((s) => sourceValue(s) === last) ? last! : op[0] ? sourceValue(op[0]) : "");
    }).catch(() => setSources([]));
  }, []);

  // A model remembered per database, so coming back lands where it was left.
  useEffect(() => {
    if (!source) return;
    const last = rememberedModel(source);
    if (last) setKey(last);
  }, [source]);

  useEffect(() => {
    if (!key) return;
    setLoading(true);
    setSelected("");
    dataModelsApi.read(key, source ? sourceIdOf(source) : null)
      .then((d) => { setDetail(d); setError(""); })
      .catch((e) => { setError(errorMessage(e)); setDetail(null); })
      .finally(() => setLoading(false));
  }, [key, source]);

  const refresh = () => {
    if (!key) return;
    setRefreshing(true);
    dataModelsApi.refresh(key, source ? sourceIdOf(source) : null)
      .then((d) => {
        setDetail(d);
        toast(d.live ? `Read ${d.entities.filter((e) => e.fields.length).length} object types again from ${d.connection?.name}`
          : "The model was re-read. Pick an OpenPages database to see its fields.");
      })
      .catch((e) => toast(errorMessage(e)))
      .finally(() => setRefreshing(false));
  };

  const chooseModel = (k: string) => { setKey(k); if (source) rememberModel(source, k); };
  const chooseSource = (v: string) => { setSource(v); rememberSource(v); };

  const groups = useMemo(() => bySolution(models), [models]);
  const entity = detail?.entities.find((e) => e.name === selected) ?? null;
  const shared = detail?.entities.filter((e) => e.shared).length ?? 0;

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h1>Data model</h1>
          <p className="muted">
            The object types in an IBM OpenPages model and how they nest. A line runs from a type to
            each type that sits under it &mdash; which is also how its queries join.
          </p>
        </div>
        <div className="row-wrap">
          <button className="btn btn-ghost" onClick={refresh} disabled={refreshing || loading || !key}>
            {refreshing ? <span className="spinner" aria-hidden="true" /> : <Icon name="history" size={16} />}
            {refreshing ? "Refreshing" : "Refresh data"}
          </button>
          <button className="btn btn-primary" disabled={!detail}
            onClick={() => navigate("/", { state: { mode: "build", dataModel: key, source } })}>
            <Icon name="spark" size={16} /> Build a report with this model
          </button>
        </div>
      </div>

      <div className="row-wrap model-controls">
        <label className="model-picker">
          <span className="muted small">Data model</span>
          <select value={key} onChange={(e) => chooseModel(e.target.value)} aria-label="Data model">
            {groups.map(([solution, list]) => (
              <optgroup key={solution} label={solution}>
                {list.map((m) => (
                  <option key={m.key} value={m.key}>
                    {m.namespace}{m.is_default ? " (default)" : ""} &middot; {m.entity_count} types
                  </option>
                ))}
              </optgroup>
            ))}
          </select>
        </label>

        <label className="model-picker">
          <span className="muted small">Database</span>
          <select value={source} onChange={(e) => chooseSource(e.target.value)} aria-label="Database"
            disabled={sources.length === 0}>
            {sources.map((s) => <option key={sourceValue(s)} value={sourceValue(s)}>{s.name}</option>)}
            {sources.length === 0 && <option value="">No OpenPages connection</option>}
          </select>
        </label>

        <label className="model-picker grow">
          <span className="muted small">Find a type or field</span>
          <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="risk, status, loss…"
            aria-label="Find a type or field" />
        </label>
      </div>

      {error && <div className="alert alert-error">{error}</div>}
      {detail?.note && <div className="alert alert-info">{detail.note}</div>}

      {detail && (
        <p className="muted small">
          {detail.name} &middot; {detail.entities.length} object types &middot; {detail.relationships.length} relationships
          {detail.connection ? ` · ${shared} shared from ${detail.connection.name}`
            : " · no database chosen, so no fields are shown"}
        </p>
      )}

      {loading && !detail && <div className="card"><span className="spinner" aria-hidden="true" /> Reading the model…</div>}

      {detail && (
        <div className={"model-layout" + (entity ? " with-panel" : "")}>
          <ModelDiagram model={detail} search={search} selected={selected} onSelect={setSelected} />
          {entity && (
            <aside className="card model-panel">
              <div className="page-head tight">
                <h2>{entity.name}</h2>
                <button type="button" className="icon-btn" aria-label="Close" onClick={() => setSelected("")}>
                  <Icon name="x" size={16} />
                </button>
              </div>
              <p className="muted small">
                {entity.shared === null ? "No database chosen, so nothing has been checked."
                  : entity.shared ? "Shared with this app, so reports can use it."
                  : entity.exists ? "Installed in OpenPages, but not shared with this app yet."
                  : "Not installed in this OpenPages environment."}
              </p>

              {entity.parents.length > 0 && (
                <p className="small"><strong>Sits under:</strong> {entity.parents.join(", ")}</p>
              )}
              {entity.children.length > 0 && (
                <p className="small"><strong>Has under it:</strong> {entity.children.join(", ")}</p>
              )}
              {entity.self_nesting && <p className="small">Nests under itself, so it forms a tree.</p>}

              <h3 className="small">Fields ({entity.fields.length})</h3>
              {entity.fields.length === 0 ? (
                <p className="muted small">No fields have been read for this type.</p>
              ) : (
                <ul className="model-panel-fields">
                  {entity.fields.map((f) => (
                    <li key={f.name}>
                      <span className="model-field-name">{f.name}</span>
                      <span className="model-field-type">{f.type}</span>
                      {f.values.length > 0 && f.values.length <= 15 && (
                        <span className="muted small">{f.values.join(", ")}</span>
                      )}
                    </li>
                  ))}
                </ul>
              )}
            </aside>
          )}
        </div>
      )}
    </div>
  );
}
