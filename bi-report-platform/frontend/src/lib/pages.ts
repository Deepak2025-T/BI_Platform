/**
 * Reports in more than one page, the way a workbook has sheets.
 *
 * A template like the ORM overview is nearly forty charts. On one scroll that is a wall; split
 * into Overview, Risk profile, Control effectiveness, Process coverage and Business entity scope
 * it is five short pages, each of which answers one question and fits on a screen.
 *
 * Pages are optional and additive. A report with none - every report saved before this existed -
 * has one implied page holding everything, draws no tab bar, and behaves exactly as it did.
 */

import type { DashboardConfig, DashboardPage, Widget } from "../api/types";

/** One page of a report. The same shape the config saves (api/types DashboardPage). */
export type Page = DashboardPage;

/** The id the single implied page goes by when a report has no pages of its own. */
export const ONE_PAGE = "main";

const newId = () => Math.random().toString(16).slice(2, 10);

/** The report's pages, or the one implied page. Never empty, so callers need no special case. */
export function pagesOf(config: Pick<DashboardConfig, "pages">): Page[] {
  const pages = (config.pages ?? []).filter((p) => p && p.id);
  return pages.length ? pages : [{ id: ONE_PAGE, name: "Report" }];
}

/**
 * Which page a widget is on.
 *
 * A widget with no page, or one naming a page that has since been deleted, belongs to the first
 * page. That is what keeps a half-edited report readable: a tile can be orphaned by an edit, but
 * it can never become invisible.
 */
export function pageOf(pages: Page[], widget: Pick<Widget, "page">): string {
  const named = widget.page;
  return named && pages.some((p) => p.id === named) ? named : pages[0].id;
}

/** The widgets on one page, each with its index in the report, which is what edits act on. */
export function widgetsOn(config: Pick<DashboardConfig, "pages" | "widgets">, pageId: string) {
  const pages = pagesOf(config);
  return config.widgets
    .map((w, index) => ({ widget: w, index }))
    .filter(({ widget }) => pageOf(pages, widget) === pageId);
}

/**
 * The report split into one page per heading, or null when there is nothing worth splitting.
 *
 * The headings are already the report's own sections, written by whoever built it, so they are a
 * better set of page breaks than anything this could invent. Whatever sits above the first
 * heading - the row of totals, usually - becomes the page people land on.
 */
export function splitByHeadings(widgets: Widget[]): { pages: Page[]; widgets: Widget[] } | null {
  const headings = widgets.filter((w) => w.kind === "text" && w.title.trim());
  if (headings.length < 2) return null;

  const pages: Page[] = [];
  const out: Widget[] = [];
  let current = "";

  for (const w of widgets) {
    if (w.kind === "text" && w.title.trim()) {
      current = newId();
      pages.push({ id: current, name: w.title.trim() });
      // The heading became the tab, so repeating it at the top of its own page says it twice.
      // Its explanatory text is worth keeping, so a heading that has some stays as a note.
      if (w.text?.trim()) out.push({ ...w, page: current, title: "" });
      continue;
    }
    if (!current) {
      // Above the first heading: the opening page, made only once something lands on it.
      if (!pages.length) { current = newId(); pages.push({ id: current, name: "Overview" }); }
      else current = pages[0].id;
    }
    out.push({ ...w, page: current });
  }

  // A heading with nothing under it would be an empty tab.
  const used = new Set(out.map((w) => w.page));
  const kept = pages.filter((p) => used.has(p.id));
  return kept.length > 1 ? { pages: kept, widgets: out } : null;
}

/** A page to add, named so it doesn't collide with one already there. */
export function nextPage(pages: Page[]): Page {
  const taken = new Set(pages.map((p) => p.name.toLowerCase()));
  let n = pages.length + 1;
  while (taken.has(`page ${n}`)) n += 1;
  return { id: newId(), name: `Page ${n}` };
}
