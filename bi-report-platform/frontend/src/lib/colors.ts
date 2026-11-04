/**
 * Colour for a chart's categories.
 *
 * A chart with one series used to draw every bar in the same colour, which hides the thing the
 * chart is about: "Major" and "Minor" look identical. These rules give each category a colour that
 * matches what it means — red for Major, green for Minor — the way a risk report is read on paper.
 *
 * Three sources, strongest first:
 *   1. rules the person wrote on the chart (style.colorRules)
 *   2. the meanings below, when the category's name is one people already read as a colour
 *   3. the palette, cycled, so anything unrecognised still differs from its neighbours
 */

/** Named colours used by the meanings below and offered in the pickers. */
export const TONES = {
  green: "#2E9E5B",
  lime: "#7CB342",
  yellow: "#E3B505",
  amber: "#F5A623",
  orange: "#EE7B30",
  red: "#D64545",
  darkRed: "#9B2226",
  blue: "#00B4D8",
  navy: "#0D3B66",
  teal: "#2A9D8F",
  purple: "#6D597A",
  grey: "#8A98A8",
} as const;

/**
 * Words that carry a colour in business reporting, and what they mean. Each entry is tried in
 * order against the whole category name, so put the narrow ones first: "not determined" must beat
 * "determined", and "not effective" must beat "effective".
 */
const MEANINGS: { test: RegExp; color: string }[] = [
  // Nothing known yet. First, so "not rated" never reads as a rating.
  { test: /\b(not (determined|rated|assessed|applicable|started)|undetermined|unrated|unassigned|unknown|none|n\/?a|tbd|blank|empty)\b/, color: TONES.grey },

  // Severity and risk ratings, worst first.
  { test: /\b(catastrophic|critical|severe|extreme|very high|major)\b/, color: TONES.red },
  { test: /\b(significant|substantial|elevated|high)\b/, color: TONES.orange },
  { test: /\b(moderate|medium|average|fair|watch)\b/, color: TONES.yellow },
  { test: /\b(minor|low|minimal|negligible|insignificant|immaterial)\b/, color: TONES.green },

  // Effectiveness and test outcomes.
  { test: /\b(not effective|ineffective|failed|fail|deficient|design deficiency|breach|non[- ]?compliant|overdue|past due|rejected|escalated)\b/, color: TONES.red },
  { test: /\b(partially effective|partial|needs improvement|improvement required|with exceptions|qualified)\b/, color: TONES.amber },
  { test: /\b(effective|passed|pass|satisfactory|compliant|adequate|remediated|resolved|verified)\b/, color: TONES.green },

  // Workflow status.
  { test: /\b(open|new|draft|pending|awaiting|in review|under review|submitted)\b/, color: TONES.blue },
  { test: /\b(in progress|ongoing|in remediation|assigned|accepted)\b/, color: TONES.teal },
  { test: /\b(closed|complete|completed|done|approved|signed off|implemented)\b/, color: TONES.green },
  { test: /\b(cancelled|canceled|withdrawn|deferred|on hold|retired|archived)\b/, color: TONES.grey },

  // Plain yes/no, and traffic lights written out.
  { test: /^\s*(yes|true|y|in scope|sox in scope)\s*$/, color: TONES.green },
  { test: /^\s*(no|false|n|out of scope)\s*$/, color: TONES.grey },
  { test: /^\s*(red|r)\s*$/, color: TONES.red },
  { test: /^\s*(amber|a)\s*$/, color: TONES.amber },
  { test: /^\s*(green|g)\s*$/, color: TONES.green },

  // Priority, where P1 is the urgent one.
  { test: /^\s*(p?1|priority 1|urgent|immediate)\s*$/, color: TONES.red },
  { test: /^\s*(p?2|priority 2)\s*$/, color: TONES.orange },
  { test: /^\s*(p?3|priority 3)\s*$/, color: TONES.yellow },
  { test: /^\s*(p?4|p?5|priority [45])\s*$/, color: TONES.green },
];

/** The colour a category's name means on its own, or "" when it means nothing in particular. */
export function meaningColor(label: string): string {
  const text = String(label ?? "").toLowerCase().trim();
  if (!text) return "";
  for (const m of MEANINGS) if (m.test.test(text)) return m.color;
  return "";
}

/** True when enough of these names carry a meaning for colouring by meaning to look deliberate. */
export function worthColoringByMeaning(labels: string[]): boolean {
  const named = labels.filter((l) => meaningColor(l));
  // Half or more, and at least two: one lonely red bar among greys looks like a mistake.
  return named.length >= 2 && named.length * 2 >= labels.length;
}

/** One rule a person wrote: a category name (or part of one) and the colour it should take. */
export interface ColorRule {
  /** Matched against the category name, ignoring case. "*" or "" matches whatever is left over. */
  match: string;
  color: string;
}

/** The colour a person's own rules give this category, or "" when none of them apply. */
export function ruleColor(label: string, rules: ColorRule[] | undefined): string {
  if (!rules?.length) return "";
  const text = String(label ?? "").toLowerCase().trim();
  let fallback = "";
  for (const r of rules) {
    const match = String(r.match ?? "").toLowerCase().trim();
    const color = normalizeColor(r.color);
    if (!color) continue;
    if (!match || match === "*") { fallback = fallback || color; continue; }
    if (text === match || text.includes(match)) return color;
  }
  return fallback;
}

/**
 * A colour per category, in the order the categories are drawn. `palette` is the chart's own list,
 * used for anything the rules and the meanings don't cover.
 */
export function categoryColors(labels: string[], rules: ColorRule[] | undefined, palette: string[],
                               useMeanings: boolean): string[] {
  return labels.map((label, i) =>
    ruleColor(label, rules) || (useMeanings ? meaningColor(label) : "") || palette[i % palette.length]);
}

// ---------- Reading colours people type ----------

const CSS_NAMES: Record<string, string> = {
  black: "#000000", white: "#FFFFFF", red: "#FF0000", green: "#008000", blue: "#0000FF",
  yellow: "#FFFF00", orange: "#FFA500", purple: "#800080", grey: "#808080", gray: "#808080",
  pink: "#FFC0CB", brown: "#A52A2A", navy: "#000080", teal: "#008080", lime: "#00FF00",
  cyan: "#00FFFF", magenta: "#FF00FF", gold: "#FFD700", silver: "#C0C0C0", maroon: "#800000",
  olive: "#808000", indigo: "#4B0082", violet: "#EE82EE", amber: "#FFBF00", transparent: "",
};

const hex2 = (n: number) => Math.max(0, Math.min(255, Math.round(n))).toString(16).padStart(2, "0").toUpperCase();

/**
 * Reads a colour a person typed and gives back #RRGGBB, or "" when it isn't a colour.
 *
 * Accepts #abc, #aabbcc, bare aabbcc, rgb(0 180 216), rgb(0,180,216), rgba(...) and the common
 * colour names. Everything is stored as #RRGGBB because <input type="color"> and the chart library
 * both want that one shape; the person can still type whichever they have to hand.
 */
export function normalizeColor(input: string | undefined | null): string {
  const text = String(input ?? "").trim().toLowerCase();
  if (!text) return "";
  if (text in CSS_NAMES) return CSS_NAMES[text];

  const hex = text.startsWith("#") ? text.slice(1) : /^[0-9a-f]{3,8}$/.test(text) ? text : "";
  if (hex) {
    if (hex.length === 3 || hex.length === 4) return ("#" + [...hex.slice(0, 3)].map((c) => c + c).join("")).toUpperCase();
    if (hex.length === 6 || hex.length === 8) return ("#" + hex.slice(0, 6)).toUpperCase();
    return "";
  }

  // rgb()/rgba(), with commas or spaces, and percentages.
  const fn = /^rgba?\s*\(([^)]*)\)$/.exec(text);
  if (fn) {
    const parts = fn[1].split(/[\s,/]+/).filter(Boolean).slice(0, 3);
    if (parts.length !== 3) return "";
    const numbers = parts.map((p) => p.endsWith("%") ? (parseFloat(p) / 100) * 255 : parseFloat(p));
    if (numbers.some((n) => !Number.isFinite(n))) return "";
    return "#" + numbers.map(hex2).join("");
  }
  return "";
}

/** #RRGGBB as "rgb(r, g, b)", for showing people the other way of writing it. */
export function toRgb(color: string): string {
  const hex = normalizeColor(color);
  if (!hex) return "";
  const n = parseInt(hex.slice(1), 16);
  return `rgb(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255})`;
}
