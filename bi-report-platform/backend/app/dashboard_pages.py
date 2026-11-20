"""
Splitting a long report into pages, the way a workbook has sheets.

The ORM overview is nearly forty charts. On one scroll that is a wall nobody reads to the bottom
of; split into Overview, Risk profile, Control effectiveness, Process coverage and Business entity
scope it is five short pages, each answering one question.

The section headings a template already carries are the split: whoever wrote the template decided
where one subject ends and the next begins, which is a better set of page breaks than anything
worked out from the charts. Whatever sits above the first heading - the row of totals, usually -
becomes the page people land on.

Pages are optional everywhere they appear. A report built without them, and every report saved
before this existed, has one implied page holding everything and draws no tabs.
"""

import uuid

# Below this many charts a report reads perfectly well on one scroll, and tabs are an extra click
# on the way to something that was already in front of you.
SPLIT_OVER = 12

# What the first page is called when the report opens with totals rather than a heading.
FIRST_PAGE = "Overview"


def _is_heading(widget: dict) -> bool:
    return widget.get("kind") == "text" and str(widget.get("title") or "").strip() != ""


def split_by_headings(widgets: list[dict], split_over: int = SPLIT_OVER) -> tuple[list[dict], list[dict]]:
    """(pages, widgets) with each widget given the page it belongs on.

    Returns ([], widgets) unchanged when there is nothing worth splitting: fewer than two
    headings, or few enough charts that one page is the friendlier answer."""
    headings = [w for w in widgets if _is_heading(w)]
    charts = [w for w in widgets if w.get("kind") not in ("text", "media")]
    if len(headings) < 2 or len(charts) < split_over:
        return [], widgets

    pages: list[dict] = []
    out: list[dict] = []
    current = ""

    for widget in widgets:
        if _is_heading(widget):
            current = uuid.uuid4().hex[:8]
            pages.append({"id": current, "name": str(widget["title"]).strip()[:60]})
            # The heading is the tab now, so repeating it at the top of its own page says it
            # twice. Its explanatory line is worth keeping, so one that has text stays as a note.
            if str(widget.get("text") or "").strip():
                out.append({**widget, "page": current, "title": ""})
            continue
        if not current:
            # Above the first heading. The opening page is made only once something lands on it.
            if not pages:
                current = uuid.uuid4().hex[:8]
                pages.append({"id": current, "name": FIRST_PAGE})
            else:
                current = pages[0]["id"]
        out.append({**widget, "page": current})

    # A heading whose charts were all dropped would be an empty tab.
    used = {w.get("page") for w in out}
    kept = [p for p in pages if p["id"] in used]
    if len(kept) < 2:
        return [], widgets
    return kept, out


def pages_from_sections(widgets: list[dict], sections: list[str]) -> list[dict]:
    """(pages) for a plan whose charts named the tab they belong on, and sets each widget's page.

    This is the other way a report comes to have tabs. split_by_headings reads them off a
    template's section headings; here the request itself asked for them ("a tab for risks, a tab
    for controls") and the planner said which chart goes where, so the names are the person's own
    words rather than anything worked out afterwards.

    The widgets are reordered so that each tab's charts sit together: a report whose list is
    interleaved reads correctly on screen, because each tab filters the list, but it exports and
    prints in the order the list is in. Nothing happens unless at least two tabs were named and
    every chart landed on one - a partial answer would leave charts scattered onto a tab they were
    never meant for, which is worse than the one page they would otherwise share.
    """
    if len(widgets) != len(sections):
        return []
    named = [s.strip() for s in sections]
    if not all(named):
        return []
    # Distinct tab names, in the order they were first asked for. Case and spacing are not a new
    # tab: "Risk profile" and "risk profile" are one tab, named the way it was written first.
    order: list[str] = []
    seen: dict[str, str] = {}
    for name in named:
        key = " ".join(name.lower().split())
        if key not in seen:
            seen[key] = name[:60]
            order.append(key)
    if len(order) < 2:
        return []

    pages = [{"id": uuid.uuid4().hex[:8], "name": seen[key]} for key in order]
    by_key = {key: pages[i]["id"] for i, key in enumerate(order)}
    for widget, name in zip(widgets, named):
        widget["page"] = by_key[" ".join(name.lower().split())]
    rank = {page["id"]: i for i, page in enumerate(pages)}
    widgets.sort(key=lambda w: rank[w["page"]])        # stable: the order within a tab is kept
    return pages


# The id the single implied page goes by when a report has no pages of its own. It matches
# lib/pages.ts in the frontend, so the two agree about what "the first page" means.
ONE_PAGE = "main"


def pages_of(config: dict) -> list[dict]:
    """The report's pages, or the one implied page. Never empty, so callers need no special case."""
    pages = [p for p in (config.get("pages") or []) if isinstance(p, dict) and p.get("id")]
    return pages or [{"id": ONE_PAGE, "name": "Report"}]


def page_of(pages: list[dict], widget: dict) -> str:
    """Which page a widget is on.

    A widget with no page, or one naming a page that has since been deleted, belongs to the first
    page - the same rule the frontend follows, so a tile orphaned by an edit is still drawn and
    still filtered, rather than quietly falling out of both.
    """
    named = widget.get("page")
    return named if named and any(p["id"] == named for p in pages) else pages[0]["id"]
