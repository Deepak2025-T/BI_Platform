import type { ReactNode } from "react";
import type { ReportTemplate } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { PALETTES } from "../lib/report";

type CardTemplate = Pick<ReportTemplate, "name" | "description" | "prompt" | "color" | "layout" | "visibility"> &
  Partial<Pick<ReportTemplate, "is_builtin" | "owner_id" | "owner_name">>;

const CHART_LABEL = { grouped: "Bars", stacked: "Stacked", table: "Table" } as const;

/** One-line summary of what a template sets up, e.g. "3 sections, Stacked, Warm". */
export function layoutSummary(t: CardTemplate) {
  const l = t.layout;
  if (l.kind === "dashboard") {
    const n = (l.widgets ?? []).filter((w) => w.kind !== "text").length;
    return `${l.source_type === "openpages" ? "OpenPages dashboard" : "Dashboard"}, ${n} charts`;
  }
  const parts = [
    l.sections && `${l.sections.length} section${l.sections.length === 1 ? "" : "s"}`,
    l.chart && CHART_LABEL[l.chart],
    l.palette && PALETTES[l.palette].label,
  ].filter(Boolean);
  return parts.length ? parts.join(", ") : "Standard layout";
}

export function visibilityLabel(t: CardTemplate) {
  return t.is_builtin ? "Built-in" : t.visibility === "shared" ? "Shared" : "Only you";
}

interface Props {
  template: CardTemplate;
  /** Makes the whole card a button. */
  onUse?: () => void;
  /** Extra controls under the card (edit, delete ...). */
  actions?: ReactNode;
  selected?: boolean;
}

export default function TemplateCard({ template: t, onUse, actions, selected }: Props) {
  const { user } = useAuth();
  const byline = t.owner_name && !t.is_builtin && t.owner_id !== user?.id ? `, by ${t.owner_name}` : "";
  const body = (
    <>
      <span className="tpl-top">
        <span className="tpl-bar" style={{ background: t.color }} />
        <span className={"tpl-tag" + (t.visibility === "private" && !t.is_builtin ? " private" : "")}>{visibilityLabel(t)}</span>
      </span>
      <span className="strong">{t.name || "Untitled template"}</span>
      <span className="muted small">{t.description || t.prompt || "No description"}</span>
      <span className="tpl-meta">{layoutSummary(t)}{byline}</span>
    </>
  );
  return (
    <div className={"tpl" + (selected ? " on" : "")} style={{ ["--tpl-color" as string]: t.color }}>
      {onUse ? (
        <button type="button" className="tpl-main" onClick={onUse} aria-pressed={selected}>{body}</button>
      ) : (
        <div className="tpl-main">{body}</div>
      )}
      {actions && <div className="tpl-actions">{actions}</div>}
    </div>
  );
}
