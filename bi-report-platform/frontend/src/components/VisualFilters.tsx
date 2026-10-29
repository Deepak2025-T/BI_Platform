import { useEffect, useState } from "react";
import { visualsApi } from "../api/visuals";
import type { FilterOp, VisualField, VisualFilter } from "../api/types";
import Icon from "./Icon";

/** Operators, grouped by what they suit, with how many values each one needs. */
const TEXT_OPS: [FilterOp, string][] = [
  ["in", "is one of"], ["not_in", "is not one of"], ["=", "is"], ["!=", "is not"],
  ["contains", "contains"], ["starts_with", "starts with"], ["ends_with", "ends with"],
  ["is_null", "is empty"], ["is_not_null", "is not empty"],
];
const NUMBER_OPS: [FilterOp, string][] = [
  ["=", "is"], ["!=", "is not"], [">", "is more than"], [">=", "is at least"],
  ["<", "is less than"], ["<=", "is at most"], ["between", "is between"],
  ["is_null", "is empty"], ["is_not_null", "is not empty"],
];
const DATE_OPS: [FilterOp, string][] = [
  ["between", "is between"], [">=", "is on or after"], ["<=", "is on or before"],
  ["=", "is"], ["is_null", "is empty"], ["is_not_null", "is not empty"],
];

const VALUE_COUNT: Partial<Record<FilterOp, number>> = { is_null: 0, is_not_null: 0, between: 2 };
const valuesNeeded = (op: FilterOp) => VALUE_COUNT[op] ?? 1;

interface Props {
  sourceId: number | null;
  table: string;
  fields: VisualField[];
  filters: VisualFilter[];
  onChange: (filters: VisualFilter[]) => void;
}

/** One filter row: a column, a comparison, and the values it compares against. */
function Row({ filter, field, sourceId, table, onChange, onRemove }: {
  filter: VisualFilter; field: VisualField | undefined; sourceId: number | null; table: string;
  onChange: (f: VisualFilter) => void; onRemove: () => void;
}) {
  const [options, setOptions] = useState<string[] | null>(null);
  const [loading, setLoading] = useState(false);
  const isList = filter.op === "in" || filter.op === "not_in";
  const ops = field?.is_date ? DATE_OPS : field?.is_number ? NUMBER_OPS : TEXT_OPS;
  const values = filter.values ?? [];

  // The values a column holds are only worth fetching for the "is one of" lists.
  useEffect(() => {
    if (!isList || options !== null || loading) return;
    setLoading(true);
    visualsApi.values(sourceId, table, filter.column)
      .then((r) => setOptions(r.values))
      .catch(() => setOptions([]))
      .finally(() => setLoading(false));
  }, [isList, options, loading, sourceId, table, filter.column]);

  const setValue = (i: number, v: string) => {
    const next = [...values];
    next[i] = v;
    onChange({ ...filter, values: next });
  };

  const inputType = field?.is_date ? "date" : field?.is_number ? "number" : "text";

  return (
    <li className="filter-row">
      <div className="filter-head">
        <span className="filter-column" title={filter.column}>{filter.column}</span>
        <select aria-label={`How to compare ${filter.column}`} value={filter.op}
          onChange={(e) => {
            const op = e.target.value as FilterOp;
            // Keep the values that still fit the new comparison.
            const keep = valuesNeeded(op) < 0 ? values : values.slice(0, Math.max(valuesNeeded(op), 0));
            onChange({ ...filter, op, values: keep });
          }}>
          {ops.map(([id, label]) => <option key={id} value={id}>{label}</option>)}
        </select>
        <button type="button" className="icon-btn" title={`Remove the filter on ${filter.column}`} onClick={onRemove}>
          <Icon name="x" size={14} />
        </button>
      </div>

      {isList ? (
        loading ? <span className="muted small">Reading the values…</span>
        : options && options.length > 0 ? (
          <div className="filter-options">
            {options.map((o) => {
              const on = values.map(String).includes(o);
              return (
                <button key={o} type="button" className={`chip-btn sm${on ? " on" : ""}`}
                  onClick={() => onChange({ ...filter,
                    values: on ? values.filter((v) => String(v) !== o) : [...values, o] })}>
                  {o}
                </button>
              );
            })}
          </div>
        ) : <span className="muted small">No values to choose from.</span>
      ) : (
        <div className="filter-values">
          {Array.from({ length: valuesNeeded(filter.op) }, (_, i) => (
            <input key={i} type={inputType} value={String(values[i] ?? "")} aria-label={`Value ${i + 1}`}
              placeholder={filter.op === "between" ? (i === 0 ? "From" : "To") : "Value"}
              onChange={(e) => setValue(i, e.target.value)} />
          ))}
        </div>
      )}
    </li>
  );
}

/** Filters that narrow the rows this one chart reads, before anything is grouped. */
export default function VisualFilters({ sourceId, table, fields, filters, onChange }: Props) {
  const [adding, setAdding] = useState("");

  function add(column: string) {
    const field = fields.find((f) => f.name === column);
    if (!field) return;
    const op: FilterOp = field.is_date ? "between" : field.is_number ? "=" : "in";
    onChange([...filters, { column, op, values: [] }]);
    setAdding("");
  }

  return (
    <div className="stack-sm">
      <ul className="filter-list">
        {filters.map((f, i) => (
          <Row key={`${f.column}-${i}`} filter={f} field={fields.find((x) => x.name === f.column)}
            sourceId={sourceId} table={table}
            onChange={(next) => onChange(filters.map((x, j) => (j === i ? next : x)))}
            onRemove={() => onChange(filters.filter((_, j) => j !== i))} />
        ))}
      </ul>
      <select aria-label="Add a filter" value={adding} onChange={(e) => add(e.target.value)}>
        <option value="">Add a filter…</option>
        {fields.map((f) => <option key={f.name} value={f.name}>{f.name}</option>)}
      </select>
    </div>
  );
}
