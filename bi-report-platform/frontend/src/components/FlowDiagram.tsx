import type { CSSProperties } from "react";
import Icon from "./Icon";

export interface FlowStep {
  /** Icon name from the shared icon set. */
  icon: string;
  label: string;
  /** The live detail under the label, e.g. the chosen model or database. */
  sub: string;
  /** Greyed out when this step is not part of the current plan. */
  dim?: boolean;
}

// The viewBox is padded either side of these so the first and last labels,
// which are centred on their badge, have room to sit without being clipped.
const X = [60, 260, 460, 660];
const CY = 46;
const R = 30; // half the badge, so links start and end at its edge

const clip = (s: string, n = 20) => (s.length > n ? s.slice(0, n - 1) + "…" : s);

/**
 * The four stages a question travels through, drawn as one animated SVG.
 * Every label is live, so the picture changes as the question, model and
 * database change. Motion is CSS only and stops under prefers-reduced-motion.
 */
export default function FlowDiagram({ steps, live }: { steps: FlowStep[]; live: boolean }) {
  return (
    <svg
      className={"flow" + (live ? " on" : "")}
      viewBox="-40 0 800 132"
      preserveAspectRatio="xMidYMid meet"
      role="img"
      aria-label={steps.map((s) => `${s.label}, ${s.sub}`).join(", then ")}
    >
      {steps.slice(0, -1).map((_, i) => {
        const from = X[i] + R;
        const to = X[i + 1] - R;
        const faded = steps[i].dim || steps[i + 1].dim;
        return (
          <g key={`link-${i}`} className={"flow-link" + (faded ? " dim" : "")} style={{ "--d": `${i * 0.5}s` } as CSSProperties}>
            <line className="flow-rail" x1={from} y1={CY} x2={to} y2={CY} />
            <line className="flow-pulse" x1={from} y1={CY} x2={to} y2={CY} />
            <circle className="flow-dot" cx={from} cy={CY} r="3.5" style={{ "--run": `${to - from}px` } as CSSProperties} />
          </g>
        );
      })}

      {steps.map((s, i) => (
        <g key={s.label} className={"flow-node" + (s.dim ? " dim" : "")} style={{ "--d": `${i * 0.12}s` } as CSSProperties}>
          <circle className="flow-halo" cx={X[i]} cy={CY} r={R} />
          <rect className="flow-badge" x={X[i] - R} y={CY - R} width={R * 2} height={R * 2} rx="17" />
          <g className="flow-icon" transform={`translate(${X[i] - 13} ${CY - 13})`}>
            <Icon name={s.icon} size={26} />
          </g>
          <text className="flow-label" x={X[i]} y={CY + R + 22} textAnchor="middle">{s.label}</text>
          <text className="flow-sub" x={X[i]} y={CY + R + 39} textAnchor="middle">{clip(s.sub)}</text>
        </g>
      ))}
    </svg>
  );
}
