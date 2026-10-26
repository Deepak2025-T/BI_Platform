import type { CSSProperties } from "react";
import type { WidgetStyle } from "../api/types";

/** Header band colours: strong brand colours, then soft tints. */
export const HEADER_COLORS = ["#00B4D8", "#0D3B66", "#2A9D8F", "#F5A623", "#A63D40", "#6D597A", "#1E7F4F", "#E3F4FA", "#EEF3F7", "#FFF1D6"];
/** Card backgrounds: soft tints that keep charts readable, and one dark. */
export const CARD_COLORS = ["#F4FAFD", "#F5F7FA", "#FFF8EC", "#EFF8F3", "#FBF0F1", "#F5F1F9", "#0D1B2A"];

/** True for colours where white text has more contrast than the app's dark text (#1A2332). */
export function isDark(hex?: string): boolean {
  const m = /^#?([0-9a-f]{6})$/i.exec(hex ?? "");
  if (!m) return false;
  const n = parseInt(m[1], 16);
  const [r, g, b] = [n >> 16, (n >> 8) & 255, n & 255].map((c) => {
    const v = c / 255;
    return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4;
  });
  const lum = 0.2126 * r + 0.7152 * g + 0.0722 * b;
  const DARK_TEXT = 0.016; // luminance of #1A2332
  return 1.05 / (lum + 0.05) > (lum + 0.05) / (DARK_TEXT + 0.05);
}

/** Class names and CSS variables for a tile with card and header colours. */
export function cardLook(style?: WidgetStyle): { className: string; style: CSSProperties } {
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
  return { className, style: vars as CSSProperties };
}
