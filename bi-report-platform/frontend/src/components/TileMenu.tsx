import { useEffect, useRef, useState } from "react";
import Icon from "./Icon";

export interface TileMenuItem {
  label: string;
  onClick: () => void;
  disabled?: boolean;
  danger?: boolean;
}

/** The "⋯" menu on a dashboard tile in edit mode, for the actions people use less often. */
export default function TileMenu({ name, items }: { name: string; items: TileMenuItem[] }) {
  const [open, setOpen] = useState(false);
  const box = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent | KeyboardEvent) => {
      if (e instanceof KeyboardEvent ? e.key === "Escape" : !box.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", close);
    return () => { document.removeEventListener("mousedown", close); document.removeEventListener("keydown", close); };
  }, [open]);

  return (
    <div className="tile-menu" ref={box}>
      <button type="button" className="icon-btn" aria-label={`More actions for ${name}`} aria-haspopup="menu" aria-expanded={open}
        title="More" onClick={() => setOpen((o) => !o)}><Icon name="more" size={16} /></button>
      {open && (
        <div className="tile-menu-list" role="menu">
          {items.map((it) => (
            <button key={it.label} type="button" role="menuitem" className={it.danger ? "danger" : ""} disabled={it.disabled}
              onClick={() => { setOpen(false); it.onClick(); }}>{it.label}</button>
          ))}
        </div>
      )}
    </div>
  );
}
