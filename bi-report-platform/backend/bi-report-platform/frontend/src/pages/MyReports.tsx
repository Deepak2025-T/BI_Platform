import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { errorMessage } from "../api/client";
import { categoriesApi, reportsApi } from "../api/endpoints";
import { reportToolsApi } from "../api/reportTools";
import type { Category, CategoryRef, Report } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import CategoryManager from "../components/CategoryManager";
import Icon from "../components/Icon";
import { scheduleLabel } from "../components/RefreshSchedule";
import { useToast } from "../components/Toast";
import { shortDate } from "../lib/format";

/** "all", "none" (no category) or a category id. */
type Filter = "all" | "none" | number;

interface Group {
  key: string;
  category: CategoryRef | null;
  description?: string;
  reports: Report[];
}

export default function MyReports() {
  const { user, isManager } = useAuth();
  const toast = useToast();
  const navigate = useNavigate();

  async function duplicate(r: Report) {
    try {
      const copy = await reportToolsApi.duplicate(r.id);
      toast(`Made "${copy.title}", your own draft to change.`);
      navigate(`/reports/${copy.id}/edit`);
    } catch (e) { toast(errorMessage(e)); }
  }
  const [reports, setReports] = useState<Report[] | null>(null);
  const [categories, setCategories] = useState<Category[]>([]);
  const [filter, setFilter] = useState<Filter>("all");
  const [search, setSearch] = useState("");
  const [managing, setManaging] = useState(false);

  useEffect(() => {
    reportsApi.list().then(setReports).catch((e) => { toast(errorMessage(e)); setReports([]); });
    categoriesApi.list().then(setCategories).catch(() => setCategories([]));
  }, [toast]);

  const counts = useMemo(() => {
    const m = new Map<Filter, number>();
    for (const r of reports ?? []) m.set(r.category?.id ?? "none", (m.get(r.category?.id ?? "none") ?? 0) + 1);
    return m;
  }, [reports]);

  const groups = useMemo<Group[]>(() => {
    const q = search.trim().toLowerCase();
    const matching = (reports ?? []).filter((r) => !q || r.title.toLowerCase().includes(q) || r.prompt.toLowerCase().includes(q));
    const inGroup = (id: number | null) => matching.filter((r) => (r.category?.id ?? null) === id);
    const all: Group[] = [
      ...categories.map((c) => ({ key: String(c.id), category: c, description: c.description, reports: inGroup(c.id) })),
      { key: "none", category: null, reports: inGroup(null) },
    ];
    if (filter === "all") return all.filter((g) => g.reports.length > 0);
    return all.filter((g) => g.key === String(filter));
  }, [reports, categories, filter, search]);

  // If the selected category is deleted, go back to all reports.
  useEffect(() => {
    if (typeof filter === "number" && !categories.some((c) => c.id === filter)) setFilter("all");
  }, [categories, filter]);

  async function remove(r: Report) {
    if (!window.confirm(`Delete "${r.title}"? This can't be undone.`)) return;
    try {
      await reportsApi.remove(r.id);
      setReports((list) => list?.filter((x) => x.id !== r.id) ?? null);
      toast("Report deleted");
    } catch (e) { toast(errorMessage(e)); }
  }

  function categoriesChanged(next: Category[]) {
    // Reports in a deleted category become uncategorised.
    const ids = new Set(next.map((c) => c.id));
    setReports((list) => list?.map((r) => (r.category && !ids.has(r.category.id) ? { ...r, category: null } : r)) ?? null);
    setCategories(next);
  }

  const pill = (f: Filter, label: string, color?: string) => (
    <button key={String(f)} className={"pill" + (filter === f ? " on" : "")} aria-pressed={filter === f} onClick={() => setFilter(f)}>
      {color && <span className="cat-dot" style={{ background: color }} aria-hidden="true" />}
      {label} <span className="pill-count">{f === "all" ? reports?.length ?? 0 : counts.get(f) ?? 0}</span>
    </button>
  );

  return (
    <div className="page">
      <div className="stack" style={{ maxWidth: 1100 }}>
        <div className="row-between">
          <div>
            <h1 className="h1">Reports</h1>
            <p className="muted small">{isManager ? "All reports in your organisation, by category." : "Your reports, plus everything that has been published, by category."}</p>
          </div>
          <div className="row-wrap">
            <button className="btn btn-ghost btn-lg" onClick={() => setManaging(true)}>Manage categories</button>
            <Link to="/" className="btn btn-primary btn-lg">New report</Link>
          </div>
        </div>

        <div className="row-between">
          <div className="pills" role="group" aria-label="Filter by category">
            {pill("all", "All")}
            {categories.map((c) => pill(c.id, c.name, c.color))}
            {pill("none", "No category")}
          </div>
          <label className="search">
            <Icon name="search" size={16} />
            <span className="sr-only">Search reports</span>
            <input type="search" placeholder="Search reports" value={search} onChange={(e) => setSearch(e.target.value)} />
          </label>
        </div>

        {reports === null ? <div className="card">Loading…</div> : reports.length === 0 ? (
          <div className="card muted">No reports yet. Ask a question on the home page to build one.</div>
        ) : groups.every((g) => g.reports.length === 0) ? (
          <div className="card muted">{search ? "No reports match your search." : "No reports in this category yet. Pick it when you publish a report."}</div>
        ) : groups.map((g) => (
          <section key={g.key} className="card flush cat-group" aria-label={g.category?.name ?? "No category"}
            style={{ ["--cat-color" as string]: g.category?.color ?? "var(--border-strong)" }}>
            <div className="cat-group-head">
              <span className="cat-dot lg" style={{ background: g.category?.color ?? "transparent" }} aria-hidden="true" />
              <div className="grow">
                <h2 className="h2">{g.category?.name ?? "No category"}</h2>
                {g.description && <div className="muted small">{g.description}</div>}
              </div>
              <span className="muted small">{g.reports.length} report{g.reports.length === 1 ? "" : "s"}</span>
            </div>
            <div className="table-scroll">
              <table className="table fixed">
                <colgroup><col /><col className="w-status" /><col className="w-owner" /><col className="w-date" /><col className="w-actions" /></colgroup>
                <thead><tr><th scope="col">Report</th><th scope="col">Status</th><th scope="col">Owner</th><th scope="col">Updated</th><th scope="col"><span className="sr-only">Actions</span></th></tr></thead>
                <tbody>
                  {g.reports.map((r) => {
                    const canEdit = isManager || r.owner_id === user?.id;
                    return (
                      <tr key={r.id}>
                        <td><Link to={`/reports/${r.id}`} className="report-link strong">{r.title}</Link><div className="muted small">{r.prompt}</div></td>
                        <td>
                          <span className={"badge " + (r.status === "published" ? "badge-ok" : "badge-draft")}>{r.status === "published" ? "Published" : "Draft"}</span>
                          {r.refresh_every !== "off" && <div className="muted small refresh-note" title="Auto-refresh">↻ {scheduleLabel(r)}</div>}
                        </td>
                        <td>{r.owner_name}</td>
                        <td className="muted">{shortDate(r.updated_at)}</td>
                        <td className="r nowrap">
                          <Link className="btn btn-ghost btn-sm" to={`/reports/${r.id}`}>Open</Link>{" "}
                          {canEdit && <Link className="btn btn-ghost btn-sm" to={`/reports/${r.id}/edit`}>Edit</Link>}{" "}
                          <button className="btn btn-ghost btn-sm" onClick={() => duplicate(r)}>Duplicate</button>{" "}
                          {canEdit && <button className="btn btn-ghost btn-sm" onClick={() => remove(r)}>Delete</button>}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </section>
        ))}
      </div>

      {managing && <CategoryManager categories={categories} onClose={() => setManaging(false)} onChange={categoriesChanged} />}
    </div>
  );
}
