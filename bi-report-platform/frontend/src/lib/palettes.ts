import type { ColorPalette } from "../api/types";
import { normalizeColor } from "./colors";

/**
 * Chart colour palettes.
 *
 * The built-in ones are here rather than in the database: they never change, and a row per
 * built-in palette would mean a migration every time one is adjusted. Anything a person makes is
 * saved through /api/palettes and arrives as a `ColorPalette`, which is why both shapes are
 * flattened to `PaletteChoice` before the pickers see them.
 *
 * A palette is *copied into* a chart when it is applied, never referenced. A saved report then
 * keeps the colours it was given, so deleting a palette can't quietly repaint work from last year.
 */

export interface PaletteChoice {
  /** "sys:ocean" for a built-in one, "own:12" for a saved one. */
  key: string;
  name: string;
  colors: string[];
  /** Saved palettes only: the row, for editing, duplicating and deleting. */
  saved?: ColorPalette;
}

/** The palette a chart falls back to, and the first entry in every picker. */
export const DEFAULT_PALETTE = ["#00B4D8", "#0D3B66", "#F5A623", "#7A8BA3", "#2A9D8F", "#A63D40", "#6D597A", "#1E7F4F"];

export const SYSTEM_PALETTES: { id: string; name: string; colors: string[] }[] = [
  { id: "default", name: "Default", colors: DEFAULT_PALETTE },
  { id: "ocean", name: "Ocean", colors: ["#00B4D8", "#0077B6", "#0D3B66", "#48CAE4", "#90E0EF", "#5B8CA8"] },
  { id: "warm", name: "Warm", colors: ["#F3A712", "#EE7B30", "#A63D40", "#E9C46A", "#D64545", "#5C3D2E"] },
  { id: "forest", name: "Forest", colors: ["#1E7F4F", "#2A9D8F", "#7CB342", "#4E7C59", "#A7C957", "#2F5D50"] },
  { id: "slate", name: "Slate", colors: ["#1A2332", "#3D4F66", "#5B6B80", "#7A8BA3", "#9AA8B8", "#CBD5E0"] },
  { id: "vivid", name: "Vivid", colors: ["#E63946", "#F3A712", "#2A9D8F", "#457B9D", "#6D597A", "#E07A5F", "#118AB2", "#06D6A0"] },
  // Risk reporting reads worst-to-best, so this one is ordered that way deliberately: a chart
  // sorted largest-first lands red on the biggest bar without anybody writing a rule.
  { id: "risk", name: "Risk (red to green)", colors: ["#9B2226", "#D64545", "#EE7B30", "#E3B505", "#7CB342", "#2E9E5B"] },
  { id: "rag", name: "Traffic light", colors: ["#D64545", "#F5A623", "#2E9E5B", "#8A98A8"] },
  // One hue, light to dark: for a chart where the categories are ranked rather than different.
  { id: "mono-blue", name: "Blues", colors: ["#CAF0F8", "#90E0EF", "#48CAE4", "#00B4D8", "#0077B6", "#023E8A"] },
  { id: "mono-grey", name: "Greys", colors: ["#E2E8F0", "#CBD5E0", "#9AA8B8", "#7A8BA3", "#5B6B80", "#3D4F66"] },
  // Distinguishable with the common forms of colour blindness (Okabe-Ito).
  { id: "accessible", name: "Colour-blind safe", colors: ["#0072B2", "#E69F00", "#009E73", "#CC79A7", "#56B4E9", "#D55E00", "#F0E442", "#000000"] },
];

export const SYSTEM_KEYS = SYSTEM_PALETTES.map((p) => `sys:${p.id}`);

/** Every palette on offer: the built-in ones, then the saved ones. */
export function allPalettes(saved: ColorPalette[]): PaletteChoice[] {
  return [
    ...SYSTEM_PALETTES.map((p) => ({ key: `sys:${p.id}`, name: p.name, colors: p.colors })),
    ...saved.map((p) => ({ key: `own:${p.id}`, name: p.name, colors: p.colors, saved: p })),
  ];
}

/** The palette whose colours these are, so a chart's own list still shows as the palette it came from. */
export function matchPalette(colors: string[] | undefined, choices: PaletteChoice[]): PaletteChoice | null {
  if (!colors?.length) return null;
  const same = (a: string[], b: string[]) =>
    a.length === b.length && a.every((c, i) => normalizeColor(c) === normalizeColor(b[i]));
  return choices.find((p) => same(p.colors, colors)) ?? null;
}

/** Tidies a list someone edited: real colours only, no duplicates, at most 24. */
export function cleanColors(colors: string[]): string[] {
  const out: string[] = [];
  for (const c of colors) {
    const hex = normalizeColor(c);
    if (hex && !out.includes(hex)) out.push(hex);
  }
  return out.slice(0, 24);
}

/** The 10 x 12 grid of colours the palette editor offers, as hue columns from light to dark. */
export function colorGrid(): string[][] {
  const hues = [45, 25, 0, 335, 300, 265, 230, 205, 180, 150, 210, 0];
  const sats = [70, 72, 74, 76, 78, 80, 78, 74, 68, 60];
  const lights = [92, 84, 74, 64, 54, 46, 38, 30, 22, 14];
  return lights.map((l, row) =>
    hues.map((h, col) => {
      // The last two columns are the neutrals: a grey ramp and a near-black ramp.
      const sat = col >= 10 ? (col === 10 ? 12 : 0) : sats[row];
      return hsl(h, sat, l);
    }));
}

function hsl(h: number, s: number, l: number): string {
  const a = (s / 100) * Math.min(l / 100, 1 - l / 100);
  const f = (n: number) => {
    const k = (n + h / 30) % 12;
    const v = l / 100 - a * Math.max(-1, Math.min(k - 3, 9 - k, 1));
    return Math.round(255 * v).toString(16).padStart(2, "0").toUpperCase();
  };
  return `#${f(0)}${f(8)}${f(4)}`;
}
