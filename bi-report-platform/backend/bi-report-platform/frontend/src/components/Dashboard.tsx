import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { errorMessage } from "../api/client";
import { aiModelsApi, assistantApi, reportsApi } from "../api/endpoints";
import { reportToolsApi } from "../api/reportTools";
import { scheduleApi } from "../api/schedule";
import type {
  AIModelPublic, Cell, ChartType, DashboardConfig, DashboardFilter, FilterValue, Report, Widget, WidgetData,
} from "../api/types";
import { rememberedModel } from "../lib/aiModels";
import { cardLook } from "../lib/cardColors";
import { shortDate } from "../lib/format";
import { COMPARE_OPTIONS, type CompareWith, type HistoryPoint, compareAt, timeLabels } from "../lib/history";
import { useAutosave } from "../lib/useAutosave";
import { HEIGHT, WIDTHS, hasHeight, sizeForCols, tileCols } from "../lib/tileSize";
import { CHART_LABELS, retype } from "../lib/sources";
import CategoryBadge from "./CategoryBadge";
import CardColors from "./CardColors";
import ChartEditor from "./ChartEditor";
import DataChart from "./DataChart";
import FilterColumnsDialog from "./FilterColumnsDialog";
import FullscreenButton from "./FullscreenButton";
import Icon from "./Icon";
import PublishDialog from "./PublishDialog";
import RefreshSchedule from "./RefreshSchedule";
import TableChanges from "./TableChanges";
import TileMenu from "./TileMenu";
import ResizeHandle from "./ResizeHandle";
import { useToast } from "./Toast";

interface Props {
  report: Report & { config: DashboardConfig };
  editable: boolean;
  canEdit: boolean;
}

/** A dashboard report: charts built by an AI model, each re-running its saved SQL when opened. */
export default function Dashboard({ report, editable, canEdit }: Props) {
  const navigate = useNavigate();
  const location = useLocation();
  const toast = useToast();
  const [title, setTitle] = useState(report.title);
  const [config, setConfig] = useState(report.config);
  const [data, setData] = useState<Record<string, WidgetData>>({});
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [publishing, setPublishing] = useState(false);
  const [info, setInfo] = useState<string | null>(null);
  const failed = (location.state as { failed?: { title: string; error: string }[] } | null)?.failed ?? [];
  const [values, setValues] = useState<Record<string, FilterValue>>({});
  const [updating, setUpdating] = useState(false);
  const [exporting, setExporting] = useState(false);
  const latest = useRef(0);
  const [schedule, setSchedule] = useState<Report>(report); // the report's refresh schedule, updated in place
  const [snapshotAt, setSnapshotAt] = useState<string | null>(null);
  const filters = config.filters ?? [];
  // History (auto-refresh keeps each refresh): trends per chart, and a comparison with an earlier refresh.
  // Both use the saved refreshes, so they show when the dashboard shows a refresh (no filters set).
  const autoOn = schedule.refresh_every !== "off";
  const [historyData, setHistoryData] = useState<Record<string, HistoryPoint[]>>({});
  const [compareWith, setCompareWith] = useState<CompareWith>("previous");
  const [baseline, setBaseline] = useState<{ label: string; widgets: Record<string, { columns: string[]; rows: Cell[][] }> } | null>(null);
  const [historyOpen, setHistoryOpen] = useState<Set<string>>(new Set());

  // Runs every chart's saved SQL with the chosen filter values. refresh skips the 15-minute cache.
  const load = useCallback((refresh = false) => {
    const n = ++latest.current;
    setUpdating(true);
    assistantApi.data(report.id, { filters: values, refresh })
      .then((res) => {
        if (n !== latest.current) return;
        setData(Object.fromEntries(res.widgets.map((w) => [w.id, w])));
        setSnapshotAt(res.snapshot_at);
        setLoadError("");
      })
      .catch((e) => { if (n === latest.current) setLoadError(errorMessage(e)); })
      .finally(() => { if (n === latest.current) { setLoading(false); setUpdating(false); } });
  }, [report.id, values]);

  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    if (!autoOn || !snapshotAt) { setHistoryData({}); return; }
    scheduleApi.history(report.id).then((h) => setHistoryData(h.widgets)).catch(() => setHistoryData({}));
  }, [report.id, autoOn, snapshotAt]);

  useEffect(() => {
    if (!autoOn || !snapshotAt || compareWith === "none") { setBaseline(null); return; }
    scheduleApi.compare(report.id, compareAt(compareWith))
      .then((c) => setBaseline(c ? { label: shortDate(c.taken_at), widgets: Object.fromEntries(c.widgets.map((w) => [w.id, w])) } : null))
      .catch(() => setBaseline(null));
  }, [report.id, autoOn, snapshotAt, compareWith]);

  const toggleHistory = (id: string) => setHistoryOpen((s) => {
    const next = new Set(s);
    if (next.has(id)) next.delete(id); else next.add(id);
    return next;
  });

  const setValue = (id: string, patch: FilterValue) =>
    setValues((v) => ({ ...v, [id]: { ...v[id], ...patch } }));
  const active = filters.filter((f) => {
    const v = values[f.id];
    return f.kind === "date" ? !!(v?.date_from || v?.date_to) : !!v?.values?.length;
  });

  async function exportExcel() {
    setExporting(true);
    try {
      const blob = await assistantApi.exportExcel(report.id, { filters: values });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${(title || "Dashboard").replace(/[\\/:*?"<>|]+/g, " ").trim()}.xlsx`;
      a.click();
      window.setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch {
      toast("Couldn't create the Excel file. Try again.");
    } finally {
      setExporting(false);
    }
  }

  // When the data shown was fetched: the oldest chart result, which may come from the cache.
  const results = Object.values(data).filter((d): d is Extract<WidgetData, { ok: true }> => d.ok);
  const ranAt = results.map((d) => d.ran_at).filter(Boolean).sort()[0];
  const anyCached = results.some((d) => d.cached);

  // Edit mode: save 700 ms after the last change, and right away when leaving the editor.
  const draft = useMemo(() => ({ title, config }), [title, config]);
  const saveState = useAutosave(draft, (d) => reportsApi.update(report.id, { title: d.title || "Untitled dashboard", config: d.config }),
                                editable);

  const [editingChart, setEditingChart] = useState<string | null>(null);
  const [filterDialog, setFilterDialog] = useState<{ filter?: DashboardFilter } | null>(null);
  const [duplicating, setDuplicating] = useState(false);
  // Drag and drop: a tile becomes draggable while its handle is held, so text in its inputs can still be selected.
  const [armed, setArmed] = useState<string | null>(null);
  const [dragId, setDragId] = useState<string | null>(null);
  const [overId, setOverId] = useState<string | null>(null);
  const chartWidgets = config.widgets.filter((w) => w.kind !== "text");

  const dropOn = (targetId: string) => {
    if (!dragId || dragId === targetId) return;
    const list = [...config.widgets];
    const from = list.findIndex((w) => w.id === dragId);
    const target = list.findIndex((w) => w.id === targetId);
    const [moved] = list.splice(from, 1);
    const at = list.findIndex((w) => w.id === targetId);
    list.splice(from < target ? at + 1 : at, 0, moved); // dragging down lands after the target, up lands before it
    setWidgets(list);
  };
  const dragProps = (id: string) => editable ? {
    draggable: armed === id,
    onDragStart: (e: React.DragEvent) => { setDragId(id); e.dataTransfer.effectAllowed = "move"; e.dataTransfer.setData("text/plain", id); },
    onDragOver: (e: React.DragEvent) => { if (dragId && dragId !== id) { e.preventDefault(); setOverId(id); } },
    onDragLeave: () => setOverId((o) => (o === id ? null : o)),
    onDrop: (e: React.DragEvent) => { e.preventDefault(); dropOn(id); setOverId(null); },
    onDragEnd: () => { setDragId(null); setOverId(null); setArmed(null); },
  } : {};
  const dragClass = (id: string) => (dragId === id ? " dragging" : "") + (overId === id ? " drop-target" : "");
  const handle = (w: Widget) => editable && (
    <span className="drag-handle" title="Drag to move" aria-hidden="true"
      onMouseDown={() => setArmed(w.id)} onMouseUp={() => setArmed(null)}><Icon name="grip" size={16} /></span>
  );
  const addText = () => setWidgets([...config.widgets, {
    id: Math.random().toString(16).slice(2, 10), kind: "text", title: "New section", text: "", question: "", sql: "",
    chart: { type: "table", x: "", y: [] }, size: "full",
  }]);
  // Resizing: the corner handle on each tile (see ResizeHandle).
  const gridRef = useRef<HTMLDivElement>(null);
  const [resizing, setResizing] = useState<string | null>(null);
  const patchWidget = (id: string, patch: Partial<Widget>) =>
    setConfig((c) => ({ ...c, widgets: c.widgets.map((x) => (x.id === id ? { ...x, ...patch } : x)) }));
  const resizer = (w: Widget) => editable && (
    <ResizeHandle name={w.title || "tile"} cols={tileCols(w)} height={hasHeight(w) ? w.height ?? HEIGHT.default : undefined}
      grid={gridRef} onChange={(patch) => patchWidget(w.id, patch)} onActive={(on) => setResizing(on ? w.id : null)} />
  );
  const resizeClass = (w: Widget) => (editable ? " resizable" : "") + (resizing === w.id ? " resizing" : "");

  // Removing asks nothing but can be undone from the message that follows.
  const remove = (w: Widget) => {
    const before = config.widgets;
    setWidgets(before.filter((x) => x.id !== w.id));
    toast(`Removed "${w.title || "text"}".`, { label: "Undo", onClick: () => setConfig((c) => ({ ...c, widgets: before })) });
  };
  const menuItems = (w: Widget, i: number) => [
    ...(w.kind === "text" ? [] : [{ label: "Duplicate", onClick: () => duplicateChart(w) }]),
    { label: "Move earlier", onClick: () => move(i, -1), disabled: i === 0 },
    { label: "Move later", onClick: () => move(i, 1), disabled: i === config.widgets.length - 1 },
    { label: "Remove", onClick: () => remove(w), danger: true },
  ];

  // Header and card colours: on one tile, or the same on every tile.
  const setLook = (w: Widget, patch: Partial<NonNullable<Widget["style"]>>) =>
    patchWidget(w.id, { style: { ...w.style, ...patch } });
  const lookAll = (patch: Pick<NonNullable<Widget["style"]>, "headBg" | "cardBg">) => {
    setConfig((c) => ({ ...c, widgets: c.widgets.map((x) => ({ ...x, style: { ...x.style, ...patch } })) }));
    toast("Every card now uses these colours");
  };

  const colorAll = (color: string) => {
    commit({ ...config, widgets: config.widgets.map((w) => (w.kind === "text" ? w : { ...w, style: { ...w.style, color } })) });
    toast("Every chart now uses this colour");
  };

  // In edit mode changes autosave. From the preview, a chart edited with its Edit button is saved straight away.
  const commit = (next: DashboardConfig) => {
    setConfig(next);
    if (!editable) {
      reportsApi.update(report.id, { config: next }).then(() => toast("Chart saved")).catch((e) => toast(errorMessage(e)));
    }
  };
  const saveChart = (w: Widget, d: WidgetData | null) => {
    commit({ ...config, widgets: config.widgets.map((x) => (x.id === w.id ? w : x)) });
    if (d) setData((m) => ({ ...m, [w.id]: d }));
    setEditingChart(null);
  };
  const duplicateChart = (w: Widget) => {
    const copy = { ...w, id: Math.random().toString(16).slice(2, 10), title: `Copy of ${w.title}`.slice(0, 120) };
    const i = config.widgets.findIndex((x) => x.id === w.id);
    setWidgets([...config.widgets.slice(0, i + 1), copy, ...config.widgets.slice(i + 1)]);
    if (data[w.id]) setData((m) => ({ ...m, [copy.id]: { ...m[w.id], id: copy.id } }));
  };

  async function duplicateReport() {
    setDuplicating(true);
    try {
      const copy = await reportToolsApi.duplicate(report.id);
      toast(`Made "${copy.title}", your own draft to change.`);
      navigate(`/reports/${copy.id}/edit`);
    } catch (err) {
      toast(errorMessage(err));
    } finally {
      setDuplicating(false);
    }
  }

  const setWidgets = (widgets: Widget[]) => setConfig((c) => ({ ...c, widgets }));
  const change = (id: string, patch: Partial<Widget>) => setWidgets(config.widgets.map((w) => (w.id === id ? { ...w, ...patch } : w)));
  const move = (i: number, d: number) => {
    const list = [...config.widgets];
    if (i + d < 0 || i + d >= list.length) return;
    [list[i], list[i + d]] = [list[i + d], list[i]];
    setWidgets(list);
  };

  async function publish(categoryId: number | null) {
    await reportsApi.update(report.id, { title, config });
    const published = await reportsApi.publish(report.id, categoryId);
    toast(published.category ? `Published in ${published.category.name}.` : "Published. Everyone in your organisation can open it.");
    navigate(`/reports/${report.id}`);
  }

  const params = config.parameters;
  const paramText = [
    params?.date_from || params?.date_to ? `${params.date_from ?? "start"} to ${params.date_to ?? "today"}` : "",
    params?.filters ?? "",
  ].filter(Boolean).join(", ");

  return (
    <div className="viewer">
      <header className={editable ? "toolbar" : "viewer-head"}>
        {editable ? (
          <>
            <label htmlFor="dtitle" className="sr-only">Dashboard title</label>
            <input id="dtitle" className="title-input" value={title} onChange={(e) => setTitle(e.target.value)} />
            <span className="muted small" aria-live="polite">
              {saveState === "saving" ? "Saving…" : saveState === "error" ? "Couldn't save. Check your connection." : report.status === "published" ? "Published, changes saved" : "Draft, saved"}
            </span>
            <button className="btn btn-ghost" onClick={duplicateReport} disabled={duplicating}>{duplicating ? "Duplicating…" : "Duplicate"}</button>
            <FullscreenButton />
            <button className="btn btn-ghost" onClick={() => navigate(`/reports/${report.id}`)}>See it as viewers will</button>
            <button className="btn btn-primary" onClick={() => setPublishing(true)}>{report.status === "published" ? "Update published report" : "Publish"}</button>
          </>
        ) : (
          <div className="row-between">
            <div>
              <div className="row-wrap">
                <h1 className="h1">{report.title}</h1>
                {report.status === "published" && <CategoryBadge category={report.category} />}
              </div>
              <div className="muted small">
                {report.status === "published" ? "Published" : "Draft, only you and managers can see it"}. By {report.owner_name}, updated {shortDate(report.updated_at)}.
              </div>
            </div>
            <div className="row-wrap no-print">
              <button className="btn btn-ghost" onClick={() => window.print()}>Download PDF</button>
              <button className="btn btn-ghost" onClick={exportExcel} disabled={exporting || loading}>
                {exporting ? "Preparing Excel…" : "Download Excel"}
              </button>
              <button className="btn btn-ghost" onClick={duplicateReport} disabled={duplicating}
                title="Copy this dashboard into a new draft of your own">{duplicating ? "Duplicating…" : "Duplicate"}</button>
              <FullscreenButton />
              {canEdit && <Link className="btn btn-primary" to={`/reports/${report.id}/edit`}>Edit dashboard</Link>}
            </div>
          </div>
        )}
      </header>

      <div className="viewer-body stack">
        <div className="row-wrap muted small dash-meta">
          <span className="chip"><span className="muted">Data</span> <b>{config.source_name}</b></span>
          {config.model && <span className="chip"><span className="muted">Built with</span> <b>{config.model}</b></span>}
          {paramText && <span className="chip"><span className="muted">Parameters</span> <b>{paramText}</b></span>}
          <span>{schedule.refresh_every === "off"
            ? "Each chart re-runs its saved query when the dashboard opens. No AI is used to show it."
            : "Shows the latest scheduled refresh of each chart's saved query (setting filters queries live). No AI is used."}</span>
        </div>
        <RefreshSchedule report={schedule} canEdit={canEdit} refreshedAt={snapshotAt}
          onChange={(r) => { setSchedule(r); load(); }} />

        {editable && (
          <FilterDesigner reportId={report.id} widgets={chartWidgets} filters={filters}
            onChange={(list) => setConfig((c) => ({ ...c, filters: list }))}
            onCustom={(filter) => setFilterDialog({ filter })} />
        )}

        <div className="filter-bar" role="group" aria-label="Dashboard filters">
          {filters.map((f) => f.kind === "date" ? (
            <div key={f.id} className="filter-field">
              <span className="filter-label">{f.label}</span>
              <input type="date" aria-label={`${f.label} from`} value={values[f.id]?.date_from ?? ""}
                max={values[f.id]?.date_to ?? undefined} onChange={(e) => setValue(f.id, { date_from: e.target.value || null })} />
              <span className="muted small">to</span>
              <input type="date" aria-label={`${f.label} to`} value={values[f.id]?.date_to ?? ""}
                min={values[f.id]?.date_from ?? undefined} onChange={(e) => setValue(f.id, { date_to: e.target.value || null })} />
            </div>
          ) : (
            <label key={f.id} className="filter-field">
              <span className="filter-label">{f.label}</span>
              <select value={values[f.id]?.values?.[0] ?? ""} aria-label={f.label}
                onChange={(e) => setValue(f.id, { values: e.target.value ? [e.target.value] : [] })}>
                <option value="">All</option>
                {f.options.map((o) => <option key={o} value={o}>{o}</option>)}
              </select>
            </label>
          ))}
          {active.length > 0 && <button className="btn btn-ghost btn-sm no-print" onClick={() => setValues({})}>Clear filters</button>}
          {autoOn ? (
            <label className="filter-field no-print">
              <span className="filter-label">Compare with</span>
              <select value={compareWith} aria-label="Compare with" onChange={(e) => setCompareWith(e.target.value as CompareWith)}>
                {COMPARE_OPTIONS.map(([k, l]) => <option key={k} value={k}>{l}</option>)}
              </select>
            </label>
          ) : canEdit && <span className="muted small no-print">Turn on auto-refresh to see changes over time.</span>}
          {autoOn && compareWith !== "none" && (active.length > 0
            ? <span className="muted small">Comparisons use unfiltered data; clear the filters to see them.</span>
            : snapshotAt && !baseline && <span className="muted small">No earlier refresh to compare with yet.</span>)}
          <span className="filter-status muted small" aria-live="polite">
            {updating && !loading ? "Updating…" : ranAt ? `Data from ${new Date(ranAt).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}${snapshotAt ? " (auto-refresh)" : anyCached ? ", saved for up to 15 minutes" : ""}` : ""}
          </span>
          <button className="btn btn-ghost btn-sm no-print" onClick={() => load(true)} disabled={updating}
            title="Run every query again now and show the latest data">Refresh</button>
        </div>
        {failed.length > 0 && editable && (
          <div className="alert alert-warn small">
            {failed.length} planned chart{failed.length === 1 ? " was" : "s were"} left out because the query didn't work:{" "}
            {failed.map((f) => f.title).join(", ")}. Add them again below by asking in other words.
          </div>
        )}
        {loadError && <div className="alert alert-error">{loadError}</div>}

        <div className="dash-grid" ref={gridRef}>
          {config.widgets.map((w, i) => {
            if (w.kind === "text") {
              return (
                <section key={w.id} className={`widget w-text size-${w.size ?? "auto"}${editable || w.style?.cardBg ? " card" : ""}${editable ? " editing" : ""}${cardLook(w.style).className}${dragClass(w.id)}${resizeClass(w)}`}
                  style={cardLook(w.style).style} aria-label={w.title || "Text"} {...dragProps(w.id)}>
                  <div className="widget-head">
                    {handle(w)}
                    {editable ? (
                      <input className="widget-title-input text-tile-title" value={w.title} placeholder="Heading" aria-label="Heading"
                        onChange={(e) => change(w.id, { title: e.target.value })} />
                    ) : w.title && <h2 className="text-tile-title">{w.title}</h2>}
                    {editable && (
                      <div className="widget-tools no-print">
                        <select className="chart-pick" value={sizeForCols(tileCols(w))} aria-label="Width" onChange={(e) => change(w.id, { size: e.target.value as Widget["size"] })}>
                          {WIDTHS.map((x) => <option key={x.size} value={x.size}>{x.label}</option>)}
                        </select>
                        <CardColors name={w.title || "text"} style={w.style ?? {}} onChange={(p) => setLook(w, p)} onApplyAll={lookAll} />
                        <TileMenu name={w.title || "text"} items={menuItems(w, i)} />
                      </div>
                    )}
                  </div>
                  {editable ? (
                    <textarea className="text-tile-input" rows={2} value={w.text ?? ""} placeholder="Notes for readers (optional)" aria-label="Notes"
                      onChange={(e) => change(w.id, { text: e.target.value })} />
                  ) : w.text && <p className="text-tile-body">{w.text}</p>}
                  {resizer(w)}
                </section>
              );
            }
            const d = data[w.id];
            const points = historyData[w.id] ?? [];
            const showHistory = historyOpen.has(w.id) && points.length > 1;
            const before = baseline?.widgets[w.id];
            const compare = before && d?.ok ? { label: baseline!.label, columns: before.columns, rows: before.rows } : undefined;
            const spark = w.chart.type === "kpi" ? points.map((p) => p.value).filter((v): v is number => typeof v === "number") : undefined;
            const unfiltered = (d?.not_filtered ?? []).map((id) => filters.find((f) => f.id === id)?.label).filter(Boolean);
            return (
              <section key={w.id} className={`card widget w-${w.chart.type} size-${w.size ?? "auto"}${cardLook(w.style).className}${dragClass(w.id)}${resizeClass(w)}`}
                style={cardLook(w.style).style} aria-label={w.title} {...dragProps(w.id)}>
                <div className="widget-head">
                  {handle(w)}
                  {editable ? (
                    <input className="widget-title-input" value={w.title} aria-label="Chart title" onChange={(e) => change(w.id, { title: e.target.value })} />
                  ) : <h2 className="h2">{w.title}</h2>}
                  {unfiltered.length > 0 && (
                    <span className="badge badge-off" title={`This chart's data has no column for: ${unfiltered.join(", ")}`}>
                      Not filtered{filters.length > 1 ? ` by ${unfiltered.join(", ")}` : ""}
                    </span>
                  )}
                  <div className="widget-tools no-print">
                    {editable && d?.ok && (
                      <select className="chart-pick" value={w.chart.type} aria-label="Chart type"
                        onChange={(e) => change(w.id, { chart: retype(w.chart, e.target.value as ChartType, d.columns, d.rows) })}>
                        {Object.entries(CHART_LABELS).map(([k, l]) => <option key={k} value={k}>{l}</option>)}
                      </select>
                    )}
                    {(editable || canEdit) && (
                      <button className="icon-btn" aria-label={`Edit ${w.title}`} title="Edit chart: title, type, columns, size, SQL, or ask AI"
                        onClick={() => setEditingChart(w.id)}><Icon name="edit" size={16} /></button>
                    )}
                    {points.length > 1 && (
                      <button className={"icon-btn" + (showHistory ? " on" : "")} aria-pressed={showHistory} aria-label={`History of ${w.title}`}
                        title={showHistory ? "Back to the latest data" : `Show history over ${points.length} refreshes`}
                        onClick={() => toggleHistory(w.id)}><Icon name="history" size={16} /></button>
                    )}
                    <button className="icon-btn" aria-label={`About ${w.title}`} aria-expanded={info === w.id} title="Where this comes from"
                      onClick={() => setInfo(info === w.id ? null : w.id)}><Icon name="info" size={16} /></button>
                    {editable && <CardColors name={w.title} style={w.style ?? {}} onChange={(p) => setLook(w, p)} onApplyAll={lookAll} />}
                    {editable && <TileMenu name={w.title} items={menuItems(w, i)} />}
                  </div>
                </div>
                {info === w.id && (
                  <div className="widget-info small">
                    {w.question && <div><span className="muted">Question:</span> {w.question}</div>}
                    <div><span className="muted">Database:</span> {config.source_name}{d?.ok ? `, ${d.row_count} rows in ${d.elapsed_ms} ms` : ""}</div>
                    <pre className="code">{w.sql}</pre>
                  </div>
                )}
                {loading && !d ? <div className="widget-loading muted small"><span className="spinner" aria-hidden="true" />Running the query…</div>
                  : !d ? <div className="muted small">Not loaded yet.</div>
                  : showHistory ? <HistoryChart widget={w} points={points} height={w.height ?? HEIGHT.default} />
                  : d.ok ? <>
                      {compare && w.chart.type === "table" && <TableChanges columns={d.columns} rows={d.rows} compare={compare} />}
                      <DataChart columns={d.columns} rows={d.rows} chart={w.chart} style={w.style} truncated={d.truncated}
                        height={w.height ?? HEIGHT.default} tableHeight={w.height} compare={compare} spark={spark} />
                    </>
                  : <div className="note note-bad">This chart's query couldn't run: {d.error}</div>}
                {resizer(w)}
              </section>
            );
          })}
        </div>
        {config.widgets.length === 0 && <div className="card muted">No charts yet.{editable ? " Add one below." : ""}</div>}

        {editable && (
          <div className="add-tiles no-print">
            <button className="btn btn-ghost" onClick={addText}><Icon name="plus" size={16} />Add a heading or note</button>
            <span className="muted small">Drag tiles by their <Icon name="grip" size={14} /> handle to rearrange them, and by the bottom-right corner to resize them.</span>
          </div>
        )}

        {editable && (
          <AddByAsking sourceId={config.source_id} sourceName={config.source_name}
            onAdded={(widget, d) => { setWidgets([...config.widgets, widget]); setData((m) => ({ ...m, [widget.id]: d })); }} />
        )}
      </div>

      {editingChart && config.widgets.some((w) => w.id === editingChart) && (
        <ChartEditor reportId={report.id} widget={config.widgets.find((w) => w.id === editingChart)!} data={data[editingChart]}
          onClose={() => setEditingChart(null)} onSave={saveChart} onApplyColorToAll={colorAll}
          onApplyCardToAll={(patch) => commit({ ...config, widgets: config.widgets.map((x) => ({ ...x, style: { ...x.style, ...patch } })) })} />
      )}
      {filterDialog && (
        <FilterColumnsDialog reportId={report.id} widgets={chartWidgets} filter={filterDialog.filter}
          onClose={() => setFilterDialog(null)}
          onSaved={(f) => {
            setConfig((c) => {
              const list = c.filters ?? [];
              return { ...c, filters: list.some((x) => x.id === f.id) ? list.map((x) => (x.id === f.id ? f : x)) : [...list, f] };
            });
            setFilterDialog(null);
            toast(`"${f.label}" filters ${Object.keys(f.columns).length} of ${chartWidgets.length} charts`);
          }} />
      )}
      {publishing && (
        <PublishDialog report={{ ...report, title: title || "Untitled dashboard" }} onClose={() => setPublishing(false)} onPublish={publish} />
      )}
    </div>
  );
}

/** The AI models people may use, with the last-used (or default) one picked. */
function useModels() {
  const [models, setModels] = useState<AIModelPublic[]>([]);
  const [model, setModel] = useState("");
  useEffect(() => {
    aiModelsApi.available().then((list) => {
      setModels(list);
      const last = rememberedModel();
      setModel(list.some((m) => String(m.id) === last) ? last! : String((list.find((m) => m.is_default) ?? list[0])?.id ?? ""));
    }).catch(() => setModels([]));
  }, []);
  return { models, model, setModel };
}

/** Edit mode: add dashboard-wide filters. The AI model maps each one to a column per chart, once. */
/** A chart's numbers over the kept refreshes: one line, or one per category (the 6 largest now). */
function HistoryChart({ widget, points, height }: { widget: Widget; points: HistoryPoint[]; height: number }) {
  const labels = timeLabels(points.map((p) => p.t));
  let columns: string[], rows: Cell[][];
  if (points.some((p) => p.values)) {
    const latest = points[points.length - 1].values ?? {};
    const cats = Object.keys(latest).sort((a, b) => latest[b] - latest[a]).slice(0, 6);
    columns = ["When", ...cats];
    rows = points.map((p, i) => [labels[i], ...cats.map((c) => p.values?.[c] ?? 0)]);
  } else {
    columns = ["When", widget.title || "Value"];
    rows = points.map((p, i) => [labels[i], p.value ?? null]);
  }
  const style = { ...widget.style, sort: "none" as const, horizontal: false, stacked: false };
  return (
    <>
      <DataChart columns={columns} rows={rows} chart={{ type: "line", x: "When", y: columns.slice(1) }} style={style} height={height} fitAxis />
      <p className="chart-changes small muted">History: {points.length} refreshes since {shortDate(points[0].t)}.</p>
    </>
  );
}

function FilterDesigner({ reportId, widgets, filters, onChange, onCustom }: {
  reportId: number; widgets: Widget[]; filters: DashboardFilter[]; onChange: (list: DashboardFilter[]) => void;
  /** Opens the dialog for choosing columns by hand: a filter to edit, or none for a new one. */
  onCustom: (filter?: DashboardFilter) => void;
}) {
  const toast = useToast();
  const { models, model, setModel } = useModels();
  const [label, setLabel] = useState("");
  const [kind, setKind] = useState<DashboardFilter["kind"]>("date");
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [open, setOpen] = useState(filters.length === 0);

  async function map(name: string, k: DashboardFilter["kind"], id?: string) {
    setBusy(id ?? "new");
    setError("");
    try {
      const f = await assistantApi.mapFilter(reportId, { model_id: Number(model), label: name, kind: k, id, widgets });
      onChange(id ? filters.map((x) => (x.id === id ? f : x)) : [...filters, f]);
      toast(`"${f.label}" filters ${Object.keys(f.columns).length} of ${widgets.length} charts`);
      if (!id) setLabel("");
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(null);
    }
  }

  return (
    <section className={"card stack-sm no-print filter-designer" + (open ? "" : " closed")}>
      <button type="button" className="fold-head" aria-expanded={open} onClick={() => setOpen((o) => !o)}>
        <h2 className="h2">Filters{filters.length ? ` (${filters.length})` : ""}</h2>
        {!open && filters.length > 0 && <span className="muted small grow">{filters.map((f) => f.label).join(", ")}</span>}
        <span className="muted small">{open ? "Hide" : "Add or change filters"}</span>
        <Icon name={open ? "up" : "down"} size={16} />
      </button>
      {open && <>
      <p className="muted small">
        Add a date range or a category such as region. The AI model picks the matching column in each chart once, when
        you add the filter; viewers then filter without AI. Charts with no matching column show "Not filtered".
      </p>
      {filters.map((f) => {
        const missing = widgets.filter((w) => !f.columns[w.id]).map((w) => w.title);
        return (
          <div key={f.id} className="filter-row">
            <b>{f.label}</b>
            <span className="muted small grow">
              {f.kind === "date" ? "Date range" : `Category, ${f.options.length} values`}. Filters {widgets.length - missing.length} of {widgets.length} charts
              {missing.length > 0 && missing.length < widgets.length ? ` (not ${missing.join(", ")})` : ""}.
            </span>
            <button className="btn btn-ghost btn-sm" disabled={!!busy || !model || !widgets.length} onClick={() => map(f.label, f.kind, f.id)}
              title="Ask the AI model again, for example after adding charts">{busy === f.id ? "Mapping…" : "Map again"}</button>
            <button className="btn btn-ghost btn-sm" onClick={() => onCustom(f)} title="Choose each chart's column yourself">Edit</button>
            <button className="icon-btn danger" aria-label={`Remove the ${f.label} filter`} title="Remove"
              onClick={() => onChange(filters.filter((x) => x.id !== f.id))}><Icon name="trash" size={16} /></button>
          </div>
        );
      })}
      <form className="row-wrap" onSubmit={(e) => { e.preventDefault(); if (label.trim()) map(label.trim(), kind); }}>
        <label htmlFor="filter-label" className="sr-only">Filter name</label>
        <input id="filter-label" className="grow" value={label} maxLength={60} onChange={(e) => setLabel(e.target.value)}
          placeholder={kind === "date" ? "e.g. Order date" : "e.g. Region"} />
        <select value={kind} onChange={(e) => setKind(e.target.value as DashboardFilter["kind"])} aria-label="Filter type">
          <option value="date">Date range</option>
          <option value="category">Category</option>
        </select>
        <select value={model} onChange={(e) => setModel(e.target.value)} aria-label="AI model" disabled={!models.length}>
          {models.map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}
        </select>
        <button type="submit" className="btn btn-primary" disabled={!!busy || !model || !label.trim() || !widgets.length || filters.length >= 10}>
          {busy === "new" ? "Finding columns…" : "Add filter"}
        </button>
      </form>
      <div className="row-wrap">
        <span className="muted small">Or set it up yourself, choosing the column for each chart:</span>
        <button type="button" className="btn btn-ghost btn-sm" onClick={() => onCustom()} disabled={!widgets.length || filters.length >= 10}>
          Add a custom filter
        </button>
      </div>
      {!models.length && <p className="muted small">The AI option needs an AI model; custom filters don't.</p>}
      </>}
      {error && <div className="alert alert-error">{error}</div>}
    </section>
  );
}

function AddByAsking({ sourceId, sourceName, onAdded }: {
  sourceId: number | null; sourceName: string; onAdded: (w: Widget, d: WidgetData) => void;
}) {
  const toast = useToast();
  const { models, model, setModel } = useModels();
  const [question, setQuestion] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function add(e: React.FormEvent) {
    e.preventDefault();
    if (question.trim().length < 2 || !model) return;
    setBusy(true);
    setError("");
    try {
      const res = await assistantApi.widget({ source_id: sourceId, model_id: Number(model), question: question.trim() });
      onAdded(res.widget, { id: res.widget.id, ok: true, ...res.data });
      setQuestion("");
      toast(`Added "${res.widget.title}"`);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="card stack-sm no-print" onSubmit={add}>
      <h2 className="h2">Add a chart by asking</h2>
      <div className="row-wrap">
        <label htmlFor="add-q" className="sr-only">What should the new chart show?</label>
        <input id="add-q" className="grow" value={question} maxLength={1000} placeholder={`e.g. Monthly total for the last year, from ${sourceName}`}
          onChange={(e) => setQuestion(e.target.value)} />
        <select value={model} onChange={(e) => setModel(e.target.value)} aria-label="AI model" disabled={!models.length}>
          {models.map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}
        </select>
        <button type="submit" className="btn btn-primary" disabled={busy || !model || question.trim().length < 2}>
          {busy ? "Building…" : "Add chart"}
        </button>
      </div>
      {!models.length && <p className="muted small">Adding charts needs an AI model.</p>}
      {error && <div className="alert alert-error">{error}</div>}
    </form>
  );
}
