import type { CSSProperties } from "react";
import type { DashboardConfig, ReportFont, ReportTypography, WidgetStyle } from "../api/types";
import { isDark } from "./cardColors";

/**
 * How a report and its tiles are set: font, size, weight, spacing, borders and where a heading
 * sits.
 *
 * All of it is optional and all of it is absent on every report saved before it existed, so a
 * report that says nothing here looks exactly as it always did. Each setting is written as a CSS
 * variable on the element it belongs to and read by one rule in the stylesheet, rather than as a
 * pile of inline properties: a variable set on the report is inherited by every tile, which is
 * what makes "change the report's font" one change instead of one per chart.
 */

/** The fonts a report can be set in. Each is a stack that needs no web font to work. */
export const FONTS: { key: ReportFont; label: string; stack: string; hint: string }[] = [
  { key: "", label: "Default", stack: "", hint: "The app's own typeface." },
  { key: "system", label: "System", stack: 'system-ui, "Segoe UI", Roboto, sans-serif',
    hint: "Whatever this computer uses for its own windows." },
  { key: "serif", label: "Serif", stack: 'Georgia, "Times New Roman", serif',
    hint: "For a report that will be printed or read as a document." },
  { key: "mono", label: "Monospace", stack: 'var(--mono)',
    hint: "Every character the same width, so figures line up." },
];

/** Text sizes offered, in pixels. 14 is what the app uses everywhere else. */
export const FONT_SIZES: [number, string][] = [
  [12, "Small"], [13, "Compact"], [14, "Default"], [15, "Comfortable"], [16, "Large"], [18, "Larger"], [20, "Largest"],
];

/** Space inside a tile's edge, in pixels. 18 is the app's card padding. */
export const PADDINGS: [number, string][] = [
  [8, "Tight"], [12, "Snug"], [18, "Default"], [24, "Roomy"], [32, "Generous"],
];

/** How thick a tile's border is. 0 is none; 1 is the app's hairline. */
export const BORDER_WIDTHS: [number, string][] = [[0, "None"], [1, "Hairline"], [2, "Medium"], [3, "Thick"]];

/** How round a tile's corners are, in pixels. 12 is the app's. */
export const RADII: [number, string][] = [[0, "Square"], [6, "Slight"], [12, "Default"], [20, "Round"]];

export const ALIGNMENTS: [NonNullable<WidgetStyle["align"]>, string][] =
  [["left", "Left"], ["center", "Centre"], ["right", "Right"]];

export const V_ALIGNMENTS: [NonNullable<WidgetStyle["vAlign"]>, string][] =
  [["top", "Top"], ["middle", "Middle"], ["bottom", "Bottom"]];

/** Border colours offered: the app's own lines first, then something to pick a tile out with. */
export const BORDER_COLORS = ["#DCE5EE", "#CFDCE8", "#0D3B66", "#00B4D8", "#2A9D8F", "#F5A623", "#A63D40", "#1A2332"];

/** Colours for words: dark enough to read on a pale card, pale enough to read on a dark one. */
export const TEXT_COLORS = ["#1A2332", "#4A5568", "#0D3B66", "#00779E", "#1E5B3A", "#8A2A1F", "#6D597A", "#FFFFFF"];

/** Heading sizes for a heading tile, in pixels. 19 is what a heading has always been. */
export const HEADING_SIZES: [number, string][] = [
  [15, "Small"], [17, "Medium"], [19, "Default"], [24, "Large"], [30, "Huge"], [38, "Banner"],
];

/** Where a tile narrower than its row sits in it. */
export const JUSTIFIES: [NonNullable<WidgetStyle["justify"]>, string][] =
  [["left", "Left"], ["center", "Centre"], ["right", "Right"]];

const FONT_STACK = new Map(FONTS.map((f) => [f.key, f.stack]));

/** The CSS font stack for a font key, or "" for the app's own. */
export const fontStack = (font?: ReportFont): string => FONT_STACK.get(font ?? "") ?? "";

/** A number only when it is one and within range, so a hand-edited config can't break a layout. */
function within(value: unknown, low: number, high: number): number | undefined {
  return typeof value === "number" && Number.isFinite(value) && value >= low && value <= high
    ? value : undefined;
}

/** The variables a whole report's font and size set, read by every tile under it. */
export function reportLook(typography?: ReportTypography): CSSProperties {
  const vars: Record<string, string> = {};
  const stack = fontStack(typography?.font);
  if (stack) vars["--report-font"] = stack;
  const size = within(typography?.fontSize, 10, 28);
  if (size) vars["--report-size"] = `${size}px`;
  return vars as CSSProperties;
}

/**
 * Class names and variables for one tile.
 *
 * Header and card colours were here first (lib/cardColors) and still behave the same way; this
 * adds the rest of the look around them. A tile that sets nothing gets an empty class name and no
 * variables, so it is drawn by the plain stylesheet with no inline anything.
 */
export function tileLook(style?: WidgetStyle): { className: string; style: CSSProperties } {
  const vars: Record<string, string> = {};
  let className = "";

  if (style?.cardBg) {
    vars["--card-bg"] = style.cardBg;
    className += " has-card-bg" + (isDark(style.cardBg) ? " dark-card" : "");
  }
  if (style?.headBg) {
    vars["--head-bg"] = style.headBg;
    vars["--head-fg"] = isDark(style.headBg) ? "#FFFFFF" : "#1A2332";
    className += " has-head-bg";
  }
  // Set by hand, the tile's words are that colour whatever is behind them: a choice beats the
  // automatic white-on-dark, which is only there to keep an unset tile readable.
  if (style?.textColor) {
    vars["--tile-fg"] = style.textColor;
    className += " has-fg";
  }
  const heading = within(style?.headingSize, 10, 64);
  if (heading !== undefined) {
    vars["--tile-heading"] = `${heading}px`;
    className += " has-heading-size";
  }
  if (style?.justify && style.justify !== "left") className += ` justify-${style.justify}`;

  const stack = fontStack(style?.font);
  if (stack) {
    vars["--tile-font"] = stack;
    className += " has-font";
  }
  const size = within(style?.fontSize, 10, 28);
  if (size) {
    vars["--tile-size"] = `${size}px`;
    className += " has-size";
  }
  if (style?.bold) className += " tile-bold";

  if (style?.align && style.align !== "left") className += ` align-${style.align}`;
  if (style?.vAlign && style.vAlign !== "middle") className += ` valign-${style.vAlign}`;

  const padding = within(style?.padding, 0, 48);
  if (padding !== undefined) {
    vars["--tile-pad"] = `${padding}px`;
    className += " has-pad";
  }

  // A width of 0 is "no border", which is a real choice and not the same as saying nothing, so it
  // is kept rather than treated as missing.
  const borderWidth = within(style?.borderWidth, 0, 8);
  if (borderWidth !== undefined) {
    vars["--tile-border-w"] = `${borderWidth}px`;
    className += " has-border";
  }
  if (style?.border) {
    vars["--tile-border"] = style.border;
    className += " has-border";
  }
  const radius = within(style?.radius, 0, 32);
  if (radius !== undefined) {
    vars["--tile-radius"] = `${radius}px`;
    className += " has-radius";
  }

  return { className, style: vars as CSSProperties };
}

/** Whether a tile is set in anything other than the report's own look. */
export const isStyled = (style?: WidgetStyle): boolean =>
  !!(style && (style.headBg || style.cardBg || style.textColor || style.legendColor || style.font
    || style.fontSize || style.bold || style.align || style.vAlign || style.justify
    || style.headingSize !== undefined || style.padding !== undefined || style.border
    || style.borderWidth !== undefined || style.radius !== undefined));

/** Everything the look panel sets, cleared. Used by "Reset this tile's look". */
export const CLEARED_LOOK: Partial<WidgetStyle> = {
  headBg: undefined, cardBg: undefined, textColor: undefined, legendColor: undefined,
  font: undefined, fontSize: undefined, bold: undefined, align: undefined, vAlign: undefined,
  justify: undefined, headingSize: undefined, padding: undefined, border: undefined,
  borderWidth: undefined, radius: undefined,
};

/** The report's own look, as a sentence for the panel that overrides it. */
export function typographyLabel(config: Pick<DashboardConfig, "typography">): string {
  const font = FONTS.find((f) => f.key === (config.typography?.font ?? ""))?.label ?? "Default";
  const size = config.typography?.fontSize ?? 14;
  return `${font}, ${size}px`;
}
