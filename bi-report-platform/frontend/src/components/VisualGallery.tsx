import type { ChartType } from "../api/types";
import { VISUAL_GROUPS, VISUALS, type VisualDef } from "../lib/visuals";

/** A small drawing of each shape, so the gallery reads at a glance like Power BI's. */
function Glyph({ chart, style }: { chart: ChartType; style?: VisualDef["style"] }) {
  const a = "var(--accent)", b = "#7A8BA3";
  const bars = (xs: number[], horizontal?: boolean) =>
    xs.map((h, i) => (horizontal
      ? <rect key={i} x={2} y={3 + i * 5} width={h} height={3} rx={1} fill={i % 2 ? b : a} />
      : <rect key={i} x={3 + i * 5} y={18 - h} width={3} height={h} rx={1} fill={i % 2 ? b : a} />));

  switch (chart) {
    case "bar":
      if (style?.horizontal) return <svg viewBox="0 0 22 22">{bars([14, 9, 17], true)}</svg>;
      if (style?.stackMode === "full") return (
        <svg viewBox="0 0 22 22">{[0, 1, 2].map((i) => (
          <g key={i}><rect x={3 + i * 5} y={4} width={3} height={7} rx={1} fill={a} />
            <rect x={3 + i * 5} y={11} width={3} height={7} rx={1} fill={b} /></g>))}</svg>
      );
      if (style?.stackMode === "stacked") return (
        <svg viewBox="0 0 22 22">{[0, 1, 2].map((i) => (
          <g key={i}><rect x={3 + i * 5} y={10 - i} width={3} height={4} rx={1} fill={a} />
            <rect x={3 + i * 5} y={14 - i} width={3} height={4 + i} rx={1} fill={b} /></g>))}</svg>
      );
      return <svg viewBox="0 0 22 22">{bars([13, 8, 16])}</svg>;
    case "line":
      return <svg viewBox="0 0 22 22"><polyline points="3,15 8,9 13,12 19,4" fill="none" stroke={a} strokeWidth="2"
        strokeLinecap="round" strokeLinejoin="round" /></svg>;
    case "area":
      return <svg viewBox="0 0 22 22"><path d="M3 15 L8 9 L13 12 L19 5 L19 18 L3 18 Z" fill={a} opacity=".35" />
        <polyline points="3,15 8,9 13,12 19,5" fill="none" stroke={a} strokeWidth="2" strokeLinejoin="round" /></svg>;
    case "combo":
      return <svg viewBox="0 0 22 22">{bars([9, 13, 7])}
        <polyline points="4,8 9,5 14,10 19,3" fill="none" stroke="#F5A623" strokeWidth="2" strokeLinejoin="round" /></svg>;
    case "pie":
      return <svg viewBox="0 0 22 22"><circle cx="11" cy="11" r="8" fill={b} />
        <path d="M11 11 L11 3 A8 8 0 0 1 18 14 Z" fill={a} /></svg>;
    case "donut":
      return <svg viewBox="0 0 22 22"><circle cx="11" cy="11" r="7.5" fill="none" stroke={b} strokeWidth="4" />
        <circle cx="11" cy="11" r="7.5" fill="none" stroke={a} strokeWidth="4"
          strokeDasharray="18 47" transform="rotate(-90 11 11)" /></svg>;
    case "scatter":
      return <svg viewBox="0 0 22 22">{[[5, 15], [9, 8], [13, 12], [17, 5], [8, 16]].map(([x, y], i) => (
        <circle key={i} cx={x} cy={y} r="2" fill={i % 2 ? b : a} />))}</svg>;
    case "table":
      return <svg viewBox="0 0 22 22"><rect x="3" y="4" width="16" height="14" rx="1.5" fill="none" stroke={b} />
        <line x1="3" y1="9" x2="19" y2="9" stroke={a} strokeWidth="1.5" />
        <line x1="11" y1="4" x2="11" y2="18" stroke={b} /></svg>;
    case "matrix":
      return <svg viewBox="0 0 22 22"><rect x="3" y="4" width="16" height="14" rx="1.5" fill="none" stroke={b} />
        <line x1="3" y1="9" x2="19" y2="9" stroke={a} strokeWidth="1.5" />
        <line x1="8" y1="4" x2="8" y2="18" stroke={a} strokeWidth="1.5" />
        <line x1="13.5" y1="4" x2="13.5" y2="18" stroke={b} /></svg>;
    case "kpi":
      return <svg viewBox="0 0 22 22"><rect x="3" y="6" width="16" height="10" rx="2" fill="none" stroke={b} />
        <text x="11" y="14.5" textAnchor="middle" fontSize="8" fontWeight="700" fill={a}>42</text></svg>;
    case "gauge":
      return <svg viewBox="0 0 22 22"><path d="M4 16 A7 7 0 0 1 18 16" fill="none" stroke={b} strokeWidth="2.5"
        strokeLinecap="round" /><path d="M4 16 A7 7 0 0 1 9 9.4" fill="none" stroke={a} strokeWidth="2.5"
          strokeLinecap="round" /><line x1="11" y1="16" x2="14" y2="11" stroke={a} strokeWidth="1.5" strokeLinecap="round" /></svg>;
    default:
      return <svg viewBox="0 0 22 22"><rect x="4" y="4" width="14" height="14" rx="2" fill={b} /></svg>;
  }
}

/** The chart picker. Choosing one keeps whatever fields still fit its wells. */
export default function VisualGallery({ value, onChange }: { value: string; onChange: (id: string) => void }) {
  return (
    <div className="visual-gallery">
      {VISUAL_GROUPS.map((group) => (
        <div key={group} className="visual-group">
          <div className="visual-group-label">{group}</div>
          <div className="visual-grid">
            {VISUALS.filter((v) => v.group === group).map((v) => (
              <button key={v.id} type="button" title={v.label} aria-pressed={v.id === value}
                className={`visual-tile${v.id === value ? " on" : ""}`} onClick={() => onChange(v.id)}>
                <Glyph chart={v.chart} style={v.style} />
                <span className="sr-only">{v.label}</span>
              </button>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
