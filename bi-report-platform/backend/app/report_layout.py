"""
One shape for every report: the numbers at the top, the charts three to a row, the records last.

A dashboard people read every morning should not need to be learnt twice. Whether it came from a
built-in template or from a sentence someone typed, it opens the same way: the headline counts
across the top, then the breakdowns, then the summary table of the records behind them. Anyone who
knows where to look on one report knows where to look on all of them.

Three to a row is the width that makes that true. Two left a bar chart of six categories with more
empty space than chart; four made the labels unreadable. Three fits the twelve-column grid exactly
and matches what a KPI row already does.

Two things are deliberately left alone:

  - Headings and notes are never moved. They introduce the charts underneath them, so reordering
    across one would file charts under the wrong heading. They split a page into runs instead, and
    each run is ordered within itself.
  - A page is ordered against itself only. A report with tabs is several reports on one object,
    and a table at the end of tab one does not belong after tab three.
"""

# The twelve-column grid these map onto lives in frontend/src/styles/app.css (.dash-grid).
KPI_SIZE = "quarter"    # span 3 - four counts across the top
CHART_SIZE = "third"    # span 4 - three charts to a row
TABLE_SIZE = "full"     # span 12 - a summary table has columns to show


def _kind(widget: dict) -> str:
    return widget.get("kind", "chart")


def _chart_type(widget: dict) -> str:
    return str((widget.get("chart") or {}).get("type") or "")


def is_kpi(widget: dict) -> bool:
    return _kind(widget) == "chart" and _chart_type(widget) == "kpi"


def is_table(widget: dict) -> bool:
    return _kind(widget) == "chart" and _chart_type(widget) == "table"


def _rank(widget: dict) -> int:
    """Where a chart belongs within its run: counts, then breakdowns, then records."""
    if is_kpi(widget):
        return 0
    if is_table(widget):
        return 2
    return 1


def _sized(widget: dict) -> dict:
    """The width for what this widget is. Headings and images keep whatever they were given."""
    if _kind(widget) != "chart":
        return widget
    size = KPI_SIZE if is_kpi(widget) else TABLE_SIZE if is_table(widget) else CHART_SIZE
    if widget.get("size") == size:
        return widget
    return {**widget, "size": size}


def _runs(widgets: list[dict]) -> list[list[dict]]:
    """A page split at its headings: each heading alone, each run of charts together."""
    runs: list[list[dict]] = []
    charts: list[dict] = []
    for widget in widgets:
        if _kind(widget) == "chart":
            charts.append(widget)
            continue
        if charts:
            runs.append(charts)
            charts = []
        runs.append([widget])       # the heading itself, left exactly where it was
    if charts:
        runs.append(charts)
    return runs


def _pages(widgets: list[dict]) -> list[list[dict]]:
    """The widgets of each page, in the order the pages first appear."""
    pages: dict[str, list[dict]] = {}
    for widget in widgets:
        pages.setdefault(str(widget.get("page") or ""), []).append(widget)
    return list(pages.values())


def shape(widgets: list[dict]) -> list[dict]:
    """The report in reading order, each widget the width its kind calls for.

    Pure: the list and the widgets given are not modified, so a caller can compare before and
    after. Safe on an empty list, on one widget, and on a report that is already in this shape.
    """
    out: list[dict] = []
    for page in _pages(list(widgets or [])):
        for run in _runs(page):
            # sorted() is stable, so charts of the same kind keep the order they were written in -
            # the plan's own sequence still decides which breakdown comes first.
            out.extend(sorted(run, key=_rank) if len(run) > 1 else run)
    return [_sized(w) for w in out]
