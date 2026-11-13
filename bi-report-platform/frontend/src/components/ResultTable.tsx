import { useRef, useState } from "react";
import type { Cell } from "../api/types";
import { cellText, columnLabel } from "../lib/format";
import Icon from "./Icon";

interface Props {
  columns: string[];
  rows: Cell[][];
  /** Rows to show; the rest are counted below the table. */
  limit?: number;
  truncated?: boolean;
  /** Column widths in pixels, by column name. Columns with no width share what's left. */
  widths?: Record<string, number>;
  /** Columns the person has taken off this table. The query still returns them. */
  hiddenColumns?: string[];
  /** Given when the person may change the table: drag a column edge, or take a column off. */
  onColumns?: (patch: { widths?: Record<string, number>; hiddenColumns?: string[] }) => void;
}

/** Narrower than this and a column is a sliver with nothing readable in it. */
const MIN_WIDTH = 60;

/** Any query result as a table. Numbers are right-aligned. */
export default function ResultTable({ columns, rows, limit = 100, truncated, widths = {}, hiddenColumns = [], onColumns }: Props) {
  const hidden = new Set(hiddenColumns);
  const shown = columns.map((c, i) => ({ name: c, i })).filter((c) => !hidden.has(c.name));
  const numeric = columns.map((_, i) => rows.some((r) => typeof r[i] === "number")
                                     && rows.every((r) => r[i] === null || typeof r[i] === "number"));
  const body = rows.slice(0, limit);
  const sized = shown.some((c) => widths[c.name]);
  // The drag in progress, so the width follows the pointer without a re-render per pixel landing
  // in the report's own state.
  const [dragging, setDragging] = useState<{ name: string; width: number } | null>(null);
  const head = useRef<HTMLTableSectionElement>(null);

  const widthOf = (name: string) => (dragging?.name === name ? dragging.width : widths[name]);

  /** Drag a column's right-hand edge. The width is written to the report when the drag ends. */
  const startResize = (name: string, event: React.PointerEvent) => {
    if (!onColumns) return;
    event.preventDefault();
    const cell = (event.target as HTMLElement).closest("th");
    const from = event.clientX;
    const start = widths[name] ?? cell?.getBoundingClientRect().width ?? MIN_WIDTH;
    let last = start;
    const move = (e: PointerEvent) => {
      last = Math.max(MIN_WIDTH, Math.round(start + e.clientX - from));
      setDragging({ name, width: last });
    };
    const done = () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", done);
      setDragging(null);
      // Every visible column is pinned at the width it ended up with, or the ones left loose would
      // all jump the moment the first is fixed.
      const next = { ...widths, [name]: last };
      for (const c of shown) {
        if (!next[c.name]) {
          const w = head.current?.querySelector<HTMLElement>(`[data-col="${CSS.escape(c.name)}"]`);
          if (w) next[c.name] = Math.max(MIN_WIDTH, Math.round(w.getBoundingClientRect().width));
        }
      }
      onColumns({ widths: next });
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", done);
  };

  const hide = (name: string) => onColumns?.({ hiddenColumns: [...hiddenColumns, name] });

  return (
    <div className="table-scroll">
      <table className={"table num result-table" + (sized ? " sized" : "") + (onColumns ? " adjustable" : "")}>
        {sized && (
          <colgroup>
            {shown.map((c) => <col key={c.name} style={widthOf(c.name) ? { width: widthOf(c.name) } : undefined} />)}
          </colgroup>
        )}
        <thead ref={head}>
          <tr>
            {shown.map((c) => (
              <th key={c.name + c.i} scope="col" data-col={c.name} className={numeric[c.i] ? "r" : ""}>
                <span className="th-label">{columnLabel(c.name)}</span>
                {onColumns && (
                  <>
                    {shown.length > 1 && (
                      <button type="button" className="th-hide" title={`Take ${columnLabel(c.name)} off this table`}
                        aria-label={`Take ${columnLabel(c.name)} off this table`} onClick={() => hide(c.name)}>
                        <Icon name="x" size={12} />
                      </button>
                    )}
                    <span className="th-grip" role="separator" aria-label={`Width of ${columnLabel(c.name)}`}
                      title="Drag to set this column's width" onPointerDown={(e) => startResize(c.name, e)} />
                  </>
                )}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {body.map((row, ri) => (
            <tr key={ri}>{shown.map((c) => <td key={c.i} className={numeric[c.i] ? "r" : ""} title={cellText(row[c.i])}>{cellText(row[c.i])}</td>)}</tr>
          ))}
          {rows.length === 0 && <tr><td colSpan={shown.length || 1} className="muted">No rows</td></tr>}
        </tbody>
      </table>
      <div className="row-wrap table-foot">
        {(rows.length > limit || truncated) && (
          <p className="muted small pad-x">
            Showing {body.length} of {rows.length}{truncated ? "+ (results are capped at 500 rows)" : ""} rows.
          </p>
        )}
        {onColumns && hidden.size > 0 && (
          <button type="button" className="link-btn small no-print" onClick={() => onColumns({ hiddenColumns: [] })}>
            {hidden.size} column{hidden.size === 1 ? "" : "s"} taken off — put {hidden.size === 1 ? "it" : "them"} back
          </button>
        )}
        {onColumns && sized && (
          <button type="button" className="link-btn small no-print" onClick={() => onColumns({ widths: {} })}>
            Even column widths
          </button>
        )}
      </div>
    </div>
  );
}
