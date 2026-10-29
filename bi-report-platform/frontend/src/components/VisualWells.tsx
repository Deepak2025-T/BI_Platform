import { useState } from "react";
import type { Agg, DateBucket, VisualField, VisualMeasure } from "../api/types";
import { AGG_LABELS, type VisualDef, type WellId, type Wells, canDrop, defaultMeasureName } from "../lib/visuals";
import { FIELD_DRAG_TYPE } from "./VisualFields";
import Icon from "./Icon";

const AGGS: Agg[] = ["sum", "avg", "min", "max", "count", "count_distinct"];
const BUCKETS: DateBucket[] = ["year", "quarter", "month", "week", "day"];

interface Props {
  visual: VisualDef;
  wells: Wells;
  fields: VisualField[];
  /** Date groupings, by column name. */
  buckets: Record<string, DateBucket | undefined>;
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
export default function VisualWells({ visual, wells, fields, buckets, onDrop, onRemove, onAgg, onBucket, onRefuse }: Props) {
  const [over, setOver] = useState<WellId | null>(null);
  const fieldOf = (name: string) => fields.find((f) => f.name === name);

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
                const column = isMeasure ? (item as VisualMeasure).column : (item as string);
                const field = fieldOf(column);
                return (
                  <li key={`${column}-${i}`} className="well-item">
                    {isMeasure ? (
                      <>
                        <select aria-label={`How to summarise ${column}`} value={(item as VisualMeasure).agg}
                          onChange={(e) => onAgg(def.id, i, e.target.value as Agg)}>
                          {AGGS.filter((a) => a === "count" || a === "count_distinct" || field?.is_number)
                            .map((a) => <option key={a} value={a}>{AGG_LABELS[a]}</option>)}
                        </select>
                        <span className="well-item-name" title={defaultMeasureName(item as VisualMeasure)}>
                          {column || "rows"}
                        </span>
                      </>
                    ) : (
                      <>
                        <span className="well-item-name" title={column}>{column}</span>
                        {field?.is_date && (
                          <select aria-label={`How to group ${column}`} value={buckets[column] ?? ""}
                            onChange={(e) => onBucket(column, (e.target.value || undefined) as DateBucket | undefined)}>
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
