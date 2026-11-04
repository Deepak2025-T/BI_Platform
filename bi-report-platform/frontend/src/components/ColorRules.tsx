import type { WidgetStyle } from "../api/types";
import { TONES, meaningColor, normalizeColor, toRgb, worthColoringByMeaning } from "../lib/colors";
import { Seg } from "./Controls";

const MODES: [NonNullable<WidgetStyle["colorMode"]>, string, string][] = [
  ["auto", "By meaning", "Colours names people already read as colours: Major red, Minor green, Closed green."],
  ["palette", "By category", "A different palette colour for each category."],
  ["single", "One colour", "Every category in the chart colour above."],
  ["rules", "My rules only", "Only the rules below decide; anything else uses the chart colour."],
];

/** The colours offered for a rule, named so people can pick the one they mean. */
const PICKS: [string, string][] = [
  ["Green", TONES.green], ["Yellow", TONES.yellow], ["Amber", TONES.amber], ["Orange", TONES.orange],
  ["Red", TONES.red], ["Dark red", TONES.darkRed], ["Blue", TONES.blue], ["Navy", TONES.navy],
  ["Teal", TONES.teal], ["Purple", TONES.purple], ["Grey", TONES.grey],
];

interface Props {
  style: WidgetStyle;
  onChange: (patch: Partial<WidgetStyle>) => void;
  /** The categories this chart actually draws, offered as one-click rules. */
  labels: string[];
}

/**
 * How a chart colours its categories, and the person's own rules for naming the colours.
 *
 * A rule matches a category by name, so "major" catches "Major" and "Major - Financial" alike.
 * Rules are tried in order and beat the built-in meanings, which is what makes them worth having:
 * the meanings are a sensible default, not a house style.
 */
export default function ColorRules({ style, onChange, labels }: Props) {
  const mode = style.colorMode ?? "auto";
  const rules = style.colorRules ?? [];
  const setRules = (next: { match: string; color: string }[]) =>
    onChange({ colorRules: next.length ? next : undefined });
  const edit = (i: number, patch: Partial<{ match: string; color: string }>) =>
    setRules(rules.map((r, n) => (n === i ? { ...r, ...patch } : r)));

  // What "By meaning" would do to this chart right now, so the choice isn't guesswork.
  const meanings = labels.map((l) => [l, meaningColor(l)] as const).filter(([, c]) => c);
  const covered = worthColoringByMeaning(labels);
  const unruled = labels.filter((l) => !rules.some((r) => {
    const m = r.match.toLowerCase().trim();
    return m && (l.toLowerCase().trim() === m || l.toLowerCase().includes(m));
  }));

  return (
    <div className="box stack-sm">
      <div className="strong small">Colour by value</div>
      <div className="seg-row">
        {MODES.map(([k, label, why]) => (
          <Seg key={k} on={mode === k} onClick={() => onChange({ colorMode: k === "auto" ? undefined : k })} title={why}>
            {label}
          </Seg>
        ))}
      </div>

      {mode === "auto" && (
        meanings.length === 0
          ? <p className="hint">None of these categories read as a colour, so the chart keeps one colour. Add a rule below to set them yourself.</p>
          : !covered
            ? <p className="hint">Only {meanings.length} of {labels.length} categories read as a colour, too few to colour by meaning. Add rules below, or choose “By category”.</p>
            : <div className="rule-preview">
                {meanings.map(([l, c]) => (
                  <span key={l} className="rule-chip"><span className="rule-dot" style={{ background: c }} />{l}</span>
                ))}
              </div>
      )}

      {rules.length > 0 && (
        <div className="stack-sm">
          {rules.map((r, i) => {
            const hex = normalizeColor(r.color);
            return (
              <div className="rule-row" key={i}>
                <input value={r.match} placeholder="Category name, e.g. Major" aria-label={`Rule ${i + 1}: category`}
                  onChange={(e) => edit(i, { match: e.target.value })} />
                <select value={PICKS.some(([, c]) => c === hex) ? hex : ""} aria-label={`Rule ${i + 1}: named colour`}
                  onChange={(e) => e.target.value && edit(i, { color: e.target.value })}>
                  <option value="">Custom…</option>
                  {PICKS.map(([name, c]) => <option key={c} value={c}>{name}</option>)}
                </select>
                <input className={"color-text" + (hex ? "" : " bad")} value={r.color} spellCheck={false}
                  placeholder="#D64545 or rgb(214, 69, 69)" aria-label={`Rule ${i + 1}: colour`} aria-invalid={!hex}
                  title={hex ? `${hex} · ${toRgb(hex)}` : "Not a colour"}
                  onChange={(e) => edit(i, { color: e.target.value })} />
                <input type="color" value={hex || "#D64545"} aria-label={`Rule ${i + 1}: pick a colour`}
                  onChange={(e) => edit(i, { color: e.target.value.toUpperCase() })} />
                <button type="button" className="link-btn" aria-label={`Remove rule ${i + 1}`}
                  onClick={() => setRules(rules.filter((_, n) => n !== i))}>Remove</button>
              </div>
            );
          })}
        </div>
      )}

      <div className="row-wrap">
        <button type="button" className="link-btn" onClick={() => setRules([...rules, { match: "", color: TONES.red }])}>
          Add a rule
        </button>
        {/* The categories on screen, so the usual case is one click rather than typing names. */}
        {unruled.slice(0, 8).map((l) => (
          <button key={l} type="button" className="link-btn" title={`Add a rule for ${l}`}
            onClick={() => setRules([...rules, { match: l, color: meaningColor(l) || TONES.blue }])}>
            + {l}
          </button>
        ))}
        {rules.length > 0 && (
          <button type="button" className="link-btn" onClick={() => setRules([])}>Clear the rules</button>
        )}
      </div>
    </div>
  );
}
