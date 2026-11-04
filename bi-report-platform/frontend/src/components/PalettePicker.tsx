import { useEffect, useState } from "react";
import { errorMessage } from "../api/client";
import { palettesApi } from "../api/endpoints";
import type { ColorPalette } from "../api/types";
import { normalizeColor, toRgb } from "../lib/colors";
import {
  DEFAULT_PALETTE, allPalettes, cleanColors, colorGrid, matchPalette, type PaletteChoice,
} from "../lib/palettes";
import { ColorPicker } from "./Controls";
import Icon from "./Icon";
import Modal from "./Modal";

interface Props {
  /** The colours in use, or undefined for the default palette. */
  value: string[] | undefined;
  onChange: (colors: string[] | undefined) => void;
  label?: string;
  /** Shown under the heading, e.g. which charts this palette applies to. */
  hint?: string;
}

/**
 * Pick a palette, or make one.
 *
 * Built-in palettes and saved ones are listed together because, to the person choosing, they are
 * the same kind of thing. The difference only shows on the menu: a built-in palette can be
 * duplicated but not edited or deleted, since everyone else is using it too.
 *
 * Choosing a palette copies its colours onto whatever is being styled. That is deliberate - see
 * lib/palettes.ts - so a saved report can't change colour because someone edited a palette.
 */
export default function PalettePicker({ value, onChange, label = "Colour palette", hint }: Props) {
  const [saved, setSaved] = useState<ColorPalette[]>([]);
  const [error, setError] = useState("");
  const [editing, setEditing] = useState<{ palette: PaletteChoice | null; colors: string[]; name: string } | null>(null);
  const [menu, setMenu] = useState<string>("");

  const load = () => palettesApi.list().then(setSaved).catch((e) => setError(errorMessage(e)));
  useEffect(() => { load(); }, []);

  const choices = allPalettes(saved);
  const current = matchPalette(value, choices);
  // Colours that don't match any palette: the chart was coloured by hand, so show them as they are.
  const custom = value?.length && !current ? value : null;

  const apply = (colors: string[]) => onChange(cleanColors(colors));

  const duplicate = async (choice: PaletteChoice) => {
    setMenu("");
    try {
      const copy = choice.saved
        ? await palettesApi.duplicate(choice.saved.id)
        : await palettesApi.create({ name: `${choice.name} copy`, colors: choice.colors });
      setSaved((list) => [...list, copy].sort((a, b) => a.name.localeCompare(b.name)));
      apply(copy.colors);
    } catch (e) { setError(errorMessage(e)); }
  };

  const remove = async (choice: PaletteChoice) => {
    if (!choice.saved) return;
    setMenu("");
    try {
      await palettesApi.remove(choice.saved.id);
      setSaved((list) => list.filter((p) => p.id !== choice.saved!.id));
      // The charts keep their colours: the palette was copied onto them when it was applied.
    } catch (e) { setError(errorMessage(e)); }
  };

  const save = async (name: string, colors: string[], existing: ColorPalette | undefined) => {
    const tidy = cleanColors(colors);
    if (tidy.length < 2) { setError("A palette needs at least two colours."); return; }
    try {
      const row = existing
        ? await palettesApi.update(existing.id, { name, colors: tidy })
        : await palettesApi.create({ name, colors: tidy });
      setSaved((list) => [...list.filter((p) => p.id !== row.id), row].sort((a, b) => a.name.localeCompare(b.name)));
      apply(row.colors);
      setEditing(null);
      setError("");
    } catch (e) { setError(errorMessage(e)); }
  };

  const row = (choice: PaletteChoice) => {
    const on = current?.key === choice.key;
    const own = !!choice.saved;
    return (
      <div className={"palette-row" + (on ? " on" : "")} key={choice.key}>
        <button type="button" className="palette-pick" aria-pressed={on}
          title={choice.colors.join(", ")} onClick={() => apply(choice.colors)}>
          <span className="palette-name">{choice.name}</span>
          <span className="palette-strip">
            {choice.colors.map((c, i) => <span key={`${c}-${i}`} style={{ background: c }} />)}
          </span>
        </button>
        <div className="palette-menu-wrap">
          <button type="button" className="icon-btn" aria-label={`More for ${choice.name}`}
            aria-expanded={menu === choice.key}
            onClick={() => setMenu(menu === choice.key ? "" : choice.key)}><Icon name="more" size={16} /></button>
          {menu === choice.key && (
            <div className="palette-menu" role="menu">
              <button type="button" role="menuitem" onClick={() => duplicate(choice)}>Duplicate</button>
              {own && choice.saved!.can_edit && (
                <button type="button" role="menuitem"
                  onClick={() => { setMenu(""); setEditing({ palette: choice, colors: choice.colors, name: choice.name }); }}>
                  Edit
                </button>
              )}
              {own && choice.saved!.can_edit && (
                <button type="button" role="menuitem" className="danger" onClick={() => remove(choice)}>Delete</button>
              )}
              {!own && <span className="palette-menu-note">Built in, so it can only be duplicated.</span>}
            </div>
          )}
        </div>
      </div>
    );
  };

  const mine = choices.filter((c) => c.saved);
  const system = choices.filter((c) => !c.saved);

  return (
    <fieldset className="group palette-group">
      <legend>{label}</legend>
      {hint && <p className="hint">{hint}</p>}
      {error && <p className="hint bad">{error}</p>}

      {custom && (
        <div className="palette-row on">
          <span className="palette-pick as-text">
            <span className="palette-name">Custom colours</span>
            <span className="palette-strip">{custom.map((c, i) => <span key={`${c}-${i}`} style={{ background: c }} />)}</span>
          </span>
          <button type="button" className="link-btn"
            onClick={() => setEditing({ palette: null, colors: custom, name: "My palette" })}>Save as a palette</button>
        </div>
      )}

      {mine.length > 0 && (
        <>
          <div className="palette-head">Custom</div>
          <div className="palette-list">{mine.map(row)}</div>
        </>
      )}

      <div className="palette-head">System</div>
      <div className="palette-list">{system.map(row)}</div>

      <div className="row-wrap">
        <button type="button" className="link-btn"
          onClick={() => setEditing({ palette: null, colors: [...DEFAULT_PALETTE.slice(0, 5)], name: "My palette" })}>
          New palette
        </button>
        {value && <button type="button" className="link-btn" onClick={() => onChange(undefined)}>Use the default</button>}
      </div>

      {editing && (
        <PaletteEditor start={editing} onCancel={() => setEditing(null)}
          onSave={(name, colors) => save(name, colors, editing.palette?.saved)} />
      )}
    </fieldset>
  );
}

/** Builds one palette: its name and the colours, in the order charts will use them. */
function PaletteEditor({ start, onCancel, onSave }: {
  start: { palette: PaletteChoice | null; colors: string[]; name: string };
  onCancel: () => void;
  onSave: (name: string, colors: string[]) => void;
}) {
  const [name, setName] = useState(start.name);
  const [colors, setColors] = useState<string[]>(start.colors.length ? start.colors : [...DEFAULT_PALETTE.slice(0, 5)]);
  // Which swatch the grid and the picker below are changing. -1 means they add a new one.
  const [at, setAt] = useState(0);
  const grid = colorGrid();
  const put = (color: string) => {
    const hex = normalizeColor(color);
    if (!hex) return;
    setColors((list) => (at >= 0 && at < list.length
      ? list.map((c, i) => (i === at ? hex : c))
      : [...list, hex].slice(0, 24)));
    if (at < 0) setAt(colors.length);
  };
  const move = (from: number, by: number) => {
    const to = from + by;
    if (to < 0 || to >= colors.length) return;
    const list = [...colors];
    [list[from], list[to]] = [list[to], list[from]];
    setColors(list);
    setAt(to);
  };

  return (
    <Modal title={start.palette ? `Edit palette: ${start.palette.name}` : "New palette"} onClose={onCancel} size="lg"
      onSubmit={() => onSave(name.trim() || "My palette", colors)}
      footer={<>
        <button type="button" className="btn ghost" onClick={onCancel}>Cancel</button>
        <button type="submit" className="btn">Save palette</button>
      </>}>
      <div className="stack">
        <label className="field">Palette name
          <input value={name} maxLength={60} onChange={(e) => setName(e.target.value)} autoFocus />
        </label>

        <fieldset className="group">
          <legend>Colours, in the order charts use them</legend>
          <div className="palette-edit-row">
            {colors.map((c, i) => (
              <button key={`${c}-${i}`} type="button" className={"palette-chip" + (at === i ? " on" : "")}
                style={{ background: c }} aria-pressed={at === i} title={`${c} · ${toRgb(c)}`}
                aria-label={`Colour ${i + 1}, ${c}`} onClick={() => setAt(i)} />
            ))}
            <button type="button" className="palette-chip add" aria-label="Add a colour"
              onClick={() => setAt(-1)} title="Pick a colour below to add it">+</button>
          </div>
          <div className="row-wrap">
            <button type="button" className="link-btn" disabled={at < 1} onClick={() => move(at, -1)}>Move left</button>
            <button type="button" className="link-btn" disabled={at < 0 || at >= colors.length - 1}
              onClick={() => move(at, 1)}>Move right</button>
            <button type="button" className="link-btn" disabled={at < 0 || colors.length <= 2}
              onClick={() => { setColors(colors.filter((_, i) => i !== at)); setAt(Math.max(0, at - 1)); }}>
              Remove this colour
            </button>
            <span className="hint">{at < 0 ? "Pick a colour to add it." : `Changing colour ${at + 1} of ${colors.length}.`}</span>
          </div>
        </fieldset>

        <ColorPicker label={at < 0 ? "Colour to add" : `Colour ${at + 1}`}
          value={at >= 0 ? colors[at] ?? "#00B4D8" : "#00B4D8"} onChange={put} />

        <fieldset className="group">
          <legend>Colour guide</legend>
          <div className="color-grid" role="group" aria-label="Colour guide">
            {grid.map((line, r) => (
              <div className="color-grid-row" key={r}>
                {line.map((c, i) => (
                  <button key={`${r}-${i}`} type="button" className="color-grid-cell" style={{ background: c }}
                    title={`${c} · ${toRgb(c)}`} aria-label={c} onClick={() => put(c)} />
                ))}
              </div>
            ))}
          </div>
        </fieldset>

        <div className="palette-preview">
          <span className="hint">How a chart will look</span>
          <div className="palette-bars">
            {colors.map((c, i) => (
              <span key={`${c}-${i}`} style={{ background: c, height: `${100 - i * (60 / Math.max(1, colors.length))}%` }} />
            ))}
          </div>
        </div>
      </div>
    </Modal>
  );
}
