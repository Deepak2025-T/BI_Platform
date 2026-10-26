import { useEffect, useMemo, useRef, useState } from "react";
import { Navigate, useNavigate, useParams } from "react-router-dom";
import { reportsApi } from "../api/endpoints";
import { type ChartKind, type NumberFormat, type PaletteId, type ReportConfig, type SectionId, type SectionSize, isDashboard } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { Group, Seg } from "../components/Controls";
import Icon from "../components/Icon";
import CategoryBadge from "../components/CategoryBadge";
import Dashboard from "../components/Dashboard";
import FullscreenButton from "../components/FullscreenButton";
import PublishDialog from "../components/PublishDialog";
import ReportBody, { SECTION_HEIGHT } from "../components/ReportBody";
import TemplateForm from "../components/TemplateForm";
import { useToast } from "../components/Toast";
import { PALETTES, SECTION_LABELS, layoutOf } from "../lib/report";
import { HEIGHT, HEIGHTS, WIDTHS, clampHeight, colsFor, sizeForCols } from "../lib/tileSize";
import { useAutosave } from "../lib/useAutosave";
import { useQueryResult, useReport } from "../lib/useReport";

export default function ReportEditor() {
  const id = Number(useParams().id);
  const navigate = useNavigate();
  const toast = useToast();
  const { user, isManager } = useAuth();
  const { report, error } = useReport(id);
  const [title, setTitle] = useState("");
  const [config, setConfig] = useState<ReportConfig | null>(null);
  const [selected, setSelected] = useState<SectionId>("revenue");
  const [savingTemplate, setSavingTemplate] = useState(false);
  const [publishing, setPublishing] = useState(false);
  const loaded = useRef(false);
  const { result, error: qError } = useQueryResult(config?.params);

  useEffect(() => {
    if (report && !loaded.current && !isDashboard(report.config)) {
      loaded.current = true;
      setTitle(report.title);
      setConfig(report.config);
    }
  }, [report]);

  // Autosave 700 ms after the last change (not on opening), and right away when leaving the editor.
  const draft = useMemo(() => (config ? { title, config } : null), [title, config]);
  const saveState = useAutosave(draft, (d) => reportsApi.update(id, { title: d!.title || "Untitled report", config: d!.config }),
                                !!config);

  if (error) return <div className="page narrow"><div className="alert alert-error">{error}</div></div>;
  if (report && !isManager && report.owner_id !== user?.id) return <Navigate to={`/reports/${id}`} replace />;
  if (report && isDashboard(report.config)) return <Dashboard key={report.id} report={{ ...report, config: report.config }} editable canEdit />;
  if (!report || !config) return <div className="page">Loading report…</div>;

  const set = <K extends keyof ReportConfig>(k: K, v: ReportConfig[K]) => setConfig({ ...config, [k]: v });
  // Functional update: resizing by dragging sends many changes in a row.
  const resize = (sid: SectionId, patch: SectionSize) =>
    setConfig((c) => c && ({ ...c, sizes: { ...c.sizes, [sid]: { ...c.sizes?.[sid], ...patch } } }));
  const current = config.sizes?.[selected] ?? {};
  const move = (i: number, d: number) => {
    const s = [...config.sections];
    const j = i + d;
    if (j < 0 || j >= s.length) return;
    [s[i], s[j]] = [s[j], s[i]];
    set("sections", s);
  };

  async function publish(categoryId: number | null) {
    await reportsApi.update(id, { title, config: config! });
    const published = await reportsApi.publish(id, categoryId);
    toast(published.category
      ? `Published in ${published.category.name}. Everyone in your organisation can open it.`
      : "Published. Everyone in your organisation can open it.");
    navigate(`/reports/${id}`);
  }

  return (
    <div className="editor">
      <div className="toolbar">
        <label htmlFor="rtitle" className="sr-only">Report title</label>
        <input id="rtitle" className="title-input" value={title} onChange={(e) => setTitle(e.target.value)} />
        <span className="muted small" aria-live="polite">
          {saveState === "saving" ? "Saving…" : saveState === "error" ? "Couldn't save. Check your connection." : report.status === "published" ? "Published, changes saved" : "Draft, saved"}
        </span>
        <button className="btn btn-ghost" onClick={() => setSavingTemplate(true)}>Save as template</button>
        <FullscreenButton />
        <button className="btn btn-ghost" onClick={() => navigate(`/reports/${id}`)}>See it as viewers will</button>
        {report.status === "published" && <CategoryBadge category={report.category} />}
        <button className="btn btn-primary" onClick={() => setPublishing(true)}>{report.status === "published" ? "Update published report" : "Publish"}</button>
      </div>

      <div className="editor-grid">
        <aside className="card outline" aria-label="Sections">
          <div className="strong small pad-x">Sections</div>
          {config.sections.map((s, i) => (
            <div key={s} className={"outline-row" + (selected === s ? " on" : "")}>
              <button className="outline-name" onClick={() => setSelected(s)}>{SECTION_LABELS[s]}</button>
              <button className="icon-btn" aria-label={`Move ${SECTION_LABELS[s]} up`} disabled={i === 0} onClick={() => move(i, -1)}><Icon name="up" size={16} /></button>
              <button className="icon-btn" aria-label={`Move ${SECTION_LABELS[s]} down`} disabled={i === config.sections.length - 1} onClick={() => move(i, 1)}><Icon name="down" size={16} /></button>
            </div>
          ))}
        </aside>

        <div className="editor-canvas">
          {qError && <div className="alert alert-error">{qError}</div>}
          {result ? (
            <ReportBody title={title} result={result} config={config} selected={selected} onSelect={setSelected} onResize={resize} />
          ) : (
            <div className="card">Running the saved query…</div>
          )}
        </div>

        <aside className="card panel" aria-label="Section settings">
          <div>
            <div className="muted small">Editing</div>
            <div className="h2">{SECTION_LABELS[selected]}</div>
          </div>

          {selected === "revenue" && (
            <>
              <Group label="Show as">
                {([["grouped", "Bars"], ["stacked", "Stacked"], ["table", "Table"]] as [ChartKind, string][]).map(([k, l]) => (
                  <Seg key={k} on={config.chart === k} onClick={() => set("chart", k)}>{l}</Seg>
                ))}
              </Group>
              <Group label="Colours" column>
                {(Object.keys(PALETTES) as PaletteId[]).map((k) => (
                  <Seg key={k} on={config.palette === k} onClick={() => set("palette", k)} left>
                    <span className="swatches">{PALETTES[k].colors.map((c) => <span key={c} style={{ background: c }} />)}</span>
                    {PALETTES[k].label}
                  </Seg>
                ))}
              </Group>
              <label className="check">
                <input type="checkbox" checked={config.showValues} onChange={(e) => set("showValues", e.target.checked)} />
                Show values on the bars
              </label>
            </>
          )}

          {selected === "products" && (
            <Group label="How many products">
              {([3, 5] as const).map((n) => <Seg key={n} on={config.topN === n} onClick={() => set("topN", n)}>Top {n}</Seg>)}
            </Group>
          )}
          {selected === "kpis" && <p className="muted small">Each tile has an info button that shows viewers where the number comes from.</p>}
          {selected === "insights" && <p className="muted small">Insights are recalculated from the report's numbers every time it loads, and each one names the figures it uses.</p>}

          <Group label="Width">
            {WIDTHS.map((x) => (
              <Seg key={x.size} on={sizeForCols(colsFor(current.size, 12)) === x.size} onClick={() => resize(selected, { size: x.size })}
                title={x.label}>{x.short}</Seg>
            ))}
          </Group>
          {selected === "revenue" && (
            <Group label="Height">
              {HEIGHTS.map(([h, l]) => (
                <Seg key={h} on={(current.height ?? SECTION_HEIGHT) === h} onClick={() => resize(selected, { height: h })}>{l}</Seg>
              ))}
              <label className="height-px">
                <input type="number" min={HEIGHT.min} max={HEIGHT.max} step={HEIGHT.step} value={current.height ?? SECTION_HEIGHT}
                  aria-label="Height in pixels" onChange={(e) => resize(selected, { height: Number(e.target.value) })}
                  onBlur={(e) => resize(selected, { height: clampHeight(Number(e.target.value) || SECTION_HEIGHT) })} /> px
              </label>
            </Group>
          )}
          <p className="muted small">Or drag a section's bottom-right corner on the report.</p>

          <Group label="Numbers">
            {([["short", "$1.3M"], ["full", "$1,286,000"]] as [NumberFormat, string][]).map(([k, l]) => (
              <Seg key={k} on={config.fmt === k} onClick={() => set("fmt", k)}>{l}</Seg>
            ))}
          </Group>
        </aside>
      </div>

      {publishing && (
        <PublishDialog report={{ ...report, title: title || "Untitled report" }} onClose={() => setPublishing(false)} onPublish={publish} />
      )}

      {savingTemplate && (
        <TemplateForm
          initial={{ name: title, description: `Based on the report "${title}"`, prompt: report.prompt, layout: layoutOf(config) }}
          onClose={() => setSavingTemplate(false)}
          onSaved={(t) => { setSavingTemplate(false); toast(`Saved as template "${t.name}". Find it on the Templates page.`); }} />
      )}
    </div>
  );
}
