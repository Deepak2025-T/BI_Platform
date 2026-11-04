import type { DataModelDetail, ModelEntity, ModelRelationship } from "../api/types";

/**
 * Laying out an OpenPages object model.
 *
 * The model is a hierarchy, not a star schema: a child is related to its parent by sitting under
 * it. So it draws as rows, one per level, rather than as a fact table ringed by dimensions. Each
 * entity's depth comes from the server, which has already dealt with the namespaces that relate a
 * type back to one above it.
 *
 * Positions are worked out, not stored. The diagram is a view of a shipped model that nobody here
 * can change, so there is nothing about a hand-moved box worth keeping; boxes can still be dragged
 * for a closer look, and the layout comes back on reload.
 */

export const BOX_WIDTH = 216;
export const HEADER_HEIGHT = 34;
export const FIELD_HEIGHT = 19;
export const BOX_PADDING = 10;
const GAP_X = 48;
const GAP_Y = 64;
const MARGIN = 32;

/** Fields listed on a box before it is expanded. Enough to recognise the type, not a wall of text. */
export const FIELDS_SHOWN = 6;

export interface Box {
  name: string;
  entity: ModelEntity;
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface Layout {
  boxes: Box[];
  byName: Record<string, Box>;
  width: number;
  height: number;
}

export function boxHeight(entity: ModelEntity, expanded: boolean): number {
  const count = expanded ? entity.fields.length : Math.min(entity.fields.length, FIELDS_SHOWN);
  const more = !expanded && entity.fields.length > FIELDS_SHOWN ? 1 : 0;
  return HEADER_HEIGHT + (count + more) * FIELD_HEIGHT + (count + more ? BOX_PADDING : 4);
}

/**
 * Rows by depth, entities ordered within a row so a child sits near its parent.
 *
 * `expanded` holds the entities whose full field list is showing; they are taller, so the row
 * below has to move down, which is why the layout is recomputed rather than nudged.
 */
export function layout(detail: DataModelDetail, expanded: Set<string> = new Set()): Layout {
  const rows = new Map<number, ModelEntity[]>();
  for (const e of detail.entities) {
    const row = rows.get(e.depth) ?? [];
    row.push(e);
    rows.set(e.depth, row);
  }
  const depths = [...rows.keys()].sort((a, b) => a - b);
  const order = new Map(detail.entities.map((e, i) => [e.name, i]));

  const boxes: Box[] = [];
  let y = MARGIN;
  let width = 0;
  for (const depth of depths) {
    const row = (rows.get(depth) ?? []).slice().sort((a, b) => {
      // Keep children under the parent they belong to, then fall back to the model's own order so
      // two runs of the same model always draw the same way.
      const pa = a.parents[0] ?? "";
      const pb = b.parents[0] ?? "";
      if (pa !== pb) return (order.get(pa) ?? -1) - (order.get(pb) ?? -1);
      return (order.get(a.name) ?? 0) - (order.get(b.name) ?? 0);
    });
    let x = MARGIN;
    let tallest = 0;
    for (const entity of row) {
      const height = boxHeight(entity, expanded.has(entity.name));
      boxes.push({ name: entity.name, entity, x, y, width: BOX_WIDTH, height });
      x += BOX_WIDTH + GAP_X;
      tallest = Math.max(tallest, height);
    }
    width = Math.max(width, x - GAP_X + MARGIN);
    y += tallest + GAP_Y;
  }
  return {
    boxes,
    byName: Object.fromEntries(boxes.map((b) => [b.name, b])),
    width: Math.max(width, 640),
    height: Math.max(y - GAP_Y + MARGIN, 400),
  };
}

/**
 * The line from a parent box to a child box, as an SVG path.
 *
 * It leaves the bottom of the parent and arrives at the top of the child when the child is below,
 * and goes side to side otherwise, so a relationship that points back up the model is still
 * followable instead of cutting through the boxes between.
 */
export function linkPath(from: Box, to: Box): string {
  const fx = from.x + from.width / 2;
  const tx = to.x + to.width / 2;
  if (to.y > from.y + from.height - 1) {
    const fy = from.y + from.height;
    const ty = to.y;
    const mid = fy + (ty - fy) / 2;
    return `M ${fx} ${fy} C ${fx} ${mid}, ${tx} ${mid}, ${tx} ${ty}`;
  }
  const fromRight = tx >= fx;
  const fx2 = fromRight ? from.x + from.width : from.x;
  const tx2 = fromRight ? to.x : to.x + to.width;
  const fy = from.y + from.height / 2;
  const ty = to.y + to.height / 2;
  const bend = fromRight ? 40 : -40;
  return `M ${fx2} ${fy} C ${fx2 + bend} ${fy}, ${tx2 - bend} ${ty}, ${tx2} ${ty}`;
}

/** A box that loops back to itself, drawn as a small arc off its right-hand edge. */
export function selfPath(box: Box): string {
  const x = box.x + box.width;
  const y = box.y + HEADER_HEIGHT / 2;
  return `M ${x} ${y} C ${x + 34} ${y - 22}, ${x + 34} ${y + 22}, ${x} ${y + 14}`;
}

/** Entities a search box should leave showing, matched on the type name or any of its fields. */
export function matches(entity: ModelEntity, search: string): boolean {
  const q = search.trim().toLowerCase();
  if (!q) return true;
  return entity.name.toLowerCase().includes(q)
    || entity.fields.some((f) => f.name.toLowerCase().includes(q));
}

/** Everything one entity touches, for highlighting when a box is picked. */
export function neighbours(relationships: ModelRelationship[], name: string): Set<string> {
  const near = new Set<string>([name]);
  for (const r of relationships) {
    if (r.parent === name) near.add(r.child);
    if (r.child === name) near.add(r.parent);
  }
  return near;
}

const KEY = "bi_data_model";

/** The model chosen last time, per database, remembered in this browser only. */
export function rememberedModel(sourceValue: string): string {
  try {
    return JSON.parse(localStorage.getItem(KEY) || "{}")[sourceValue] || "";
  } catch {
    return "";
  }
}

export function rememberModel(sourceValue: string, key: string) {
  try {
    const all = JSON.parse(localStorage.getItem(KEY) || "{}");
    if (key) all[sourceValue] = key;
    else delete all[sourceValue];
    localStorage.setItem(KEY, JSON.stringify(all));
  } catch {
    /* storage unavailable */
  }
}

/** Models grouped by the solution they belong to, for an optgroup'd picker. */
export function bySolution<T extends { solution: string }>(models: T[]): [string, T[]][] {
  const groups = new Map<string, T[]>();
  for (const m of models) groups.set(m.solution, [...(groups.get(m.solution) ?? []), m]);
  return [...groups.entries()];
}
