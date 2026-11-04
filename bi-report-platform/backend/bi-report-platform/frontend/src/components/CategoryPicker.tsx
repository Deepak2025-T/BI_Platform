import { useState } from "react";
import { errorMessage } from "../api/client";
import { categoriesApi } from "../api/endpoints";
import type { Category } from "../api/types";
import { ColorPicker, SWATCH_COLORS } from "./Controls";

interface Props {
  categories: Category[];
  value: number | null;
  onChange: (id: number | null) => void;
  /** Called after a new category is created here; it is also selected. */
  onCreated: (c: Category) => void;
}

/** Choose a report's category, or make a new one without leaving the dialog. */
export default function CategoryPicker({ categories, value, onChange, onCreated }: Props) {
  const [adding, setAdding] = useState(categories.length === 0);
  const [name, setName] = useState("");
  const [color, setColor] = useState(SWATCH_COLORS[categories.length % SWATCH_COLORS.length]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function add() {
    if (!name.trim() || busy) return;
    setBusy(true);
    setError("");
    try {
      const c = await categoriesApi.create({ name: name.trim(), description: "", color });
      onCreated(c);
      onChange(c.id);
      setName("");
      setAdding(false);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  const option = (id: number | null, label: string, color?: string, count?: number) => (
    <label key={id ?? "none"} className={"cat-option" + (value === id ? " on" : "")}>
      <input type="radio" name="category" checked={value === id} onChange={() => onChange(id)} />
      {color ? <span className="cat-dot" style={{ background: color }} aria-hidden="true" /> : <span className="cat-dot empty" aria-hidden="true" />}
      <span className="grow">{label}</span>
      {count !== undefined && <span className="muted small">{count} report{count === 1 ? "" : "s"}</span>}
    </label>
  );

  return (
    <fieldset className="group stack-sm">
      <legend>Category</legend>
      <div className="cat-options" role="radiogroup">
        {categories.map((c) => option(c.id, c.name, c.color, c.report_count))}
        {option(null, "No category")}
      </div>

      {adding ? (
        <div className="box stack-sm">
          <label className="field">New category name
            <input value={name} maxLength={60} placeholder="e.g. Finance, Sales, Weekly"
              onChange={(e) => setName(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); add(); } }} />
          </label>
          <ColorPicker value={color} onChange={setColor} />
          {error && <div className="alert alert-error">{error}</div>}
          <div className="row-wrap">
            <button type="button" className="btn btn-primary btn-sm" disabled={!name.trim() || busy} onClick={add}>
              {busy ? "Adding…" : "Add category"}
            </button>
            {categories.length > 0 && <button type="button" className="btn btn-ghost btn-sm" onClick={() => setAdding(false)}>Cancel</button>}
          </div>
        </div>
      ) : (
        <button type="button" className="link-btn self-start" onClick={() => setAdding(true)}>+ New category</button>
      )}
    </fieldset>
  );
}
