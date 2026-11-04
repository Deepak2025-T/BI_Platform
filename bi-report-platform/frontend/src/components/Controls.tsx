import { useEffect, useState, type ReactNode } from "react";
import { normalizeColor, toRgb } from "../lib/colors";

export function Group({ label, children, column }: { label: string; children: ReactNode; column?: boolean }) {
  return (
    <fieldset className="group">
      <legend>{label}</legend>
      <div className={column ? "seg-col" : "seg-row"}>{children}</div>
    </fieldset>
  );
}

export function Seg({ on, onClick, children, left, disabled, title }:
  { on: boolean; onClick: () => void; children: ReactNode; left?: boolean; disabled?: boolean; title?: string }) {
  return (
    <button type="button" className={"seg" + (on ? " on" : "") + (left ? " left" : "")} aria-pressed={on}
      disabled={disabled} onClick={onClick} title={title} aria-label={title}>{children}</button>
  );
}

export const SWATCH_COLORS = ["#00B4D8", "#0D3B66", "#F5A623", "#7A8BA3", "#2A9D8F", "#A63D40", "#6D597A", "#1E7F4F"];

/**
 * Preset colour dots, a "pick any colour" button, and a box to type one in. Values are given back
 * as upper-case #RRGGBB, but a person can type whatever they have to hand: a hex code with or
 * without the #, rgb(0, 180, 216), or a plain colour name. What they typed stays in the box while
 * it is still half-written, so the field doesn't fight them mid-word.
 */
export function ColorPicker({ value, onChange, label = "Colour" }: { value: string; onChange: (c: string) => void; label?: string }) {
  const current = normalizeColor(value) || "#00B4D8";
  const [typed, setTyped] = useState(value);
  // Follow the value when it changes elsewhere (a dot, the native picker, another chart).
  useEffect(() => setTyped(value), [value]);
  const typedOk = !typed.trim() || !!normalizeColor(typed);
  return (
    <fieldset className="group">
      <legend>{label}</legend>
      <div className="color-row">
        {SWATCH_COLORS.map((c) => (
          <button key={c} type="button" className={"color-dot" + (current === c ? " on" : "")} style={{ background: c }}
            aria-label={`Colour ${c}`} aria-pressed={current === c} onClick={() => onChange(c)} />
        ))}
        <label className="color-custom" title="Pick any colour">
          <span className="sr-only">Custom colour</span>
          <input type="color" value={current} onChange={(e) => onChange(e.target.value.toUpperCase())} />
        </label>
        <input className={"color-text" + (typedOk ? "" : " bad")} value={typed} spellCheck={false}
          aria-label={`${label}: hex or rgb`} aria-invalid={!typedOk} placeholder="#00B4D8 or rgb(0, 180, 216)"
          title={current ? `${current} · ${toRgb(current)}` : undefined}
          onChange={(e) => {
            setTyped(e.target.value);
            const hex = normalizeColor(e.target.value);
            if (hex) onChange(hex);
          }}
          onBlur={() => setTyped(normalizeColor(typed) || value)} />
      </div>
      {!typedOk && <p className="hint bad">Not a colour. Try #D64545, rgb(214, 69, 69) or red.</p>}
    </fieldset>
  );
}
