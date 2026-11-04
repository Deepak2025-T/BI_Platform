import { useState } from "react";
import { type FixedSize, HEIGHT, clampHeight, sizeForCols, sizeLabel, stepWidth } from "../lib/tileSize";

interface Props {
  /** What is being resized, for screen readers. */
  name: string;
  /** Columns the tile spans now (of 12). */
  cols: number;
  /** Height in pixels; leave out for tiles that only change width. */
  height?: number;
  /** The 12-column grid the tile sits in, to turn pointer movement into columns. */
  grid: React.RefObject<HTMLElement | null>;
  onChange: (patch: { size: FixedSize; height?: number }) => void;
  onActive?: (on: boolean) => void;
}

/**
 * The corner handle on a tile: drag it to change the width (snaps to quarter, third, half, two thirds, full)
 * and the height (40 px steps), or focus it and use the arrow keys.
 */
export default function ResizeHandle({ name, cols, height, grid, onChange, onActive }: Props) {
  const [active, setActive] = useState(false);
  const hasHeight = height !== undefined;

  const start = (e: React.PointerEvent) => {
    const el = grid.current;
    if (!el || e.button !== 0) return;
    e.preventDefault();
    const colWidth = (el.clientWidth + (parseFloat(getComputedStyle(el).columnGap) || 0)) / 12;
    const x0 = e.clientX, y0 = e.clientY, h0 = height ?? HEIGHT.default;
    let last = "";
    setActive(true);
    onActive?.(true);
    const move = (ev: PointerEvent) => {
      const size = sizeForCols(cols + (ev.clientX - x0) / colWidth);
      const h = hasHeight ? clampHeight(h0 + ev.clientY - y0) : undefined;
      const key = `${size}|${h}`;
      if (key !== last) { last = key; onChange(h === undefined ? { size } : { size, height: h }); }
    };
    const up = () => {
      setActive(false);
      onActive?.(false);
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
  };

  const key = (e: React.KeyboardEvent) => {
    const h = height ?? HEIGHT.default;
    const size = sizeForCols(cols);
    const patch =
      e.key === "ArrowLeft" ? { size: stepWidth(cols, -1) } : e.key === "ArrowRight" ? { size: stepWidth(cols, 1) }
      : e.key === "ArrowUp" && hasHeight ? { size, height: clampHeight(h - HEIGHT.step) }
      : e.key === "ArrowDown" && hasHeight ? { size, height: clampHeight(h + HEIGHT.step) } : null;
    if (patch) { e.preventDefault(); onChange(patch); }
  };

  const label = sizeLabel(cols, height);
  return (
    <>
      <button type="button" className={`resize-handle no-print${hasHeight ? "" : " width-only"}`} aria-label={`Resize ${name}, now ${label}`}
        title={hasHeight ? "Drag to resize. Arrow keys: left and right change the width, up and down the height."
          : "Drag sideways to change the width (or the left and right arrow keys)."}
        onPointerDown={start} onKeyDown={key} />
      {active && <span className="resize-size" aria-hidden="true">{label}</span>}
    </>
  );
}
