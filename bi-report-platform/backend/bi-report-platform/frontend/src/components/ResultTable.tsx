import type { Cell } from "../api/types";
import { cellText, columnLabel } from "../lib/format";

interface Props {
  columns: string[];
  rows: Cell[][];
  /** Rows to show; the rest are counted below the table. */
  limit?: number;
  truncated?: boolean;
}

/** Any query result as a table. Numbers are right-aligned. */
export default function ResultTable({ columns, rows, limit = 100, truncated }: Props) {
  const numeric = columns.map((_, i) => rows.length > 0 && rows.every((r) => r[i] === null || typeof r[i] === "number"));
  const shown = rows.slice(0, limit);
  return (
    <div className="table-scroll">
      <table className="table num result-table">
        <thead>
          <tr>{columns.map((c, i) => <th key={c + i} scope="col" className={numeric[i] ? "r" : ""}>{columnLabel(c)}</th>)}</tr>
        </thead>
        <tbody>
          {shown.map((row, ri) => (
            <tr key={ri}>{row.map((v, ci) => <td key={ci} className={numeric[ci] ? "r" : ""}>{cellText(v)}</td>)}</tr>
          ))}
          {rows.length === 0 && <tr><td colSpan={columns.length || 1} className="muted">No rows</td></tr>}
        </tbody>
      </table>
      {(rows.length > limit || truncated) && (
        <p className="muted small pad-x">
          Showing {shown.length} of {rows.length}{truncated ? "+ (results are capped at 500 rows)" : ""} rows.
        </p>
      )}
    </div>
  );
}
