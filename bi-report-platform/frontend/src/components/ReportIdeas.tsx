import type { IdeaReason, ReportIdea } from "../api/types";
import Icon from "./Icon";

/**
 * What to build on the database that has just been chosen.
 *
 * A blank box asks the person to know both what they want and how to ask for it. This asks the
 * question the other way round - here is what this database can show you, pick one - and every
 * card fills the box with a full request they can then edit, rather than building anything behind
 * their back. Nothing here costs a model call, so it appears with the database.
 */

const LOOKS: Record<IdeaReason, { icon: string; group: string }> = {
  // Their own past requests come first and are marked as theirs, so a familiar title is
  // recognisable as something they wrote rather than something the tool invented.
  history: { icon: "clock", group: "You built this before" },
  subject: { icon: "grid", group: "What this database holds" },
  breadth: { icon: "layers", group: "Everything at once" },
  // The period-over-period numbers people track whatever the subject.
  kpi: { icon: "trend", group: "Common KPIs" },
  // Written by hand against the published OpenPages object model, not worked out from the
  // connection - so they are not described as coming from what it holds.
  curated: { icon: "template", group: "IBM OpenPages reference reports" },
};

interface Props {
  ideas: ReportIdea[];
  sourceName: string;
  /** Puts the request in the box, where it can be read and changed before it is sent. */
  onPick: (idea: ReportIdea) => void;
  /** Set while the suggestions for a newly chosen database are still on their way. */
  loading?: boolean;
  onHide?: () => void;
}

export default function ReportIdeas({ ideas, sourceName, onPick, loading, onHide }: Props) {
  if (loading) {
    return (
      <div className="idea-panel" aria-busy="true">
        <p className="muted small">Working out what {sourceName} can show you…</p>
      </div>
    );
  }
  if (!ideas.length) return null;
  // Every idea curated, not merely some: the subtitle has to describe the whole list.
  const curated = ideas.every((i) => i.reason === "curated");

  return (
    <section className="idea-panel" aria-label={`Reports worth building on ${sourceName}`}>
      <header className="idea-head">
        <div>
          <h3>What kind of report would you like?</h3>
          <p className="muted small">
            {curated
              ? <>One per namespace of the IBM OpenPages reporting framework, each written against
                  that namespace's own object model. Pick one to fill the box — you can change the
                  words before building.</>
              : <>From what {sourceName} holds and what you have asked for before. Pick one to fill
                  the box — you can change the words before building.</>}
          </p>
        </div>
        {onHide && (
          <button type="button" className="link-btn small" onClick={onHide}
            title="Hide these suggestions and type my own">I'll write my own</button>
        )}
      </header>

      <div className="idea-grid">
        {ideas.map((idea) => {
          const look = LOOKS[idea.reason] ?? LOOKS.subject;
          return (
            <button key={idea.id} type="button" className={`idea-card is-${idea.reason}`}
              onClick={() => onPick(idea)} title={idea.prompt}>
              <span className="idea-icon" aria-hidden="true"><Icon name={look.icon} size={16} /></span>
              <span className="idea-title">{idea.title}</span>
              <span className="idea-why">{idea.why}</span>
              {!!idea.kpis?.length && (
                <span className="idea-kpis" aria-label="Headline numbers">
                  {idea.kpis.slice(0, 3).map((k) => <span key={k} className="idea-kpi">{k}</span>)}
                </span>
              )}
              {idea.charts > 0 && (
                <span className="idea-count">
                  about {idea.charts} {idea.charts === 1 ? "chart" : "charts"}
                </span>
              )}
              <span className="sr-only">{look.group}</span>
            </button>
          );
        })}
      </div>
    </section>
  );
}
