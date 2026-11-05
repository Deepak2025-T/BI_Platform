import { useState } from "react";
import type { Agg, DateBucket, VisualField, VisualMeasure } from "../api/types";
import { AGG_LABELS, type VisualDef, type WellId, type Wells, canDrop, columnOf, defaultMeasureName,
         fieldKey, tableOf } from "../lib/visuals";
import { FIELD_DRAG_TYPE } from "./VisualFields";
import Icon from "./Icon";

const AGGS: Agg[] = ["sum", "avg", "min", "max", "count", "count_distinct"];
// OpenPages Query Service SQL has COUNT and nothing else, and no date functions at all, so those
// choices are not offered rather than offered and then refused by the backend.
const OPENPAGES_AGGS: Agg[] = ["count", "count_distinct"];
const BUCKETS: DateBucket[] = ["year", "quarter", "month", "week", "day"];

interface Props {
  visual: VisualDef;
  wells: Wells;
  fields: VisualField[];
  /** Date groupings, by field key. */
  buckets: Record<string, DateBucket | undefined>;
  /** How many tables the chart reads: with more than one, each field says where it came from. */
  tableCount?: number;
  /** IBM OpenPages can only count, and can't group dates, so it is offered less. */
  openPages?: boolean;
  onDrop: (well: WellId, column: string) => void;
  onRemove: (well: WellId, index: number) => void;
  onAgg: (well: WellId, index: number, agg: Agg) => void;
  onBucket: (column: string, bucket: DateBucket | undefined) => void;
  /** Said out loud when a drop is refused. */
  onRefuse: (reason: string) => void;
}

/**
 * The field wells: Axis, Legend, Values and the rest, depending on the chart.
 *
 * A well only takes what it can draw, so dropping text on Values is refused with a reason rather
 * than accepted and left to fail when the query runs.
 */
export default function VisualWells({ visual, wells, fields, buckets, tableCount = 1, openPages = false,
                                      onDrop, onRemove, onAgg, onBucket, onRefuse }: Props) {
  const [over, setOver] = useState<WellId | null>(null);
  const fieldOf = (key: string) => fields.find((f) => fieldKey(f.table, f.name) === key);

  function handleDrop(well: WellId, e: React.DragEvent) {
    e.preventDefault();
    setOver(null);
    const column = e.dataTransfer.getData(FIELD_DRAG_TYPE) || e.dataTransfer.getData("text/plain");
    const field = fieldOf(column);
    if (!field) return;
    const refusal = canDrop(visual, well, field, wells[well].length);
    if (refusal) { onRefuse(refusal); return; }
    onDrop(well, column);
  }

  return (
    <div className="stack-sm">
      {visual.wells.map((def) => {
        const held = wells[def.id];
        const isMeasure = def.accepts === "measure";
        return (
          <div key={def.id} className={`well${over === def.id ? " over" : ""}`}
            onDragOver={(e) => { e.preventDefault(); e.dataTransfer.dropEffect = "copy"; setOver(def.id); }}
            onDragLeave={() => setOver((w) => (w === def.id ? null : w))}
            onDrop={(e) => handleDrop(def.id, e)}>
            <div className="well-label">
              {def.label}
              {def.required && held.length === 0 && <span className="well-required" title="Needed to draw">needed</span>}
            </div>

            {held.length === 0 && <div className="well-empty">{def.hint ?? "Drag a field here"}</div>}

            <ul className="well-items">
              {held.map((item, i) => {
                const key = isMeasure ? (item as VisualMeasure).column : (item as string);
                const field = fieldOf(key);
                const column = columnOf(key);
                return (
                  <li key={`${key}-${i}`} className="well-item">
                    {isMeasure ? (
                      <>
                        <select aria-label={`How to summarise ${column}`} value={(item as VisualMeasure).agg}
                          onChange={(e) => onAgg(def.id, i, e.target.value as Agg)}>
                          {(openPages ? OPENPAGES_AGGS : AGGS)
                            .filter((a) => a === "count" || a === "count_distinct" || field?.is_number)
                            .map((a) => <option key={a} value={a}>{AGG_LABELS[a]}</option>)}
                        </select>
                        <span className="well-item-name" title={defaultMeasureName(item as VisualMeasure)}>
                          {column || "rows"}
                          {tableCount > 1 && key && <span className="well-item-table"> · {tableOf(key).split(".").pop()}</span>}
                        </span>
                      </>
                    ) : (
                      <>
                        <span className="well-item-name" title={key}>
                          {column}
                          {tableCount > 1 && <span className="well-item-table"> · {tableOf(key).split(".").pop()}</span>}
                        </span>
                        {field?.is_date && !openPages && (
                          <select aria-label={`How to group ${column}`} value={buckets[key] ?? ""}
                            onChange={(e) => onBucket(key, (e.target.value || undefined) as DateBucket | undefined)}>
                            <option value="">Each value</option>
                            {BUCKETS.map((b) => <option key={b} value={b}>By {b}</option>)}
                          </select>
                        )}
                      </>
                    )}
                    <button type="button" className="icon-btn" title={`Remove ${column}`}
                      onClick={() => onRemove(def.id, i)}>
                      <Icon name="x" size={14} />
                    </button>
                  </li>
                );
              })}
            </ul>
          </div>
        );
      })}
    </div>
  );
}
