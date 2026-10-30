import type { JoinOp, JoinType, VisualField, VisualJoin } from "../api/types";
import Icon from "./Icon";

/** What each kind of join keeps, said the way it reads on screen. */
const TYPES: [JoinType, string, string][] = [
  ["inner", "Only matching rows", "Rows that match on both sides"],
  ["left", "Keep every row of the first table", "Matched or not"],
  ["right", "Keep every row of this table", "Matched or not"],
  ["full", "Keep every row of both", "Nothing is dropped"],
];

const OPS: [JoinOp, string][] = [
  ["=", "equals"], ["!=", "is not"], [">", "is more than"], [">=", "is at least"],
  ["<", "is less than"], ["<=", "is at most"],
];

const short = (table: string) => table.split(".").pop() ?? table;

interface Props {
  /** Every table on the chart, the first one first. */
  tables: string[];
  joins: VisualJoin[];
  fieldsByTable: Record<string, VisualField[]>;
  onChange: (joins: VisualJoin[]) => void;
  onRemove: (table: string) => void;
}

/**
 * How each joined table is matched to the rest of the chart.
 *
 * A join can only be matched against a table already on the chart — the first one, or one joined
 * before it — so the tables always line up in one chain and there is never a table hanging loose.
 * The conditions start from the database's own foreign keys where it has them, and are editable:
 * matching on something other than a key, or with "is more than" rather than "equals", is fair
 * game and is what date bands and price tiers need.
 */
export default function VisualJoins({ tables, joins, fieldsByTable, onChange, onRemove }: Props) {
  const patch = (i: number, change: Partial<VisualJoin>) =>
    onChange(joins.map((j, n) => (n === i ? { ...j, ...change } : j)));

  const setCondition = (i: number, n: number, change: Partial<VisualJoin["on"][number]>) =>
    patch(i, { on: joins[i].on.map((c, k) => (k === n ? { ...c, ...change } : c)) });

  function addCondition(i: number) {
    const mine = fieldsByTable[joins[i].table] ?? [];
    const earlier = tables[0];
    const theirs = fieldsByTable[earlier] ?? [];
    patch(i, { on: [...joins[i].on, {
      left: { table: joins[i].table, column: mine[0]?.name ?? "" },
      op: "=",
      right: { table: earlier, column: theirs[0]?.name ?? "" },
    }] });
  }

  return (
    <div className="stack-sm">
      {joins.map((join, i) => {
        // Only tables already on the chart above this one can be matched against.
        const earlier = tables.slice(0, i + 1);
        const mine = fieldsByTable[join.table] ?? [];
        return (
          <div key={join.table} className="join">
            <div className="join-head">
              <span className="strong">{short(join.table)}</span>
              <button type="button" className="icon-btn" title={`Remove ${join.table}`}
                aria-label={`Remove ${join.table}`} onClick={() => onRemove(join.table)}>
                <Icon name="x" size={14} />
              </button>
            </div>
            <label className="field">
              <span className="sr-only">How {short(join.table)} is joined</span>
              <select value={join.type} aria-label={`How ${short(join.table)} is joined`}
                onChange={(e) => patch(i, { type: e.target.value as JoinType })}>
                {TYPES.map(([id, label, why]) => <option key={id} value={id} title={why}>{label}</option>)}
              </select>
            </label>

            {join.on.map((c, n) => (
              <div key={n} className="join-row">
                <select aria-label="Column on this table" value={c.left.column}
                  onChange={(e) => setCondition(i, n, { left: { table: join.table, column: e.target.value } })}>
                  {mine.map((f) => <option key={f.name} value={f.name}>{f.name}</option>)}
                </select>
                <select aria-label="How they are matched" className="join-op" value={c.op}
                  onChange={(e) => setCondition(i, n, { op: e.target.value as JoinOp })}>
                  {OPS.map(([id, label]) => <option key={id} value={id}>{label}</option>)}
                </select>
                <select aria-label="Column on the other table"
                  value={`${c.right.table ?? tables[0]}::${c.right.column}`}
                  onChange={(e) => {
                    const [table, column] = e.target.value.split("::");
                    setCondition(i, n, { right: { table, column } });
                  }}>
                  {earlier.flatMap((t) => (fieldsByTable[t] ?? []).map((f) => (
                    <option key={`${t}::${f.name}`} value={`${t}::${f.name}`}>{short(t)}.{f.name}</option>
                  )))}
                </select>
                {join.on.length > 1 && (
                  <button type="button" className="icon-btn" aria-label="Remove this condition"
                    onClick={() => patch(i, { on: join.on.filter((_, k) => k !== n) })}>
                    <Icon name="x" size={14} />
                  </button>
                )}
              </div>
            ))}

            {join.on.length === 0 && <p className="hint note-bad">Say how {short(join.table)} matches the chart.</p>}
            {join.on.length < 4 && (
              <button type="button" className="btn btn-ghost btn-sm" onClick={() => addCondition(i)}>
                <Icon name="plus" size={14} />And…
              </button>
            )}
          </div>
        );
      })}
    </div>
  );
}
