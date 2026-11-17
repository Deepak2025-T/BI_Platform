/**
 * A row of colour dots.
 *
 * It lives on its own rather than beside the first thing that used it: the card colours, the tile
 * border and the tab colour all want it, and two components that import each other to share one
 * row of buttons is a cycle waiting to be evaluated in the wrong order.
 */

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
