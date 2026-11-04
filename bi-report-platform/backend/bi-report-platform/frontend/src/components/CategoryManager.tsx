import { useState } from "react";
import { errorMessage } from "../api/client";
import { categoriesApi } from "../api/endpoints";
import type { Category, CategoryInput } from "../api/types";
import { ColorPicker, SWATCH_COLORS } from "./Controls";
import Icon from "./Icon";
import Modal from "./Modal";
import { useToast } from "./Toast";

interface Props {
  categories: Category[];
  onClose: () => void;
  /** Called with the new list after any add, edit or delete. */
  onChange: (categories: Category[]) => void;
}

const blank = (n: number): CategoryInput => ({ name: "", description: "", color: SWATCH_COLORS[n % SWATCH_COLORS.length] });
const byName = (a: Category, b: Category) => a.name.localeCompare(b.name);

export default function CategoryManager({ categories, onClose, onChange }: Props) {
  const toast = useToast();
  // null: not editing; 0: the "new category" form; otherwise the id being edited.
  const [editing, setEditing] = useState<number | null>(categories.length === 0 ? 0 : null);
  const [form, setForm] = useState<CategoryInput>(blank(categories.length));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const startNew = () => { setForm(blank(categories.length)); setEditing(0); setError(""); };
  const startEdit = (c: Category) => { setForm({ name: c.name, description: c.description, color: c.color }); setEditing(c.id); setError(""); };

  async function save() {
    if (editing === null || !form.name.trim()) return;
    setBusy(true);
    setError("");
    try {
      const body = { ...form, name: form.name.trim(), description: form.description.trim() };
      if (editing === 0) {
        onChange([...categories, await categoriesApi.create(body)].sort(byName));
        toast(`Category "${body.name}" added`);
      } else {
        const saved = await categoriesApi.update(editing, body);
        onChange(categories.map((c) => (c.id === saved.id ? saved : c)).sort(byName));
        toast("Category saved");
      }
      setEditing(null);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function remove(c: Category) {
    const note = c.report_count ? ` Its ${c.report_count} report${c.report_count === 1 ? "" : "s"} will be kept as "No category".` : "";
    if (!window.confirm(`Delete the category "${c.name}"?${note}`)) return;
    try {
      await categoriesApi.remove(c.id);
      onChange(categories.filter((x) => x.id !== c.id));
      toast("Category deleted");
    } catch (err) {
      toast(errorMessage(err));
    }
  }

  const editor = (
    <div className="box stack-sm">
      <div className="form-grid">
        <label className="field">Name
          <input autoFocus data-autofocus value={form.name} maxLength={60} required placeholder="e.g. Finance"
            onChange={(e) => setForm({ ...form, name: e.target.value })} />
        </label>
        <label className="field">Description (optional)
          <input value={form.description} maxLength={200} placeholder="What belongs here"
            onChange={(e) => setForm({ ...form, description: e.target.value })} />
        </label>
      </div>
      <ColorPicker value={form.color} onChange={(color) => setForm({ ...form, color })} />
      <div className="row-wrap">
        <button type="submit" className="btn btn-primary btn-sm" disabled={busy || !form.name.trim()}>
          {busy ? "Saving…" : editing === 0 ? "Add category" : "Save"}
        </button>
        <button type="button" className="btn btn-ghost btn-sm" onClick={() => setEditing(null)}>Cancel</button>
      </div>
    </div>
  );

  return (
    <Modal size="sm" title="Report categories" onClose={onClose} onSubmit={save} error={error}
      footer={<button type="button" className="btn btn-primary" onClick={onClose}>Done</button>}>
      <div className="stack">
        <p className="muted small">Categories group published reports on the Reports page. Anyone can add one when publishing;
          the person who made a category, or a manager, can change or delete it.</p>

        {categories.length === 0 && editing !== 0 && <p className="muted">No categories yet.</p>}
        <ul className="cat-list">
          {categories.map((c) => editing === c.id ? <li key={c.id}>{editor}</li> : (
            <li key={c.id} className="cat-row">
              <span className="cat-dot" style={{ background: c.color }} aria-hidden="true" />
              <div className="grow">
                <div className="strong">{c.name}</div>
                <div className="muted small">
                  {c.report_count} report{c.report_count === 1 ? "" : "s"}{c.description && `, ${c.description}`}
                </div>
              </div>
              {c.can_edit && (
                <>
                  <button type="button" className="btn btn-ghost btn-sm" onClick={() => startEdit(c)}>Edit</button>
                  <button type="button" className="icon-btn danger" aria-label={`Delete ${c.name}`} title="Delete" onClick={() => remove(c)}>
                    <Icon name="trash" size={16} />
                  </button>
                </>
              )}
            </li>
          ))}
        </ul>

        {editing === 0 ? editor : (
          <button type="button" className="btn btn-ghost self-start" onClick={startNew}><Icon name="plus" size={16} />New category</button>
        )}
      </div>
    </Modal>
  );
}
