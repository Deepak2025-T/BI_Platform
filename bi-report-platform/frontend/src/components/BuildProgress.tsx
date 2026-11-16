import { useLocation, useNavigate } from "react-router-dom";
import { estimatedShare, stageFor, useBuildJob } from "../lib/buildJob";
import Icon from "./Icon";

/** "1:05" for a minute and five seconds, "48s" below a minute. */
export function elapsedText(seconds: number): string {
  const whole = Math.max(0, Math.floor(seconds));
  if (whole < 60) return `${whole}s`;
  return `${Math.floor(whole / 60)}:${String(whole % 60).padStart(2, "0")}`;
}

interface RingProps {
  /** 0 to 1. */
  share: number;
  size?: number;
  /** Shown in the middle; the percentage by default. */
  label?: string;
}

/**
 * A circle that fills as the build goes on, with the share written in the middle.
 *
 * The number is an estimate from the time elapsed, not a count of work done, so wherever this is
 * used the words beside it say so.
 */
export function ProgressRing({ share, size = 44, label }: RingProps) {
  const stroke = Math.max(3, Math.round(size / 11));
  const r = (size - stroke) / 2;
  const circumference = 2 * Math.PI * r;
  const percent = Math.round(share * 100);
  return (
    <svg className="ring" width={size} height={size} viewBox={`0 0 ${size} ${size}`} role="img"
      aria-label={`About ${percent} percent of the way through`}>
      <circle className="ring-track" cx={size / 2} cy={size / 2} r={r} strokeWidth={stroke} fill="none" />
      <circle className="ring-fill" cx={size / 2} cy={size / 2} r={r} strokeWidth={stroke} fill="none"
        strokeDasharray={circumference} strokeDashoffset={circumference * (1 - share)} strokeLinecap="round"
        transform={`rotate(-90 ${size / 2} ${size / 2})`} />
      <text className="ring-text" x="50%" y="50%" dominantBaseline="central" textAnchor="middle"
        fontSize={size / 3.4}>{label ?? `${percent}%`}</text>
    </svg>
  );
}

/**
 * The build that is still running, shown in the corner of whatever page the person is on.
 *
 * It is the visible half of the promise the Build page makes: go and do something else, this
 * keeps going. The full page at /build says the same thing in more room, so the corner stays
 * quiet while the person is actually watching it there.
 */
export default function BuildProgress() {
  const { job, elapsed, clear } = useBuildJob();
  const navigate = useNavigate();
  const onBuildPage = useLocation().pathname === "/build";
  if (!job || onBuildPage) return null;

  if (job.error) {
    return (
      <div className="build-pill build-pill-bad" role="status">
        <Icon name="info" size={20} className="bad" />
        <div className="grow">
          <div className="strong small">The report couldn&rsquo;t be built</div>
          <div className="muted small">{job.error}</div>
        </div>
        <button className="icon-btn" aria-label="Dismiss" onClick={clear}><Icon name="x" size={16} /></button>
      </div>
    );
  }

  if (job.result) {
    const { reportId, title, charts, failed } = job.result;
    return (
      <div className="build-pill" role="status">
        <Icon name="check" size={22} className="ok" />
        <div className="grow">
          <div className="strong small">{title}</div>
          <div className="muted small">Ready, {charts} charts</div>
        </div>
        <button className="btn btn-primary btn-sm"
          onClick={() => { clear(); navigate(`/reports/${reportId}/edit`, { state: { failed } }); }}>Open</button>
        <button className="icon-btn" aria-label="Dismiss" onClick={clear}><Icon name="x" size={16} /></button>
      </div>
    );
  }

  const share = estimatedShare(elapsed);
  return (
    <button className="build-pill build-pill-live" onClick={() => navigate("/build")} aria-live="polite">
      <ProgressRing share={share} size={40} />
      <span className="grow build-pill-text">
        <span className="strong small">Building your report</span>
        <span className="muted small">{stageFor(share)} · {elapsedText(elapsed)}</span>
      </span>
      <Icon name="arrow" size={16} className="faint" />
    </button>
  );
}
