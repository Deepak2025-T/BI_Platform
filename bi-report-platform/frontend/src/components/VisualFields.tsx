import { useMemo, useState } from "react";
import type { VisualField } from "../api/types";
import { fieldKey } from "../lib/visuals";
import Icon from "./Icon";

interface Props {
  fields: VisualField[];
  /** The chart's tables, in order. With more than one, fields are grouped under their table. */
  tables: string[];
  /** Dropping is done with the mouse; clicking adds to the first well that fits. */
  onAdd: (field: VisualField) => void;
  /** Which fields are already on the chart, so they can be marked. */
  used: Set<string>;
}

/** The field each drag is carrying. The wells read it back on drop. */
export const FIELD_DRAG_TYPE = "application/x-bi-field";

/**
 * The columns of the chosen table. Drag one onto a well, or click it to drop it on the first well
 * that will take it — dragging is quicker, clicking works with a keyboard.
 */
export default function VisualFields({ fields, tables, onAdd, used }: Props) {
  const [search, setSearch] = useState("");

  const shown = useMemo(() => {
    const q = search.trim().toLowerCase();
    return q ? fields.filter((f) => f.name.toLowerCase().includes(q)) : fields;
  }, [fields, search]);

  const item = (f: VisualField) => {
    const key = fieldKey(f.table, f.name);
    return (
      <li key={key}>
        <button type="button" draggable className={`field-chip${used.has(key) ? " used" : ""}`}
          title={`${f.table}.${f.name} — ${f.type}`}
          onDragStart={(e) => {
            e.dataTransfer.setData(FIELD_DRAG_TYPE, key);
            e.dataTransfer.setData("text/plain", key);
            e.dataTransfer.effectAllowed = "copy";
          }}
          onClick={() => onAdd(f)}>
          <Icon name={f.is_number ? "trend" : f.is_date ? "clock" : "grid"} size={14} className="faint" />
          <span className="field-name">{f.name}</span>
        </button>
      </li>
    );
  };

  /** Numbers first, then everything else: the split people actually look for. */
  const byKind = (list: VisualField[], prefix: string) => {
    const numbers = list.filter((f) => f.is_number);
    const others = list.filter((f) => !f.is_number);
    return (
      <>
        {numbers.length > 0 && <>
          <div className="field-group-label">{prefix}Numbers</div>
          <ul className="field-list">{numbers.map(item)}</ul>
        </>}
        {others.length > 0 && <>
          <div className="field-group-label">{prefix}Everything else</div>
          <ul className="field-list">{others.map(item)}</ul>
        </>}
      </>
    );
  };

  const one = tables.length <= 1;
  return (
    <div className="stack-sm">
      <label className="field">
        Fields
        <input type="search" value={search}
          placeholder={one ? `Search ${tables[0]?.split(".").pop() ?? ""}` : `Search ${tables.length} tables`}
          onChange={(e) => setSearch(e.target.value)} />
      </label>
      {shown.length === 0 && <p className="muted small">No column matches "{search}".</p>}
      {one ? byKind(shown, "") : tables.map((t) => {
        const mine = shown.filter((f) => f.table === t);
        if (mine.length === 0) return null;
        return (
          <section key={t} className="field-table">
            <div className="field-table-name" title={t}>{t.split(".").pop()}</div>
            {byKind(mine, "")}
          </section>
        );
      })}
    </div>
  );
}
