import type { DashboardConfig, ReportFont, ReportTypography, WidgetStyle } from "../api/types";
import { SwatchRow } from "./Swatches";
import {
  ALIGNMENTS, BORDER_COLORS, BORDER_WIDTHS, FONTS, FONT_SIZES, PADDINGS, RADII, V_ALIGNMENTS,
  typographyLabel,
} from "../lib/tileLook";
import { Seg } from "./Controls";

/**
 * The look of a report, and of one tile on it.
 *
 * Everything here is an override of something that already has a sensible value, so every control
 * offers "the report's" or "default" as its first choice and starts there. Nothing is set until
 * someone sets it, which is what keeps a report that nobody has restyled drawn by the plain
 * stylesheet.
 */

/** A select whose first option means "don't set this; inherit what is above". */
function Inherited<T extends string | number>({ label, value, options, inherit, onChange, hint }: {
  label: string;
  value: T | undefined;
  options: [T, string][];
  /** What the first option says, e.g. "The report's (Serif, 14px)". */
  inherit: string;
  onChange: (value: T | undefined) => void;
  hint?: string;
}) {
  const numeric = typeof options[0]?.[0] === "number";
  return (
    <label className="field">{label}
      <select value={value ?? ""} onChange={(e) => {
        const raw = e.target.value;
        onChange(raw === "" ? undefined : (numeric ? Number(raw) : raw) as T);
      }}>
        <option value="">{inherit}</option>
        {options.map(([k, l]) => <option key={k} value={k}>{l}</option>)}
      </select>
      {hint && <span className="hint">{hint}</span>}
    </label>
  );
}

/** The whole report's font and text size. Every tile inherits these unless it says otherwise. */
export function ReportLookFields({ typography, onChange }: {
  typography?: ReportTypography;
  onChange: (next: ReportTypography | undefined) => void;
}) {
  const set = (patch: Partial<ReportTypography>) => {
    const next = { ...typography, ...patch };
    // A report that has been put back to the defaults should say nothing at all rather than carry
    // a row of empty settings around with it.
    const kept = Object.fromEntries(Object.entries(next).filter(([, v]) => v !== undefined && v !== ""));
    onChange(Object.keys(kept).length ? kept as ReportTypography : undefined);
  };

  return (
    <div className="form-grid">
      <label className="field">Font
        <select value={typography?.font ?? ""} onChange={(e) => set({ font: e.target.value as ReportFont })}>
          {FONTS.map((f) => <option key={f.key} value={f.key}>{f.label}</option>)}
        </select>
        <span className="hint">{FONTS.find((f) => f.key === (typography?.font ?? ""))?.hint}</span>
      </label>
      <label className="field">Text size
        <select value={typography?.fontSize ?? 14}
          onChange={(e) => set({ fontSize: Number(e.target.value) === 14 ? undefined : Number(e.target.value) })}>
          {FONT_SIZES.map(([px, l]) => <option key={px} value={px}>{l} · {px}px</option>)}
        </select>
        <span className="hint">Every tile is sized from this, so headings stay bigger than the body.</span>
      </label>
    </div>
  );
}

/**
 * One tile's look: its font, how its heading sits, its spacing and its border.
 *
 * The colours of the header band and the card itself are set by CardColorFields, which was here
 * first and is shown alongside this rather than folded into it.
 */
export function TileLookFields({ style, config, onChange, isTable }: {
  style: WidgetStyle;
  /** The report this tile is on, so each control can say what it would otherwise inherit. */
  config: Pick<DashboardConfig, "typography">;
  onChange: (patch: Partial<WidgetStyle>) => void;
  /** Tables get the wrapping switch; nothing else has values long enough to need it. */
  isTable?: boolean;
}) {
  return (
    <>
      <div className="form-grid">
        <Inherited label="Font" value={style.font || undefined} inherit={`The report's (${typographyLabel(config)})`}
          options={FONTS.filter((f) => f.key).map((f) => [f.key, f.label] as [ReportFont, string])}
          onChange={(font) => onChange({ font })} />
        <Inherited label="Text size" value={style.fontSize} inherit={`The report's (${config.typography?.fontSize ?? 14}px)`}
          options={FONT_SIZES.map(([px, l]) => [px, `${l} · ${px}px`] as [number, string])}
          onChange={(fontSize) => onChange({ fontSize })} />
        <Inherited label="Padding" value={style.padding} inherit="Default (18px)"
          options={PADDINGS.map(([px, l]) => [px, `${l} · ${px}px`] as [number, string])}
          onChange={(padding) => onChange({ padding })} />
        <Inherited label="Border" value={style.borderWidth} inherit="Default (hairline)"
          options={BORDER_WIDTHS.map(([px, l]) => [px, px ? `${l} · ${px}px` : l] as [number, string])}
          onChange={(borderWidth) => onChange({ borderWidth })} />
        <Inherited label="Corners" value={style.radius} inherit="Default (12px)"
          options={RADII.map(([px, l]) => [px, px ? `${l} · ${px}px` : l] as [number, string])}
          onChange={(radius) => onChange({ radius })} />
      </div>

      {style.borderWidth !== 0 && (
        <SwatchRow label="Border colour" colors={BORDER_COLORS} value={style.border} noneLabel="Default line"
          onChange={(border) => onChange({ border })} />
      )}

      <div className="form-grid">
        <div className="field">Heading across
          <div className="chip-row tight" role="group" aria-label="Heading alignment, across">
            {ALIGNMENTS.map(([k, l]) => (
              <Seg key={k} on={(style.align ?? "left") === k}
                onClick={() => onChange({ align: k === "left" ? undefined : k })}>{l}</Seg>
            ))}
          </div>
        </div>
        <div className="field">Heading down
          <div className="chip-row tight" role="group" aria-label="Heading alignment, down">
            {V_ALIGNMENTS.map(([k, l]) => (
              <Seg key={k} on={(style.vAlign ?? "middle") === k}
                onClick={() => onChange({ vAlign: k === "middle" ? undefined : k })}>{l}</Seg>
            ))}
          </div>
          <span className="hint">Shows when the heading band is taller than its words.</span>
        </div>
      </div>

      <div className="style-checks">
        <label className="check">
          <input type="checkbox" checked={!!style.bold} onChange={(e) => onChange({ bold: e.target.checked || undefined })} />
          Bolder text on this tile
        </label>
        {isTable && (
          <label className="check">
            <input type="checkbox" checked={!!style.wrapText}
              onChange={(e) => onChange({ wrapText: e.target.checked || undefined })} />
            Wrap long values onto more lines
          </label>
        )}
      </div>
    </>
  );
}
