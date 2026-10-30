import { useMemo, useState } from "react";
import type { VisualField } from "../api/types";
import Icon from "./Icon";

interface Props {
  fields: VisualField[];
  table: string;
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
export default function VisualFields({ fields, table, onAdd, used }: Props) {
  const [search, setSearch] = useState("");

  const shown = useMemo(() => {
    const q = search.trim().toLowerCase();
    return q ? fields.filter((f) => f.name.toLowerCase().includes(q)) : fields;
  }, [fields, search]);

  const numbers = shown.filter((f) => f.is_number);
  const others = shown.filter((f) => !f.is_number);

  const item = (f: VisualField) => (
    <li key={f.name}>
      <button type="button" draggable className={`field-chip${used.has(f.name) ? " used" : ""}`}
        title={`${f.name} — ${f.type}`}
        onDragStart={(e) => {
          e.dataTransfer.setData(FIELD_DRAG_TYPE, f.name);
          e.dataTransfer.setData("text/plain", f.name);
          e.dataTransfer.effectAllowed = "copy";
        }}
        onClick={() => onAdd(f)}>
        <Icon name={f.is_number ? "trend" : f.is_date ? "clock" : "grid"} size={14} className="faint" />
        <span className="field-name">{f.name}</span>
      </button>
    </li>
  );

  return (
    <div className="stack-sm">
      <label className="field">
        Fields
        <input type="search" value={search} placeholder={`Search ${table.split(".").pop() ?? ""}`}
          onChange={(e) => setSearch(e.target.value)} />
      </label>
      {shown.length === 0 && <p className="muted small">No column matches "{search}".</p>}
      {numbers.length > 0 && (
        <>
          <div className="field-group-label">Numbers</div>
          <ul className="field-list">{numbers.map(item)}</ul>
        </>
      )}
      {others.length > 0 && (
        <>
          <div className="field-group-label">Everything else</div>
          <ul className="field-list">{others.map(item)}</ul>
        </>
      )}
    </div>
  );
}
