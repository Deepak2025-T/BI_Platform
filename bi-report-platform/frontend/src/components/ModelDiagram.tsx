import { useMemo, useRef, useState } from "react";
import type { DataModelDetail, ModelEntity } from "../api/types";
import {
  BOX_PADDING, FIELDS_SHOWN, FIELD_HEIGHT, HEADER_HEIGHT, type Box,
  layout, linkPath, matches, neighbours, selfPath,
} from "../lib/dataModel";
import Icon from "./Icon";

interface Props {
  model: DataModelDetail;
  search: string;
  /** The entity whose detail panel is open, if any. */
  selected: string;
  onSelect: (name: string) => void;
}

const ZOOMS = [0.5, 0.65, 0.8, 1, 1.25, 1.5];

/**
 * The object model drawn as boxes and the lines between them.
 *
 * Lines run parent to child, because that is what an OpenPages relationship is: the child sits
 * under the parent in the hierarchy, and that is the join. An arrowhead points at the child so the
 * direction can be read without clicking anything.
 *
 * Boxes can be dragged and the canvas panned and zoomed, but none of it is saved - the model is
 * shipped and the same for everyone, so the layout is worked out fresh each time rather than
 * becoming one more thing to keep in step.
 */
export default function ModelDiagram({ model, search, selected, onSelect }: Props) {
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [moved, setMoved] = useState<Record<string, { dx: number; dy: number }>>({});
  const [zoom, setZoom] = useState(1);
  const drag = useRef<{ name: string; startX: number; startY: number; dx: number; dy: number } | null>(null);

  const base = useMemo(() => layout(model, expanded), [model, expanded]);
  const boxes = useMemo(
    () => base.boxes.map((b) => {
      const at = moved[b.name];
      return at ? { ...b, x: b.x + at.dx, y: b.y + at.dy } : b;
    }),
    [base, moved],
  );
  const byName: Record<string, Box> = useMemo(
    () => Object.fromEntries(boxes.map((b) => [b.name, b])), [boxes],
  );

  const near = selected ? neighbours(model.relationships, selected) : null;
  const found = useMemo(
    () => new Set(model.entities.filter((e) => matches(e, search)).map((e) => e.name)),
    [model, search],
  );

  const toggle = (name: string) => setExpanded((set) => {
    const next = new Set(set);
    if (!next.delete(name)) next.add(name);
    return next;
  });

  const startDrag = (e: React.PointerEvent, name: string) => {
    if (e.button !== 0) return;
    const at = moved[name] ?? { dx: 0, dy: 0 };
    drag.current = { name, startX: e.clientX, startY: e.clientY, ...at };
    (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
  };

  const onDrag = (e: React.PointerEvent) => {
    const d = drag.current;
    if (!d) return;
    setMoved((all) => ({
      ...all,
      [d.name]: { dx: d.dx + (e.clientX - d.startX) / zoom, dy: d.dy + (e.clientY - d.startY) / zoom },
    }));
  };

  const endDrag = () => { drag.current = null; };

  const stepZoom = (by: number) => {
    const i = ZOOMS.indexOf(zoom);
    setZoom(ZOOMS[Math.min(ZOOMS.length - 1, Math.max(0, (i < 0 ? 3 : i) + by))]);
  };

  // The surface grows with the drawing so the scrollbars are real rather than clipped content.
  const spread = boxes.reduce(
    (max, b) => ({ w: Math.max(max.w, b.x + b.width + 48), h: Math.max(max.h, b.y + b.height + 48) }),
    { w: base.width, h: base.height },
  );

  return (
    <div className="model-canvas">
      <div className="model-zoom">
        <button type="button" className="icon-btn" onClick={() => stepZoom(-1)}
          disabled={zoom === ZOOMS[0]} aria-label="Zoom out">&minus;</button>
        <span className="muted small" aria-live="polite">{Math.round(zoom * 100)}%</span>
        <button type="button" className="icon-btn" onClick={() => stepZoom(1)}
          disabled={zoom === ZOOMS[ZOOMS.length - 1]} aria-label="Zoom in">+</button>
        <button type="button" className="link-btn"
          onClick={() => { setMoved({}); setZoom(1); setExpanded(new Set()); }}>Reset the layout</button>
      </div>

      <div className="model-surface">
        <div className="model-stage" style={{ width: spread.w * zoom, height: spread.h * zoom }}>
          <div className="model-scale" style={{ width: spread.w, height: spread.h, transform: `scale(${zoom})` }}>
            <svg className="model-links" width={spread.w} height={spread.h} aria-hidden="true">
              <defs>
                <marker id="model-arrow" viewBox="0 0 10 10" refX="9" refY="5"
                  markerWidth="7" markerHeight="7" orient="auto-start-reverse">
                  <path d="M 0 0 L 10 5 L 0 10 z" />
                </marker>
              </defs>
              {model.relationships.map((r) => {
                const from = byName[r.parent];
                const to = byName[r.child];
                if (!from || !to) return null;
                const on = !near || (near.has(r.parent) && near.has(r.child));
                const key = `${r.parent}>${r.child}`;
                if (r.self) {
                  return <path key={key} className={"model-link self" + (on ? "" : " off")}
                    d={selfPath(from)} markerEnd="url(#model-arrow)" />;
                }
                return <path key={key} className={"model-link" + (on ? "" : " off")}
                  d={linkPath(from, to)} markerEnd="url(#model-arrow)" />;
              })}
            </svg>

            {boxes.map((b) => (
              <EntityBox key={b.name} box={b}
                dim={(near !== null && !near.has(b.name)) || (!!search && !found.has(b.name))}
                picked={selected === b.name}
                expanded={expanded.has(b.name)}
                onToggle={() => toggle(b.name)}
                onSelect={() => onSelect(selected === b.name ? "" : b.name)}
                onPointerDown={(e) => startDrag(e, b.name)}
                onPointerMove={onDrag}
                onPointerUp={endDrag}
              />
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function EntityBox({ box, dim, picked, expanded, onToggle, onSelect, onPointerDown, onPointerMove, onPointerUp }: {
  box: Box; dim: boolean; picked: boolean; expanded: boolean;
  onToggle: () => void; onSelect: () => void;
  onPointerDown: (e: React.PointerEvent) => void;
  onPointerMove: (e: React.PointerEvent) => void;
  onPointerUp: () => void;
}) {
  const e: ModelEntity = box.entity;
  const shown = expanded ? e.fields : e.fields.slice(0, FIELDS_SHOWN);
  const rest = e.fields.length - shown.length;
  // Three states worth telling apart: not checked (no connection), not installed here, installed
  // but not shared with this app - only the last of which a manager can fix on the Connections page.
  const state = e.shared === null ? "unknown" : e.shared ? "ok" : e.exists ? "unshared" : "missing";
  const why = {
    unknown: "Pick a database to see this type's fields.",
    ok: "Shared with this app, so reports can use it.",
    unshared: "This type exists in OpenPages but isn't shared with this app yet.",
    missing: "This type isn't installed in this OpenPages environment.",
  }[state];

  return (
    <div
      className={`model-box ${state}` + (picked ? " picked" : "") + (dim ? " dim" : "")}
      style={{ left: box.x, top: box.y, width: box.width, minHeight: box.height }}
    >
      <div className="model-box-head" onPointerDown={onPointerDown} onPointerMove={onPointerMove}
        onPointerUp={onPointerUp} onPointerCancel={onPointerUp}>
        <button type="button" className="model-box-name" onClick={onSelect} title={why}
          aria-pressed={picked}>
          <Icon name="grid" size={14} />
          <span>{e.name}</span>
        </button>
        {e.self_nesting && <span className="model-tag" title="This type nests under itself">tree</span>}
      </div>

      {shown.length > 0 && (
        <ul className="model-fields" style={{ paddingBottom: BOX_PADDING / 2 }}>
          {shown.map((f) => (
            <li key={f.name} style={{ height: FIELD_HEIGHT }}
              title={f.values.length ? `${f.type} · ${f.values.join(", ")}` : f.type}>
              <span className="model-field-name">{f.name}</span>
              <span className="model-field-type">{f.type}</span>
            </li>
          ))}
          {rest > 0 && (
            <li style={{ height: FIELD_HEIGHT }}>
              <button type="button" className="link-btn" onClick={onToggle}>{rest} more fields</button>
            </li>
          )}
          {expanded && e.fields.length > FIELDS_SHOWN && (
            <li style={{ height: FIELD_HEIGHT }}>
              <button type="button" className="link-btn" onClick={onToggle}>Show fewer</button>
            </li>
          )}
        </ul>
      )}

      {shown.length === 0 && (
        <div className="model-empty" style={{ height: HEADER_HEIGHT }}>
          {state === "unknown" ? "No database chosen" : state === "missing" ? "Not installed here"
            : state === "unshared" ? "Not shared with this app" : "No fields read"}
        </div>
      )}
    </div>
  );
}
