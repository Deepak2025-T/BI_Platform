import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { errorMessage } from "../api/client";
import { assistantApi } from "../api/endpoints";
import { visualsApi } from "../api/visuals";
import type { Agg, ChartSpec, DataSourceInfo, DateBucket, QueryData, VisualField, VisualFilter, VisualMeasure, VisualSpec, VisualTable, Widget, WidgetStyle } from "../api/types";
import DataChart from "../components/DataChart";
import Icon from "../components/Icon";
import { useToast } from "../components/Toast";
import VisualFields from "../components/VisualFields";
import VisualFilters from "../components/VisualFilters";
import VisualGallery from "../components/VisualGallery";
import VisualWells from "../components/VisualWells";
import { rememberSource, rememberedSource, sourceIdOf, sourceValue } from "../lib/sources";
import { VISUAL_BY_ID, type WellId, type Wells, buildSpec, canDrop, emptyWells, missingWell } from "../lib/visuals";

/** How long to wait after the last change before running the preview query. */
const PREVIEW_DELAY = 450;

/**
 * A chart that has been put on the report but not saved yet.
 *
 * It holds two things at once: what the report needs (the standalone SQL and how to draw it), and
 * what the builder needs to open it again (the table, the visual, the wells, the filters). Keeping
 * the builder's own state means reopening a chart is exact — nothing has to be read back out of
 * the compiled query.
 */
interface TrayChart {
  key: string;
  title: string;
  table: string;
  visualId: string;
  wells: Wells;
  buckets: Record<string, DateBucket | undefined>;
  filters: VisualFilter[];
  spec: VisualSpec;
  chart: ChartSpec;
  style?: Partial<WidgetStyle>;
  sql: string;
}

/**
 * Builds a chart by choosing fields instead of writing SQL or asking a model.
 *
 * Nothing here writes SQL: the wells become a spec, the backend compiles and runs it, and what
 * comes back is drawn with the same renderer the dashboards use.
 *
 * One chart is built at a time, and "Add to report" puts it aside so the next one can be built —
 * each with its own table, filters and shape. Saving makes an ordinary dashboard report out of
 * however many were collected, so it can then be arranged, filtered, scheduled and published like
 * any other.
 */
export default function VisualBuilder() {
  const navigate = useNavigate();
  const toast = useToast();

  const [sources, setSources] = useState<DataSourceInfo[]>([]);
  const [source, setSource] = useState<string>("");
  const [tables, setTables] = useState<VisualTable[]>([]);
  const [table, setTable] = useState("");
  const [fields, setFields] = useState<VisualField[]>([]);

  const [visualId, setVisualId] = useState("column_clustered");
  const [wells, setWells] = useState<Wells>(emptyWells);
  const [buckets, setBuckets] = useState<Record<string, DateBucket | undefined>>({});
  const [filters, setFilters] = useState<VisualFilter[]>([]);
  const [title, setTitle] = useState("");

  // The charts put aside for this report, and which of them the canvas is currently editing.
  const [charts, setCharts] = useState<TrayChart[]>([]);
  const [editingKey, setEditingKey] = useState<string | null>(null);
  const [reportTitle, setReportTitle] = useState("");
  const [adding, setAdding] = useState(false);

  const [data, setData] = useState<QueryData | null>(null);
  const [sql, setSql] = useState("");
  const [showSql, setShowSql] = useState(false);
  const [busy, setBusy] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [note, setNote] = useState("");

  const visual = VISUAL_BY_ID[visualId];
  const sourceId = source ? sourceIdOf(source) : null;

  /** Set while reopening a saved chart, so changing the table restores it instead of clearing it. */
  const reopening = useRef<TrayChart | null>(null);

  // ---------- Choosing a database and a table ----------

  useEffect(() => {
    assistantApi.sources().then((list) => {
      setSources(list);
      const last = rememberedSource();
      const fits = last && list.some((s) => sourceValue(s) === last);
      setSource(fits ? last! : list.length ? sourceValue(list[0]) : "");
    }).catch((err) => setError(errorMessage(err)));
  }, []);

  useEffect(() => {
    if (!source) return;
    rememberSource(source);
    setTables([]);
    setTable("");
    // A report runs against one database, so charts built on the last one can't come along.
    setCharts([]);
    setEditingKey(null);
    visualsApi.tables(sourceIdOf(source))
      .then((list) => {
        setTables(list);
        if (list.length === 1) setTable(list[0].table);
      })
      .catch((err) => setError(errorMessage(err)));
  }, [source]);

  useEffect(() => {
    if (!table) { setFields([]); return; }
    setData(null);
    setSql("");
    // Reopening a chart that was built on another table sets the table first and brings its own
    // fields with it; otherwise the fields belong to this table and nothing on the chart applies.
    const reopened = reopening.current;
    reopening.current = null;
    if (reopened) {
      setWells(reopened.wells);
      setBuckets(reopened.buckets);
      setFilters(reopened.filters);
    } else {
      setWells(emptyWells());
      setBuckets({});
      setFilters([]);
    }
    visualsApi.fields(sourceId, table)
      .then((r) => setFields(r.fields))
      .catch((err) => { setFields([]); setError(errorMessage(err)); });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [table]);

  // ---------- The spec, and the preview it drives ----------

  const built = useMemo(() => {
    if (!table) return null;
    const needed = missingWell(visual, wells);
    if (needed) return null;
    // A filter still being typed would only make the query fail, so leave it out until it is whole.
    const ready = filters.filter((f) => {
      const count = f.op === "is_null" || f.op === "is_not_null" ? 0 : f.op === "between" ? 2 : 1;
      const given = (f.values ?? []).filter((v) => String(v).trim() !== "");
      return f.op === "in" || f.op === "not_in" ? given.length > 0 : given.length === count;
    }).map((f) => ({ ...f, values: (f.values ?? []).filter((v) => String(v).trim() !== "") }));
    const built = buildSpec(visual, wells, buckets, { table, filters: ready, order: [], limit: 500 });

    // A query comes back in whatever order the database likes, so the chart has to ask. Dates read
    // in time order; everything else reads best ranked by its first number, as Power BI does.
    const axis = built.spec.dimensions[0];
    const measure = built.spec.measures[0];
    const order = axis?.bucket ? [{ ref: axis.alias!, dir: "asc" as const }]
      : measure ? [{ ref: measure.alias!, dir: "desc" as const }]
      : axis ? [{ ref: axis.alias!, dir: "asc" as const }]
      : [];
    return { ...built, spec: { ...built.spec, order } };
  }, [visual, wells, buckets, filters, table]);

  // Each change restarts the wait, so a run happens once the person stops rather than per keystroke.
  const runId = useRef(0);
  useEffect(() => {
    if (!built) { setData(null); setSql(""); return; }
    const spec = built.spec;
    const id = ++runId.current;
    setBusy(true);
    const timer = window.setTimeout(() => {
      visualsApi.run(sourceId, spec)
        .then((res) => { if (id === runId.current) { setData(res); setSql(res.sql); setError(""); } })
        .catch((err) => { if (id === runId.current) { setData(null); setError(errorMessage(err)); } })
        .finally(() => { if (id === runId.current) setBusy(false); });
    }, PREVIEW_DELAY);
    return () => window.clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [JSON.stringify(built?.spec), sourceId]);

  // ---------- Putting fields on the chart ----------

  const addTo = useCallback((well: WellId, column: string) => {
    setWells((w) => {
      const def = visual.wells.find((x) => x.id === well);
      if (!def) return w;
      if (def.accepts === "measure") {
        const field = fields.find((f) => f.name === column);
        const agg: Agg = field?.is_number ? "sum" : "count";
        return { ...w, [well]: [...(w[well] as never[]), { column, agg }] };
      }
      return { ...w, [well]: [...(w[well] as string[]), column] };
    });
    setNote("");
  }, [visual, fields]);

  /**
   * Clicking a field puts it where it most likely belongs: a number goes to Values before it is
   * offered an axis, and anything else goes to an axis first. Without that, clicking a number
   * would land it on Axis simply because Axis is listed first.
   */
  const addAnywhere = useCallback((field: VisualField) => {
    const preferred = field.is_number ? "measure" : "dimension";
    const order = [...visual.wells].sort((a, b) =>
      Number(b.accepts === preferred) - Number(a.accepts === preferred));
    const fit = order.find((w) => !canDrop(visual, w.id, field, wells[w.id].length));
    if (!fit) {
      setNote(`There's no room for "${field.name}" on a ${visual.label.toLowerCase()}. Remove a field first.`);
      return;
    }
    addTo(fit.id, field.name);
  }, [visual, wells, addTo]);

  const removeFrom = (well: WellId, index: number) =>
    setWells((w) => ({ ...w, [well]: (w[well] as unknown[]).filter((_, i) => i !== index) }));

  const setAgg = (well: WellId, index: number, agg: Agg) =>
    setWells((w) => ({ ...w, [well]: (w[well] as { agg: Agg }[]).map((m, i) => (i === index ? { ...m, agg } : m)) }));

  /**
   * Switching chart type keeps the fields. Each one stays in the well of the same name where the
   * new chart has one, and anything left over moves to the first well that will take it — so
   * changing a column chart to a donut carries the axis across to its legend rather than
   * emptying the chart.
   */
  function changeVisual(id: string) {
    const next = VISUAL_BY_ID[id];
    setVisualId(id);
    setWells((current) => {
      const kept = emptyWells();
      const spare: { dimension: string[]; measure: VisualMeasure[] } = { dimension: [], measure: [] };

      for (const [well, items] of Object.entries(current) as [WellId, unknown[]][]) {
        const def = next.wells.find((w) => w.id === well);
        const fits = def ? items.slice(0, def.max) : [];
        const over = def ? items.slice(def.max) : items;
        if (def) kept[well] = fits as never;
        // A well's items are measures only when the well it came from held measures.
        const wasMeasure = well === "values" || well === "values2" || well === "size";
        if (wasMeasure) spare.measure.push(...(over as VisualMeasure[]));
        else spare.dimension.push(...(over as string[]));
      }

      for (const def of next.wells) {
        const pool = def.accepts === "measure" ? spare.measure : spare.dimension;
        while (kept[def.id].length < def.max && pool.length) {
          (kept[def.id] as unknown[]).push(pool.shift()!);
        }
      }
      return kept;
    });
  }

  const usedColumns = useMemo(() => new Set<string>([
    ...wells.axis, ...wells.legend, ...wells.rows, ...wells.columns,
    ...[...wells.values, ...wells.values2, ...wells.size].map((m) => m.column),
  ]), [wells]);

  // ---------- Collecting the charts ----------

  const chartName = () => title.trim() || `${visual.label} of ${table.split(".").pop()}`;

  /**
   * The chart on the canvas, ready to be put on the report.
   *
   * The preview keeps filter values out of the SQL, but a saved chart is run later by the
   * dashboard with nothing alongside it, so ask for a query that stands on its own.
   */
  async function currentChart(): Promise<TrayChart> {
    const standalone = await visualsApi.compile(sourceId, built!.spec, true);
    return {
      key: editingKey ?? `c${Date.now().toString(36)}${charts.length}`,
      title: chartName(), table, visualId, wells, buckets, filters,
      spec: built!.spec, chart: built!.chart, style: visual.style, sql: standalone.sql,
    };
  }

  /** Puts the canvas chart on the report, replacing the one being edited, and clears the canvas. */
  async function addChart() {
    if (!built || !data) return;
    setAdding(true);
    setError("");
    try {
      const item = await currentChart();
      setCharts((cs) => (editingKey ? cs.map((c) => (c.key === editingKey ? item : c)) : [...cs, item]));
      toast(editingKey ? `Updated "${item.title}".` : `Added "${item.title}" to the report.`);
      clearCanvas();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setAdding(false);
    }
  }

  function clearCanvas() {
    setEditingKey(null);
    setWells(emptyWells());
    setBuckets({});
    setFilters([]);
    setTitle("");
    setData(null);
    setSql("");
    setNote("");
  }

  /** Brings a chart back onto the canvas, exactly as it was built. */
  function editChart(key: string) {
    const c = charts.find((x) => x.key === key);
    if (!c) return;
    setEditingKey(key);
    setVisualId(c.visualId);
    setTitle(c.title);
    setNote("");
    if (c.table !== table) {
      reopening.current = c;
      setTable(c.table);
    } else {
      setWells(c.wells);
      setBuckets(c.buckets);
      setFilters(c.filters);
    }
  }

  function removeChart(key: string) {
    setCharts((cs) => cs.filter((c) => c.key !== key));
    if (editingKey === key) clearCanvas();
  }

  // ---------- Saving ----------

  /**
   * Saves every chart on the report as one dashboard. Whatever is on the canvas counts too, so a
   * single chart needs no "add" first and a half-finished addition is never quietly dropped.
   */
  async function save() {
    setSaving(true);
    setError("");
    try {
      let items = charts;
      if (built && data) {
        const item = await currentChart();
        items = editingKey ? charts.map((c) => (c.key === editingKey ? item : c)) : [...charts, item];
      }
      if (!items.length) { setError("Add a chart to the report first."); return; }
      const name = reportTitle.trim() || items[0].title;
      const widgets: Widget[] = items.map((c, i) => ({
        id: `v${i + 1}`,
        title: c.title,
        question: "",
        sql: c.sql,
        chart: c.chart,
        visual: c.spec,
        style: c.style,
        // Side by side once there is more than one, as a dashboard of one chart reads better wide.
        size: items.length > 1 ? "half" : "full",
      }));
      const report = await assistantApi.save({ source_id: sourceId, title: name, prompt: "", widgets });
      toast(`Saved "${name}" with ${widgets.length} chart${widgets.length === 1 ? "" : "s"}.`);
      navigate(`/reports/${report.id}/edit`);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setSaving(false);
    }
  }

  // ---------- The page ----------

  const needed = missingWell(visual, wells);
  const sourceName = sources.find((s) => sourceValue(s) === source)?.name ?? "";

  return (
    <div className="page builder">
      <div className="row-between builder-top">
        <div className="row-wrap">
          <label className="field">
            Database
            <select value={source} onChange={(e) => setSource(e.target.value)} disabled={sources.length === 0}>
              {sources.map((s) => <option key={sourceValue(s)} value={sourceValue(s)}>{s.name}</option>)}
            </select>
          </label>
          <label className="field">
            Table
            <select value={table} onChange={(e) => setTable(e.target.value)} disabled={tables.length === 0}>
              <option value="">{tables.length ? "Choose a table…" : "No tables shared"}</option>
              {tables.map((t) => <option key={t.table} value={t.table}>{t.table}</option>)}
            </select>
          </label>
          <label className="field builder-title">
            Chart title
            <input value={title} placeholder={table ? `${visual.label} of ${table.split(".").pop()}` : "Untitled"}
              onChange={(e) => setTitle(e.target.value)} />
          </label>
        </div>
        <div className="row-wrap">
          {busy && <span className="spinner" aria-label="Running the query" />}
          <button className="btn btn-ghost" disabled={!sql} onClick={() => setShowSql((s) => !s)}>
            <Icon name="layers" size={16} />{showSql ? "Hide SQL" : "Show SQL"}
          </button>
          <button className="btn" disabled={!data || adding || saving} onClick={addChart}>
            <Icon name="plus" size={16} />
            {adding ? "Adding…" : editingKey ? "Update chart" : "Add to report"}
          </button>
          <button className="btn btn-primary" disabled={(!data && charts.length === 0) || saving || adding} onClick={save}>
            {saving ? "Saving…" : charts.length ? `Save report (${charts.length + (data ? (editingKey ? 0 : 1) : 0)})` : "Save as a report"}
          </button>
        </div>
      </div>

      {tables.length === 0 && source && (
        <p className="muted small">
          No tables have been shared from {sourceName} yet. A manager chooses them on the Connections page.
        </p>
      )}

      {charts.length > 0 && (
        <div className="card builder-tray">
          <div className="row-between row-wrap">
            <label className="field builder-title">
              Report name
              <input value={reportTitle} placeholder={charts[0].title}
                onChange={(e) => setReportTitle(e.target.value)} />
            </label>
            <span className="muted small">
              {charts.length} chart{charts.length === 1 ? "" : "s"} on this report
              {data && !editingKey ? ", plus the one on the canvas" : ""}
            </span>
          </div>
          <ul className="tray-list">
            {charts.map((c) => (
              <li key={c.key} className={`tray-chip${editingKey === c.key ? " on" : ""}`}>
                <button type="button" className="tray-open" onClick={() => editChart(c.key)}>
                  <b>{c.title}</b>
                  <span className="muted small">{VISUAL_BY_ID[c.visualId].label} · {c.table}</span>
                </button>
                <button type="button" className="tray-remove" aria-label={`Remove ${c.title}`}
                  onClick={() => removeChart(c.key)}>
                  <Icon name="x" size={15} />
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="builder-grid">
        <aside className="builder-pane" aria-label="Fields">
          {table
            ? <VisualFields fields={fields} table={table} used={usedColumns} onAdd={addAnywhere} />
            : <p className="muted small">Choose a table to see its fields.</p>}
        </aside>

        <section className="builder-canvas">
          {error && <div className="alert alert-error">{error}</div>}
          {note && <div className="alert">{note}</div>}

          {!table ? (
            <div className="builder-blank">
              <Icon name="grid" size={28} className="faint" />
              <p className="muted">Choose a table, then drag a field onto the chart.</p>
            </div>
          ) : needed ? (
            <div className="builder-blank">
              <Icon name="grid" size={28} className="faint" />
              <p className="muted">Drag a field onto <b>{needed.label}</b> to draw this chart.</p>
            </div>
          ) : data ? (
            <div className="card builder-chart">
              <div className="row-between">
                <h2 className="tile-title">{title.trim() || `${visual.label} of ${table.split(".").pop()}`}</h2>
                <span className="muted small">
                  {data.row_count}{data.truncated ? "+" : ""} rows · {data.elapsed_ms} ms
                </span>
              </div>
              <DataChart columns={data.columns} rows={data.rows} chart={built!.chart}
                style={visual.style} height={360} tableHeight={360} truncated={data.truncated} />
            </div>
          ) : (
            <div className="builder-blank"><span className="spinner" /><p className="muted">Running the query…</p></div>
          )}

          {showSql && sql && (
            <div className="card">
              <div className="muted small">The query this chart runs. Values you typed are sent separately, not written in.</div>
              <pre className="sql-box">{sql}</pre>
            </div>
          )}
        </section>

        <aside className="builder-pane" aria-label="Visualisation and fields">
          <div className="stack">
            <div>
              <div className="field-group-label">Visualisation</div>
              <VisualGallery value={visualId} onChange={changeVisual} />
            </div>
            {table && (
              <>
                <div>
                  <div className="field-group-label">{visual.label}</div>
                  <VisualWells visual={visual} wells={wells} fields={fields} buckets={buckets}
                    onDrop={addTo} onRemove={removeFrom} onAgg={setAgg}
                    onBucket={(column, bucket) => setBuckets((b) => ({ ...b, [column]: bucket }))}
                    onRefuse={setNote} />
                </div>
                <div>
                  <div className="field-group-label">Filters on this chart</div>
                  <VisualFilters sourceId={sourceId} table={table} fields={fields}
                    filters={filters} onChange={setFilters} />
                </div>
              </>
            )}
          </div>
        </aside>
      </div>
    </div>
  );
}
