import { useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { errorMessage } from "../api/client";
import { templatesApi } from "../api/endpoints";
import type { ReportTemplate, TemplateCategory, TemplateInput } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import BuildFromTemplate from "../components/BuildFromTemplate";
import DomainTiles from "../components/DomainTiles";
import Icon from "../components/Icon";
import TemplateCard from "../components/TemplateCard";
import TemplateForm from "../components/TemplateForm";
import { useToast } from "../components/Toast";
import { CATEGORY_BLURBS, MODULE_LABELS, moduleGroups, TEMPLATE_CATEGORIES } from "../lib/report";

type Filter = "all" | "mine" | "shared" | "builtin";
const FILTERS: [Filter, string][] = [["all", "All"], ["mine", "Mine"], ["shared", "Shared"], ["builtin", "Built-in"]];

type FormState = { template?: ReportTemplate; initial?: Partial<TemplateInput> } | null;

/**
 * A domain with more templates than this opens with its folders shut.
 *
 * Under it, every card fits on a screen or two and opening them all is the friendlier default.
 * Over it - GRC, with more than a hundred - the folders are the point, and a page that expands
 * them all is the wall the hierarchy exists to avoid.
 */
const COLLAPSE_OVER = 24;

export default function Templates() {
  const { user } = useAuth();
  const toast = useToast();
  const navigate = useNavigate();
  // The domain lives in the address, so the Home page can link straight into one and the back
  // button steps out of it the way people expect.
  const [params, setParams] = useSearchParams();
  const domain = (TEMPLATE_CATEGORIES as string[]).includes(params.get("domain") ?? "")
    ? (params.get("domain") as TemplateCategory) : null;
  const [templates, setTemplates] = useState<ReportTemplate[] | null>(null);
  const [filter, setFilter] = useState<Filter>("all");
  const [search, setSearch] = useState("");
  const [form, setForm] = useState<FormState>(null);
  const [building, setBuilding] = useState<ReportTemplate | null>(null);
  // Folders the reader has opened or shut by hand, which beats whatever the default would be.
  const [opened, setOpened] = useState<Record<string, boolean>>({});

  useEffect(() => { templatesApi.list().then(setTemplates).catch((e) => { toast(errorMessage(e)); setTemplates([]); }); }, [toast]);

  const setDomain = (next: TemplateCategory | null) => {
    setOpened({});
    setParams(next ? { domain: next } : {}, { replace: false });
  };

  const q = search.trim().toLowerCase();
  // Searching looks everywhere at once: someone who types "vendor" wants the template, not a
  // lecture about which folder it lives in.
  const searching = q.length > 0;

  const matching = useMemo(() => (templates ?? []).filter((t) => {
    if (filter === "mine" && (t.owner_id !== user?.id || t.is_builtin)) return false;
    if (filter === "shared" && (t.visibility !== "shared" || t.is_builtin)) return false;
    if (filter === "builtin" && !t.is_builtin) return false;
    return !q || [t.name, t.description, t.prompt].some((str) => str.toLowerCase().includes(q));
  }), [templates, filter, q, user]);

  const inDomain = useMemo(() => (domain ? matching.filter((t) => t.category === domain) : matching),
                           [matching, domain]);
  const groups = useMemo(() => moduleGroups(inDomain), [inDomain]);
  const openByDefault = inDomain.length <= COLLAPSE_OVER;
  const isOpen = (module: string) => opened[module] ?? openByDefault;
  const toggle = (module: string) => setOpened((o) => ({ ...o, [module]: !isOpen(module) }));

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
    initial: { name: `${t.name} (copy)`, description: t.description, prompt: t.prompt, color: t.color,
               category: t.category, module: t.module, layout: t.layout, visibility: "private" },
  });
  // Dashboard templates build on a connection; the others start a question on the Ask page.
  const use = (t: ReportTemplate) => (t.layout.kind === "dashboard" ? setBuilding(t) : navigate("/", { state: { template: t } }));

  const cardActions = (t: ReportTemplate) => (
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
  );

  const grid = (list: ReportTemplate[]) => (
    <div className="tpl-grid">
      {list.map((t) => <TemplateCard key={t.id} template={t} onUse={() => use(t)} actions={cardActions(t)} />)}
    </div>
  );

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
            <input type="search" placeholder="Search every template" value={search} onChange={(e) => setSearch(e.target.value)} />
          </label>
        </div>

        {/* Where you are, and the way back up. */}
        {(domain || searching) && (
          <nav className="crumbs" aria-label="Breadcrumb">
            <button className="link-btn" onClick={() => { setDomain(null); setSearch(""); }}>All templates</button>
            {domain && !searching && (
              <>
                <Icon name="arrow" size={13} className="faint" />
                <span className="strong">{domain}</span>
                <span className="muted small">{CATEGORY_BLURBS[domain]}</span>
              </>
            )}
            {searching && (
              <>
                <Icon name="arrow" size={13} className="faint" />
                <span className="strong">{matching.length} match{matching.length === 1 ? "" : "es"} for &ldquo;{search.trim()}&rdquo;</span>
              </>
            )}
          </nav>
        )}

        {templates === null ? <div className="card">Loading…</div>
          : searching ? (
            matching.length ? grid(matching)
              : <p className="muted">Nothing matches &ldquo;{search.trim()}&rdquo;. Try fewer words.</p>
          )
          : !domain ? (
            // Level one: the domains, and how much is in each.
            <DomainTiles templates={matching} onPick={setDomain} onNew={() => setForm({})} />
          )
          : groups.length === 0 ? (
            <p className="muted">No templates here match that filter. <button className="link-btn" onClick={() => setFilter("all")}>Show all</button></p>
          ) : (
            // Level two: the modules inside one domain, each opening to its cards.
            groups.map(([module, list]) => {
              const open = isOpen(module);
              const name = module || "Not in a module";
              return (
                <section key={module || "_"} className="stack tpl-module">
                  <button className={"folder" + (open ? " open" : "")} aria-expanded={open} onClick={() => toggle(module)}>
                    <Icon name={open ? "down" : "arrow"} size={16} className="faint" />
                    <span className="strong">{name}</span>
                    <span className="muted small">{MODULE_LABELS[module] ?? ""}</span>
                    <span className="grow" />
                    <span className="folder-count">{list.length}</span>
                  </button>
                  {open && grid(list)}
                </section>
              );
            })
          )}
      </div>

      {building && <BuildFromTemplate template={building} onClose={() => setBuilding(null)} />}
      {form && <TemplateForm template={form.template} initial={form.initial} onClose={() => setForm(null)} onSaved={saved} />}
    </div>
  );
}
