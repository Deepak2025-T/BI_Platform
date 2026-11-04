import { useMemo, useState } from "react";
import type { Cell } from "../api/types";
import { cellText, columnLabel } from "../lib/format";
import { rowChanges } from "../lib/history";

interface Props {
  columns: string[];
  rows: Cell[][];
  compare: { label: string; columns: string[]; rows: Cell[][] };
}

const SHOW = 8;

/** "Since 22 Oct: 2 new · 1 gone · 3 changed", with the rows behind it. */
export default function TableChanges({ columns, rows, compare }: Props) {
  const [open, setOpen] = useState(false);
  const c = useMemo(() => rowChanges(columns, rows, compare.columns, compare.rows), [columns, rows, compare]);
  const total = c.added.length + c.removed.length + c.changed.length;
  const brief = (r: Cell[]) => r.slice(0, 3).map(cellText).filter(Boolean).join(" · ");

  if (!total) return <p className="table-changes small muted">No changes since {compare.label}.</p>;
  return (
    <div className="table-changes small">
      <button type="button" className="link-btn" aria-expanded={open} onClick={() => setOpen((o) => !o)}>
        Since {compare.label}:{" "}
        {[c.added.length && `${c.added.length} new`, c.removed.length && `${c.removed.length} gone`,
          c.changed.length && `${c.changed.length} changed`].filter(Boolean).join(" · ")}
        {open ? " (hide)" : " (show)"}
      </button>
      {open && (
        <ul className="change-list">
          {c.added.slice(0, SHOW).map((r, i) => <li key={`a${i}`}><span className="chg chg-new">New</span>{brief(r)}</li>)}
          {c.removed.slice(0, SHOW).map((r, i) => <li key={`r${i}`}><span className="chg chg-gone">Gone</span>{brief(r)}</li>)}
          {c.changed.slice(0, SHOW).map((x) => (
            <li key={`c${x.key}`}>
              <span className="chg chg-changed">Changed</span>{x.key}:{" "}
              {x.cells.map((cell) => `${columnLabel(cell.column)} ${cellText(cell.from) || "(empty)"} → ${cellText(cell.to) || "(empty)"}`).join("; ")}
            </li>
          ))}
          {(c.added.length > SHOW || c.removed.length > SHOW || c.changed.length > SHOW) && (
            <li className="muted">Showing the first {SHOW} of each kind.</li>
          )}
        </ul>
      )}
    </div>
  );
}
