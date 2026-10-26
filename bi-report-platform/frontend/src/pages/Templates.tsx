import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { errorMessage } from "../api/client";
import { templatesApi } from "../api/endpoints";
import type { ReportTemplate, TemplateInput } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import BuildFromTemplate from "../components/BuildFromTemplate";
import Icon from "../components/Icon";
import TemplateCard from "../components/TemplateCard";
import TemplateForm from "../components/TemplateForm";
import { useToast } from "../components/Toast";

type Filter = "all" | "mine" | "shared" | "builtin";
const FILTERS: [Filter, string][] = [["all", "All"], ["mine", "Mine"], ["shared", "Shared"], ["builtin", "Built-in"]];

type FormState = { template?: ReportTemplate; initial?: Partial<TemplateInput> } | null;

export default function Templates() {
  const { user } = useAuth();
  const toast = useToast();
  const navigate = useNavigate();
  const [templates, setTemplates] = useState<ReportTemplate[] | null>(null);
  const [filter, setFilter] = useState<Filter>("all");
  const [search, setSearch] = useState("");
  const [form, setForm] = useState<FormState>(null);
  const [building, setBuilding] = useState<ReportTemplate | null>(null);

  useEffect(() => { templatesApi.list().then(setTemplates).catch((e) => { toast(errorMessage(e)); setTemplates([]); }); }, [toast]);

  const shown = useMemo(() => {
    const q = search.trim().toLowerCase();
    return (templates ?? []).filter((t) => {
      if (filter === "mine" && (t.owner_id !== user?.id || t.is_builtin)) return false;
      if (filter === "shared" && (t.visibility !== "shared" || t.is_builtin)) return false;
      if (filter === "builtin" && !t.is_builtin) return false;
      return !q || [t.name, t.description, t.prompt].some((s) => s.toLowerCase().includes(q));
    });
  }, [templates, filter, search, user]);

  function saved(t: ReportTemplate) {
    setTemplates((list) => form?.template ? (list ?? []).map((x) => (x.id === t.id ? t : x)) : [t, ...(list ?? [])]);
    toast(form?.template ? "Template saved" : "Template created");
    setForm(null);
  }

  async function remove(t: ReportTemplate) {
    if (!window.confirm(`Delete the template "${t.name}"? Reports already built from it are not affected.`)) return;
    try {
      await templatesApi.remove(t.id);
      setTemplates((list) => list?.filter((x) => x.id !== t.id) ?? null);
      toast("Template deleted");
    } catch (e) { toast(errorMessage(e)); }
  }

  const duplicate = (t: ReportTemplate) => setForm({
    initial: { name: `${t.name} (copy)`, description: t.description, prompt: t.prompt, color: t.color, layout: t.layout, visibility: "private" },
  });
  // Dashboard templates build on a connection; the others start a question on the Ask page.
  const use = (t: ReportTemplate) => (t.layout.kind === "dashboard" ? setBuilding(t) : navigate("/", { state: { template: t } }));

  return (
    <div className="page">
      <div className="stack" style={{ maxWidth: 1100 }}>
        <div className="row-between">
          <div>
            <h1 className="h1">Templates</h1>
            <p className="muted small">Save a question and a layout once, then start new reports from it in one click.</p>
          </div>
          <button className="btn btn-primary btn-lg" onClick={() => setForm({})}><Icon name="plus" />New template</button>
        </div>

        <div className="row-between">
          <div className="pills" role="group" aria-label="Filter templates">
            {FILTERS.map(([k, l]) => (
              <button key={k} className={"pill" + (filter === k ? " on" : "")} aria-pressed={filter === k} onClick={() => setFilter(k)}>{l}</button>
            ))}
          </div>
          <label className="search">
            <Icon name="search" size={16} />
            <span className="sr-only">Search templates</span>
            <input type="search" placeholder="Search templates" value={search} onChange={(e) => setSearch(e.target.value)} />
          </label>
        </div>

        {templates === null ? <div className="card">Loading…</div> : (
          <div className="tpl-grid">
            {shown.map((t) => (
              <TemplateCard key={t.id} template={t} onUse={() => use(t)} actions={
                <>
                  <button className="btn btn-primary btn-sm" onClick={() => use(t)}>Use</button>
                  {t.can_edit && <button className="btn btn-ghost btn-sm" onClick={() => setForm({ template: t })}>Edit</button>}
                  <span className="grow" />
                  <button className="icon-btn" aria-label={`Duplicate ${t.name}`} title="Duplicate" onClick={() => duplicate(t)}>
                    <Icon name="copy" size={16} />
                  </button>
                  {t.can_edit && (
                    <button className="icon-btn danger" aria-label={`Delete ${t.name}`} title="Delete" onClick={() => remove(t)}>
                      <Icon name="trash" size={16} />
                    </button>
                  )}
                </>
              } />
            ))}
            {filter !== "builtin" && !search && (
              <button className="tpl tpl-new" onClick={() => setForm({})}>
                <Icon name="plus" size={22} />
                <span className="strong">New template</span>
                <span className="muted small">Your own question and layout</span>
              </button>
            )}
            {shown.length === 0 && (search || filter === "builtin") && (
              <p className="muted">No templates match. Try another search or filter.</p>
            )}
          </div>
        )}
      </div>

      {building && <BuildFromTemplate template={building} onClose={() => setBuilding(null)} />}
      {form && <TemplateForm template={form.template} initial={form.initial} onClose={() => setForm(null)} onSaved={saved} />}
    </div>
  );
}
