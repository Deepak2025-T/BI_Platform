import { useEffect, useRef, useState } from "react";
import type { DashboardConfig, WidgetStyle } from "../api/types";
import { CARD_COLORS, HEADER_COLORS } from "../lib/cardColors";
import { CLEARED_LOOK, isStyled } from "../lib/tileLook";
import { SwatchRow } from "./Swatches";
import Icon from "./Icon";
import { TileLookFields } from "./LookFields";

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
  /** The report this tile is on, so each setting can say what it would otherwise inherit. */
  config?: Pick<DashboardConfig, "typography">;
  /** Tables get the wrapping switch; nothing else has values long enough to need it. */
  isTable?: boolean;
}

/**
 * The look button on a tile in edit mode.
 *
 * It is the only way a heading or a picture has of being restyled - they have no chart editor to
 * open - so everything about how one tile is drawn lives here: its colours, its font, where its
 * heading sits, its spacing and its border.
 */
export default function CardColors({ name, style, onChange, onApplyAll, config, isTable }: Props) {
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

  const custom = isStyled(style);
  return (
    <div className="tile-menu" ref={box}>
      <button type="button" className={"icon-btn" + (custom ? " on" : "")} aria-label={`Look of ${name}`} aria-haspopup="dialog"
        aria-expanded={open} title="Colours, font, spacing and border" onClick={() => setOpen((o) => !o)}><Icon name="palette" size={16} /></button>
      {open && (
        <div className="tile-menu-list card-colors" role="dialog" aria-label={`Look of ${name}`}>
          <CardColorFields style={style} onChange={onChange} />
          <TileLookFields style={style} config={config ?? {}} onChange={onChange} isTable={isTable} />
          <div className="row-wrap">
            {custom && <button type="button" className="link-btn" onClick={() => onChange(CLEARED_LOOK)}>Reset</button>}
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
