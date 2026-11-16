import { Link } from "react-router-dom";
import type { ReportTemplate, TemplateCategory } from "../api/types";
import { CATEGORY_BLURBS, TEMPLATE_CATEGORIES } from "../lib/report";
import Icon from "./Icon";

/** The face each domain puts on. Nothing turns on it; it is there so the four read apart. */
const DOMAIN_ICON: Record<TemplateCategory, string> = {
  ERP: "database",
  GRC: "check",
  Common: "grid",
  Uncategorised: "template",
};

interface Props {
  templates: ReportTemplate[];
  /** Given on the Templates page, where picking a domain stays on the page. */
  onPick?: (domain: TemplateCategory) => void;
  /** Shown as a last tile, for making one of your own. */
  onNew?: () => void;
}

/**
 * The top level of the template hierarchy: one tile per domain, with how many are filed under it.
 *
 * There are well over a hundred templates. Laid out flat they are a wall that says nothing about
 * what is in it, so the first thing anyone sees is four doors instead. Nothing is left out - every
 * template is behind one of these, and search still reaches all of them at once.
 */
export default function DomainTiles({ templates, onPick, onNew }: Props) {
  const counts = TEMPLATE_CATEGORIES.map((c) => [c, templates.filter((t) => t.category === c).length] as const)
    .filter(([, n]) => n > 0);

  return (
    <div className="domain-grid">
      {counts.map(([domain, count]) => {
        const body = (
          <>
            <span className="domain-icon" aria-hidden="true"><Icon name={DOMAIN_ICON[domain]} size={20} /></span>
            <span className="strong">{domain}</span>
            <span className="muted small">{CATEGORY_BLURBS[domain]}</span>
            <span className="domain-count">{count} template{count === 1 ? "" : "s"}</span>
          </>
        );
        return onPick ? (
          <button key={domain} type="button" className="domain-tile" onClick={() => onPick(domain)}>{body}</button>
        ) : (
          <Link key={domain} to={`/templates?domain=${encodeURIComponent(domain)}`} className="domain-tile">{body}</Link>
        );
      })}
      {onNew && (
        <button type="button" className="domain-tile domain-new" onClick={onNew}>
          <span className="domain-icon" aria-hidden="true"><Icon name="plus" size={20} /></span>
          <span className="strong">New template</span>
          <span className="muted small">Save your own question and layout</span>
        </button>
      )}
    </div>
  );
}
