import { useEffect, useState } from "react";
import { errorMessage } from "../api/client";
import { aiModelsApi } from "../api/endpoints";
import { reportToolsApi } from "../api/reportTools";
import type { AIModelPublic, ChartType, QueryData, Widget, WidgetData, WidgetSize, WidgetStyle } from "../api/types";
import { rememberedModel } from "../lib/aiModels";
import { columnLabel } from "../lib/format";
import { CHART_LABELS, retype } from "../lib/sources";
import { ColorPicker, Seg } from "./Controls";
import { HEIGHT, HEIGHTS, WIDTHS, clampHeight, hasHeight } from "../lib/tileSize";
import { cardLook } from "../lib/cardColors";
import { CardColorFields } from "./CardColors";
import DataChart from "./DataChart";
import Modal from "./Modal";
import ResultTable from "./ResultTable";

const SIZES: [WidgetSize, string][] = [["auto", "Auto"], ...WIDTHS.map((x) => [x.size, x.label] as [WidgetSize, string])];
type Tab = "chart" | "style" | "data" | "ai";

const FORMATS: [NonNullable<WidgetStyle["format"]>, string][] = [
  ["auto", "Short (1.2M)"], ["full", "Full (1,234,567)"], ["currency", "Currency"], ["percent", "Percent (0.25 = 25%)"],
];
const SORTS: [NonNullable<WidgetStyle["sort"]>, string][] = [["none", "As the query returns"], ["desc", "Largest first"], ["asc", "Smallest first"]];

interface Props {
  reportId: number;
  widget: Widget;
  data?: WidgetData;
  onClose: () => void;
  /** The edited chart, and its data when the editor ran a new query. */
  onSave: (widget: Widget, data: WidgetData | null) => void;
  /** Gives every chart on the dashboard this colour. */
  onApplyColorToAll?: (color: string) => void;
  /** Gives every card on the dashboard these header and card colours. */
  onApplyCardToAll?: (patch: Pick<WidgetStyle, "headBg" | "cardBg">) => void;
}

/** Edits one dashboard chart: how it looks, its SQL, or a change described to the AI model. */
export default function ChartEditor({ reportId, widget, data, onClose, onSave, onApplyColorToAll, onApplyCardToAll }: Props) {
  const [draft, setDraft] = useState<Widget>({ ...widget, size: widget.size ?? "auto" });
  const [result, setResult] = useState<QueryData | null>(data?.ok ? data : null);
  const [sql, setSql] = useState(widget.sql);
  const [ranSql, setRanSql] = useState(widget.sql); // the SQL the preview shows
  const [tab, setTab] = useState<Tab>("chart");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [instruction, setInstruction] = useState("");
  const [note, setNote] = useState("");
  const [models, setModels] = useState<AIModelPublic[]>([]);
  const [model, setModel] = useState("");
  // Charts measure their box when drawn; wait until the dialog is open and has its full width.
  const [ready, setReady] = useState(false);
  useEffect(() => {
    const frame = requestAnimationFrame(() => setReady(true));
    return () => cancelAnimationFrame(frame);
  }, []);

  useEffect(() => {
    aiModelsApi.available().then((list) => {
      setModels(list);
      const last = rememberedModel();
      setModel(list.some((m) => String(m.id) === last) ? last! : String((list.find((m) => m.is_default) ?? list[0])?.id ?? ""));
    }).catch(() => setModels([]));
  }, []);

  const columns = result?.columns ?? [];
  const rows = result?.rows ?? [];
  const numeric = columns.filter((_, i) => rows.length > 0 && rows.every((r) => r[i] === null || typeof r[i] === "number"));
  const sqlChanged = sql.trim() !== ranSql.trim();
  const setChart = (patch: Partial<Widget["chart"]>) => setDraft((d) => ({ ...d, chart: { ...d.chart, ...patch } }));
  const style = draft.style ?? {};
  const setStyle = (patch: Partial<WidgetStyle>) => setDraft((d) => ({ ...d, style: { ...d.style, ...patch } }));
  const isChart = ["bar", "line", "area", "pie"].includes(draft.chart.type);

  async function run() {
    setBusy(true);
    setError("");
    try {
      const res = await reportToolsApi.previewSql(reportId, sql);
      setResult(res);
      setRanSql(sql);
      setDraft((d) => ({ ...d, sql, chart: retype(d.chart, d.chart.type, res.columns, res.rows) }));
      setNote(`The query ran: ${res.row_count}${res.truncated ? "+" : ""} rows in ${res.elapsed_ms} ms.`);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function revise() {
    if (instruction.trim().length < 2 || !model) return;
    setBusy(true);
    setError("");
    try {
      const res = await reportToolsApi.reviseWidget(reportId, { model_id: Number(model), widget: { ...draft, sql: ranSql },
                                                                instruction: instruction.trim() });
      setDraft({ ...res.widget, size: draft.size });
      setResult(res.data);
      setSql(res.widget.sql);
      setRanSql(res.widget.sql);
      const fixes = res.attempts.filter((a) => !a.ok).length;
      setNote(`Changed: "${instruction.trim()}". ${fixes ? `The model needed ${fixes + 1} tries. ` : ""}Check the preview, then save.`);
      setInstruction("");
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  function save() {
    if (sqlChanged) { setTab("data"); setError("Run the changed SQL first, so the chart can be checked."); return; }
    const changedData = ranSql.trim() !== widget.sql.trim();
    onSave({ ...draft, sql: ranSql, title: draft.title.trim() || "Untitled chart" },
           changedData && result ? { id: widget.id, ok: true, ...result } : null);
  }

  return (
    <Modal title={`Edit chart: ${widget.title}`} onClose={onClose} onSubmit={save} error={error}
      footer={
        <>
          <span className="muted small grow">{note}</span>
          <button type="button" className="btn btn-ghost" onClick={onClose}>Cancel</button>
          <button type="submit" className="btn btn-primary" disabled={busy}>Save chart</button>
        </>
      }>
      <div className="stack chart-editor">
        <div className={"chart-preview card widget" + cardLook(style).className} style={cardLook(style).style}>
          <div className="widget-head"><div className="strong">{draft.title || "Untitled chart"}</div></div>
          {result ? (ready && <DataChart columns={result.columns} rows={result.rows} chart={draft.chart} style={style} height={220} truncated={result.truncated} />)
            : <p className="muted small">Run the SQL to see the chart.</p>}
        </div>

        <div className="pills" role="tablist" aria-label="What to edit">
          {([["chart", "Chart"], ["style", "Style"], ["data", "Data (SQL)"], ["ai", "Ask AI to change it"]] as [Tab, string][]).map(([k, l]) => (
            <button key={k} type="button" role="tab" aria-selected={tab === k} className={"pill" + (tab === k ? " on" : "")} onClick={() => setTab(k)}>{l}</button>
          ))}
        </div>

        {tab === "chart" && (
          <div className="stack">
            <div className="form-grid">
              <label className="field">Title
                <input data-autofocus value={draft.title} maxLength={120} onChange={(e) => setDraft({ ...draft, title: e.target.value })} />
              </label>
              <label className="field">Description (shown under the chart's info)
                <input value={draft.question} maxLength={500} onChange={(e) => setDraft({ ...draft, question: e.target.value })} />
              </label>
            </div>
            <fieldset className="group">
              <legend>Chart type</legend>
              <div className="seg-row">
                {(Object.keys(CHART_LABELS) as ChartType[]).map((t) => (
                  <Seg key={t} on={draft.chart.type === t}
                    onClick={() => setDraft((d) => ({ ...d, chart: retype(d.chart, t, columns, rows) }))}>{CHART_LABELS[t]}</Seg>
                ))}
              </div>
            </fieldset>
            {result && ["bar", "line", "area", "pie"].includes(draft.chart.type) && (
              <div className="form-grid">
                <label className="field">Categories or dates (X)
                  <select value={draft.chart.x} onChange={(e) => setChart({ x: e.target.value })}>
                    {columns.filter((c) => !numeric.includes(c)).map((c) => <option key={c} value={c}>{columnLabel(c)}</option>)}
                  </select>
                </label>
                <fieldset className="group">
                  <legend>Values (Y)</legend>
                  <div className="y-picks">
                    {numeric.map((c) => (
                      <label key={c} className="check">
                        <input type={draft.chart.type === "pie" ? "radio" : "checkbox"} name="y" checked={draft.chart.y.includes(c)}
                          onChange={(e) => setChart({ y: draft.chart.type === "pie" ? [c]
                            : e.target.checked ? [...draft.chart.y, c] : draft.chart.y.filter((y) => y !== c) })} />
                        {columnLabel(c)}
                      </label>
                    ))}
                  </div>
                </fieldset>
              </div>
            )}
            {result && draft.chart.type === "kpi" && rows.length > 1 && (
              <div className="alert alert-warn small">
                This query returns {rows.length} rows, but a number shows only the first one. Pick another chart type, or change
                the SQL (or ask AI) to return one total.
              </div>
            )}
            {result && draft.chart.type === "kpi" && (
              <label className="field">Number to show
                <select value={draft.chart.y[0] ?? ""} onChange={(e) => setChart({ y: [e.target.value] })}>
                  {numeric.map((c) => <option key={c} value={c}>{columnLabel(c)}</option>)}
                </select>
              </label>
            )}
            <fieldset className="group">
              <legend>Size on the dashboard</legend>
              <div className="seg-row">
                {SIZES.map(([k, l]) => <Seg key={k} on={draft.size === k} onClick={() => setDraft({ ...draft, size: k })}>{l}</Seg>)}
              </div>
            </fieldset>
            {hasHeight(draft) && (
              <fieldset className="group">
                <legend>Height</legend>
                <div className="seg-row">
                  {HEIGHTS.map(([h, l]) => (
                    <Seg key={h} on={(draft.height ?? HEIGHT.default) === h} onClick={() => setDraft({ ...draft, height: h })}>{l}</Seg>
                  ))}
                  <label className="height-px">
                    <input type="number" min={HEIGHT.min} max={HEIGHT.max} step={HEIGHT.step} value={draft.height ?? HEIGHT.default}
                      aria-label="Height in pixels" onChange={(e) => setDraft({ ...draft, height: Number(e.target.value) })}
                      onBlur={(e) => setDraft({ ...draft, height: clampHeight(Number(e.target.value) || HEIGHT.default) })} /> px
                  </label>
                </div>
              </fieldset>
            )}
          </div>
        )}

        {tab === "style" && (
          <div className="stack">
            <ColorPicker label="Chart colour" value={style.color ?? "#00B4D8"} onChange={(color) => setStyle({ color })} />
            <div className="row-wrap">
              {style.color && <button type="button" className="link-btn" onClick={() => setStyle({ color: undefined })}>Use the default colours</button>}
              {onApplyColorToAll && style.color && (
                <button type="button" className="link-btn" onClick={() => onApplyColorToAll(style.color!)}>Use this colour for every chart</button>
              )}
            </div>
            <div className="box stack-sm">
              <div className="strong small">Card</div>
              <CardColorFields style={style} onChange={setStyle} />
              <div className="row-wrap">
                {(style.headBg || style.cardBg) && (
                  <button type="button" className="link-btn" onClick={() => setStyle({ headBg: undefined, cardBg: undefined })}>Reset card colours</button>
                )}
                {onApplyCardToAll && (style.headBg || style.cardBg) && (
                  <button type="button" className="link-btn" onClick={() => onApplyCardToAll({ headBg: style.headBg, cardBg: style.cardBg })}>
                    Use these card colours on every chart
                  </button>
                )}
              </div>
            </div>
            <div className="form-grid">
              <label className="field">Number format
                <select value={style.format ?? "auto"} onChange={(e) => setStyle({ format: e.target.value as WidgetStyle["format"] })}>
                  {FORMATS.map(([k, l]) => <option key={k} value={k}>{l}</option>)}
                </select>
              </label>
              {draft.chart.type === "kpi" && (
                <label className="field">When this number goes up, that is
                  <select value={style.goodWhen ?? ""} onChange={(e) => setStyle({ goodWhen: (e.target.value || undefined) as WidgetStyle["goodWhen"] })}>
                    <option value="">Neither (grey)</option>
                    <option value="up">Good (green)</option>
                    <option value="down">Bad (red)</option>
                  </select>
                </label>
              )}
              {style.format === "currency" && (
                <label className="field">Currency symbol
                  <input value={style.currency ?? "£"} maxLength={4} onChange={(e) => setStyle({ currency: e.target.value })} />
                </label>
              )}
              {draft.chart.type !== "kpi" && (
                <label className="field">Order
                  <select value={style.sort ?? "none"} onChange={(e) => setStyle({ sort: e.target.value as WidgetStyle["sort"] })}>
                    {SORTS.map(([k, l]) => <option key={k} value={k}>{l}</option>)}
                  </select>
                </label>
              )}
            </div>
            {isChart && (
              <div className="style-checks">
                <label className="check"><input type="checkbox" checked={!!style.showValues} onChange={(e) => setStyle({ showValues: e.target.checked })} />
                  Show values on the chart</label>
                <label className="check"><input type="checkbox" checked={style.legend !== false} onChange={(e) => setStyle({ legend: e.target.checked })} />
                  Show the legend</label>
                {draft.chart.type === "bar" && (
                  <label className="check"><input type="checkbox" checked={!!style.horizontal} onChange={(e) => setStyle({ horizontal: e.target.checked })} />
                    Horizontal bars</label>
                )}
                {(draft.chart.type === "bar" || draft.chart.type === "area") && draft.chart.y.length > 1 && (
                  <label className="check"><input type="checkbox" checked={!!style.stacked} onChange={(e) => setStyle({ stacked: e.target.checked })} />
                    Stack the values</label>
                )}
              </div>
            )}
          </div>
        )}

        {tab === "data" && (
          <div className="stack">
            <label className="field">SQL
              <textarea className="sql-input" rows={8} value={sql} spellCheck={false} onChange={(e) => setSql(e.target.value)} />
              <span className="hint">One SELECT on the tables shared from this database. It's checked before it runs, and only reads data.</span>
            </label>
            <div className="row-wrap">
              <button type="button" className="btn btn-primary btn-sm" onClick={run} disabled={busy || !sql.trim()}>{busy ? "Running…" : "Run"}</button>
              {sqlChanged && <span className="muted small">Changed since the last run.</span>}
            </div>
            {result && <ResultTable columns={result.columns} rows={result.rows} truncated={result.truncated} limit={20} />}
          </div>
        )}

        {tab === "ai" && (
          <div className="stack">
            <label className="field">What should change?
              <textarea rows={3} value={instruction} maxLength={500} placeholder="e.g. Only completed orders, by week, top 5 products, compare with last year"
                onChange={(e) => setInstruction(e.target.value)} />
            </label>
            <div className="row-wrap">
              <select value={model} onChange={(e) => setModel(e.target.value)} aria-label="AI model" disabled={!models.length}>
                {models.map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}
              </select>
              <button type="button" className="btn btn-primary btn-sm" onClick={revise} disabled={busy || !model || instruction.trim().length < 2}>
                {busy ? "Changing…" : "Change chart"}
              </button>
            </div>
            {!models.length && <p className="muted small">Asking for changes needs an AI model.</p>}
          </div>
        )}
      </div>
    </Modal>
  );
}
