import type { QuickAction, Suggestion } from "../api/types";
import Icon from "./Icon";

/**
 * Suggested next steps and quick actions, used in chat and around reports.
 *
 * Questions are round chips with a speech bubble; a suggestion that adds a chart has a dashed edge
 * and a plus; quick actions are squarer outlined buttons with their own icons - so a glance tells
 * "ask this" from "do this". On a narrow screen each row scrolls sideways instead of wrapping
 * into a wall of chips.
 */

const CATEGORY_LABEL: Record<Suggestion["category"], string> = {
  basic: "Basic question",
  analytical: "Analytical question",
  advanced: "Advanced question",
  recent: "You asked this before",
};

function chipIcon(s: Suggestion) {
  if (s.category === "recent") return "clock";
  return s.kind === "chart" ? "plus" : "chat";
}

interface ChipsProps {
  title: string;
  items: Suggestion[];
  loading?: boolean;
  error?: string;
  /** "fallback" says these were worked out from the columns rather than written by the model. */
  origin?: "ai" | "fallback";
  notice?: string;
  onPick: (s: Suggestion) => void;
  onRefresh?: () => void;
  onDismiss?: () => void;
  disabled?: boolean;
  /** What a chip does when clicked, for the tooltip: "fills the box" or "asks it". */
  pickHint?: string;
}

export function SuggestionChips({ title, items, loading, error, origin, notice, onPick, onRefresh, onDismiss,
                                  disabled, pickHint }: ChipsProps) {
  if (!loading && !error && !items.length) return null;
  return (
    <section className="sugg no-print" aria-label={title} aria-busy={loading || undefined}>
      <header className="sugg-head">
        <Icon name="spark" size={15} className="sugg-spark" />
        <span className="sugg-title">{title}</span>
        {origin === "fallback" && !loading && items.length > 0 && (
          <span className="sugg-origin" title={notice || "Worked out from the database's columns, without the AI model."}>
            from the columns
          </span>
        )}
        <span className="grow" />
        {onRefresh && (
          <button type="button" className="icon-btn sm" onClick={onRefresh} disabled={loading}
            aria-label="Suggest different ones" title="Suggest different ones"><Icon name="refresh" size={14} /></button>
        )}
        {onDismiss && (
          <button type="button" className="icon-btn sm" onClick={onDismiss}
            aria-label={`Hide ${title.toLowerCase()}`} title="Hide"><Icon name="x" size={14} /></button>
        )}
      </header>
      {error && !loading ? (
        <div className="sugg-error small" role="alert">
          <span>{error}</span>
          {onRefresh && <button type="button" className="link-btn small" onClick={onRefresh}>Try again</button>}
        </div>
      ) : (
        <div className="sugg-chips">
          {loading && !items.length && (
            <>
              <span className="sugg-skel" aria-hidden="true" />
              <span className="sugg-skel w2" aria-hidden="true" />
              <span className="sugg-skel" aria-hidden="true" />
              <span className="sr-only">Working out suggestions…</span>
            </>
          )}
          {items.map((s) => (
            <button key={s.id + s.text} type="button" disabled={disabled || loading}
              className={`sugg-chip is-${s.kind} is-${s.category}`} onClick={() => onPick(s)}
              title={`${CATEGORY_LABEL[s.category] ?? "Suggestion"}${s.kind === "chart" ? " · adds a chart" : ""}${pickHint ? ` · ${pickHint}` : ""}`}>
              <Icon name={chipIcon(s)} size={14} className="sugg-ico" />
              <span>{s.text}</span>
            </button>
          ))}
        </div>
      )}
    </section>
  );
}

const ACTION_ICON: Record<string, string> = {
  change_chart: "trend", view_rows: "grid", view_sql: "database", export_csv: "download",
  compare_period: "history", compare_periods: "history", add_to_report: "plus", build_report: "reports",
  ask_about: "chat", add_chart: "plus", executive_summary: "spark", export_excel: "download",
  export_ppt: "download", build_another: "grid",
};

interface ActionsProps {
  actions: QuickAction[];
  onAction: (id: string) => void;
  /** The action still working, shown with a spinner and the others held. */
  busy?: string | null;
  /** Actions with these ids are on, e.g. the rows or the SQL being shown. */
  pressed?: string[];
  title?: string;
}

export function QuickActions({ actions, onAction, busy, pressed = [], title = "Quick actions" }: ActionsProps) {
  if (!actions.length) return null;
  return (
    <div className="qa no-print" role="group" aria-label={title}>
      <span className="qa-title"><Icon name="bolt" size={13} />{title}</span>
      <div className="qa-row">
        {actions.map((a) => {
          const on = pressed.includes(a.id);
          return (
            <button key={a.id} type="button" className={"qa-btn" + (on ? " on" : "")} disabled={!!busy}
              aria-pressed={pressed.length ? on : undefined} onClick={() => onAction(a.id)}>
              {busy === a.id ? <span className="spinner sm" aria-hidden="true" />
                : <Icon name={ACTION_ICON[a.id] ?? "bolt"} size={14} />}
              {a.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}
