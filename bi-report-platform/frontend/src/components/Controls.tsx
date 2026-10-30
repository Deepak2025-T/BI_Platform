import type { ReactNode } from "react";

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

/** Preset colour dots plus a "pick any colour" button. Values are upper-case #RRGGBB. */
export function ColorPicker({ value, onChange, label = "Colour" }: { value: string; onChange: (c: string) => void; label?: string }) {
  const current = value.toUpperCase();
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
          <input type="color" value={value} onChange={(e) => onChange(e.target.value.toUpperCase())} />
        </label>
      </div>
    </fieldset>
  );
}
