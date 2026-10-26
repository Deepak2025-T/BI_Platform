import { useState } from "react";
import { errorMessage } from "../api/client";
import { templatesApi } from "../api/endpoints";
import type { ChartKind, NumberFormat, PaletteId, ReportTemplate, SectionId, TemplateInput, TemplateLayout } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { ALL_SECTIONS, DEFAULT_LAYOUT, PALETTES, SECTION_LABELS } from "../lib/report";
import { ColorPicker, Group, SWATCH_COLORS, Seg } from "./Controls";
import Modal from "./Modal";
import TemplateCard from "./TemplateCard";

const EMPTY: TemplateInput = { name: "", description: "", prompt: "", color: SWATCH_COLORS[0], layout: {}, visibility: "private" };

interface Props {
  /** Template to edit. Leave out to create a new one. */
  template?: ReportTemplate;
  /** Starting values for a new template, e.g. from "Save as template" in the editor. */
  initial?: Partial<TemplateInput>;
  onClose: () => void;
  onSaved: (t: ReportTemplate) => void;
}

export default function TemplateForm({ template, initial, onClose, onSaved }: Props) {
  const { isManager } = useAuth();
  const [form, setForm] = useState<TemplateInput>(() =>
    template
      ? { name: template.name, description: template.description, prompt: template.prompt, color: template.color,
          layout: template.layout, visibility: template.visibility }
      : { ...EMPTY, ...initial });
  const [customLayout, setCustomLayout] = useState(Object.keys(form.layout).length > 0);
  const isDashboard = form.layout.kind === "dashboard";
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const set = <K extends keyof TemplateInput>(k: K, v: TemplateInput[K]) => setForm((f) => ({ ...f, [k]: v }));
  // The layout shown in the controls: saved values on top of the standard layout.
  const layout = { ...DEFAULT_LAYOUT, ...form.layout };
  const setLayout = <K extends keyof TemplateLayout>(k: K, v: TemplateLayout[K]) =>
    setForm((f) => ({ ...f, layout: { ...DEFAULT_LAYOUT, ...f.layout, [k]: v } }));
  const toggleSection = (s: SectionId) => {
    const on = layout.sections.includes(s);
    if (on && layout.sections.length === 1) return; // a report needs at least one section
    setLayout("sections", on ? layout.sections.filter((x) => x !== s) : ALL_SECTIONS.filter((x) => x === s || layout.sections.includes(x)));
  };

  const valid = form.name.trim().length > 0 && form.prompt.trim().length >= 3;

  async function save() {
    if (!valid) return;
    setSaving(true);
    setError("");
    const body = { ...form, layout: isDashboard ? form.layout : customLayout ? layout : {} };
    try {
      onSaved(template ? await templatesApi.update(template.id, body) : await templatesApi.create(body));
    } catch (err) {
      setError(errorMessage(err));
      setSaving(false);
    }
  }

  return (
    <Modal title={template ? "Edit template" : "New template"} onClose={onClose} onSubmit={save} error={error}
      footer={
        <>
          <button type="button" className="btn btn-ghost" onClick={onClose}>Cancel</button>
          <button type="submit" className="btn btn-primary" disabled={!valid || saving}>
            {saving ? "Saving…" : template ? "Save changes" : "Create template"}
          </button>
        </>
      }>
      <div className="stack">
        <label className="field">Name
          <input data-autofocus value={form.name} maxLength={80} required onChange={(e) => set("name", e.target.value)}
            placeholder="e.g. Weekly regional sales" />
        </label>
        <label className="field">Short description
          <input value={form.description} maxLength={200} onChange={(e) => set("description", e.target.value)}
            placeholder="What the report shows, in a few words" />
        </label>
        <label className="field">Question
          <textarea rows={3} value={form.prompt} maxLength={2000} required onChange={(e) => set("prompt", e.target.value)}
            placeholder="e.g. Show monthly revenue by region for Q1 2024 and the top 5 products" />
          <span className="hint">This is asked every time someone starts a report from the template.</span>
        </label>

        <ColorPicker value={form.color} onChange={(c) => set("color", c)} />

        <fieldset className="group">
          <legend>Who can use it</legend>
          <div className="seg-row">
            <Seg on={form.visibility === "private"} onClick={() => set("visibility", "private")}>Only me</Seg>
            <Seg on={form.visibility === "shared"} disabled={!isManager || template?.is_builtin}
              onClick={() => set("visibility", "shared")}>Everyone</Seg>
          </div>
          {!isManager && <span className="hint">Ask a manager to share a template with everyone.</span>}
        </fieldset>

        {isDashboard ? (
          <div className="alert alert-info small">This template builds a dashboard of {(form.layout.widgets ?? []).filter((w) => w.kind !== "text").length} ready-made
            charts. Their queries stay as they are; change the charts on the dashboard after building it.</div>
        ) : (
        <div className="box stack">
          <label className="check">
            <input type="checkbox" checked={customLayout} onChange={(e) => setCustomLayout(e.target.checked)} />
            <span><span className="strong">Set the report layout</span><br />
              <span className="hint">Otherwise new reports use the standard layout.</span></span>
          </label>
          {customLayout && (
            <>
              <fieldset className="group">
                <legend>Sections</legend>
                <div className="seg-row wide">
                  {ALL_SECTIONS.map((s) => (
                    <Seg key={s} on={layout.sections.includes(s)} onClick={() => toggleSection(s)}>{SECTION_LABELS[s]}</Seg>
                  ))}
                </div>
              </fieldset>
              <Group label="Chart">
                {([["grouped", "Bars"], ["stacked", "Stacked"], ["table", "Table"]] as [ChartKind, string][]).map(([k, l]) => (
                  <Seg key={k} on={layout.chart === k} onClick={() => setLayout("chart", k)}>{l}</Seg>
                ))}
              </Group>
              <Group label="Colours">
                {(Object.keys(PALETTES) as PaletteId[]).map((k) => (
                  <Seg key={k} on={layout.palette === k} onClick={() => setLayout("palette", k)}>
                    <span className="swatches">{PALETTES[k].colors.map((c) => <span key={c} style={{ background: c }} />)}</span>
                    {PALETTES[k].label}
                  </Seg>
                ))}
              </Group>
              <div className="form-grid">
                <Group label="Numbers">
                  {([["short", "$1.3M"], ["full", "$1,286,000"]] as [NumberFormat, string][]).map(([k, l]) => (
                    <Seg key={k} on={layout.fmt === k} onClick={() => setLayout("fmt", k)}>{l}</Seg>
                  ))}
                </Group>
                <Group label="Products">
                  {([3, 5] as const).map((n) => <Seg key={n} on={layout.topN === n} onClick={() => setLayout("topN", n)}>Top {n}</Seg>)}
                </Group>
              </div>
              <label className="check">
                <input type="checkbox" checked={layout.showValues} onChange={(e) => setLayout("showValues", e.target.checked)} />
                Show values on the bars
              </label>
            </>
          )}
        </div>
        )}
      </div>

      <aside className="modal-preview" aria-label="Preview">
        <div className="muted small">Preview</div>
        <TemplateCard template={{ ...form, layout: isDashboard ? form.layout : customLayout ? layout : {} }} />
      </aside>
    </Modal>
  );
}
