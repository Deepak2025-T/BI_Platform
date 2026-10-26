import { useEffect, useRef, useState } from "react";
import type { WidgetStyle } from "../api/types";
import { CARD_COLORS, HEADER_COLORS } from "../lib/cardColors";
import Icon from "./Icon";

/** A row of colour dots with "none" first and "pick any colour" last. */
export function SwatchRow({ label, colors, value, onChange, noneLabel }: {
  label: string; colors: string[]; value?: string; onChange: (c: string | undefined) => void; noneLabel: string;
}) {
  const current = value?.toUpperCase();
  return (
    <fieldset className="group">
      <legend>{label}</legend>
      <div className="color-row">
        <button type="button" className={"color-dot color-none" + (!current ? " on" : "")} aria-pressed={!current}
          aria-label={noneLabel} title={noneLabel} onClick={() => onChange(undefined)} />
        {colors.map((c) => (
          <button key={c} type="button" className={"color-dot" + (current === c ? " on" : "")} style={{ background: c }}
            aria-label={`${label} ${c}`} aria-pressed={current === c} onClick={() => onChange(c)} />
        ))}
        <label className="color-custom" title="Pick any colour">
          <span className="sr-only">{label}: any colour</span>
          <input type="color" value={value ?? "#FFFFFF"} onChange={(e) => onChange(e.target.value.toUpperCase())} />
        </label>
      </div>
    </fieldset>
  );
}

/** The header and card colour pickers, shared by the tile's palette button and the chart editor. */
export function CardColorFields({ style, onChange }: { style: WidgetStyle; onChange: (patch: Partial<WidgetStyle>) => void }) {
  return (
    <>
      <SwatchRow label="Header colour" colors={HEADER_COLORS} value={style.headBg} noneLabel="No header colour"
        onChange={(headBg) => onChange({ headBg })} />
      <SwatchRow label="Card background" colors={CARD_COLORS} value={style.cardBg} noneLabel="White (default)"
        onChange={(cardBg) => onChange({ cardBg })} />
    </>
  );
}

interface Props {
  name: string;
  style: WidgetStyle;
  onChange: (patch: Partial<WidgetStyle>) => void;
  /** Gives every card on the dashboard these header and card colours. */
  onApplyAll?: (patch: Pick<WidgetStyle, "headBg" | "cardBg">) => void;
}

/** The palette button on a tile in edit mode: header and card background colours. */
export default function CardColors({ name, style, onChange, onApplyAll }: Props) {
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

  const custom = !!(style.headBg || style.cardBg);
  return (
    <div className="tile-menu" ref={box}>
      <button type="button" className={"icon-btn" + (custom ? " on" : "")} aria-label={`Colours of ${name}`} aria-haspopup="dialog"
        aria-expanded={open} title="Header and card colours" onClick={() => setOpen((o) => !o)}><Icon name="palette" size={16} /></button>
      {open && (
        <div className="tile-menu-list card-colors" role="dialog" aria-label={`Colours of ${name}`}>
          <CardColorFields style={style} onChange={onChange} />
          <div className="row-wrap">
            {custom && <button type="button" className="link-btn" onClick={() => onChange({ headBg: undefined, cardBg: undefined })}>Reset</button>}
            {onApplyAll && (
              <button type="button" className="link-btn" onClick={() => { onApplyAll({ headBg: style.headBg, cardBg: style.cardBg }); setOpen(false); }}>
                Use on every card
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
