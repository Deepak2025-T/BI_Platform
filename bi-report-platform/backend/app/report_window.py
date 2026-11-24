"""Making "for past 3 months" mean the past 3 months.

A detail report names a window and every query on it is supposed to respect it. Asking for that in
the prompt does not get it: the model writes twenty queries and puts the date bound on some of
them, so the report says "Last 3 Months" at the top and draws a bar in July of last year. Worse,
the mix is invisible - two tiles that disagree look like two facts.

So the window is not asked for, it is applied. The date column of each chart is chosen once, from
the real field list of the object types that chart reads (dashboard_filters.map_filter, which
checks every answer against those fields and drops the ones that are not there), and the bound is
written into each query exactly as a date-range filter would write it. The saved SQL is bounded,
so a refresh, an export and a drill all read the same window as the page did when it was built.

A chart whose object type has no date to bound - controls tested by control type, say, where a
control has no loss date of its own - is left as it is and named in the return, because a report
that quietly bounds nineteen charts and not the twentieth is the thing this exists to prevent.
"""

from __future__ import annotations

import datetime as dt

from . import dashboard_filters
from .ai.providers import ModelSpec
from .datasources import DataSource

LABEL = "Date range"


def _is_chart(widget: dict) -> bool:
    return bool(widget.get("sql")) and widget.get("kind") != "text"


def bake(spec: ModelSpec, source: DataSource, widgets: list[dict], start: dt.date, end: dt.date):
    """(widgets with the window written into their SQL, the titles of the ones with no date to
    bound on). The widgets are copied; the ones handed in are left as they were."""
    charts = [w for w in widgets if _is_chart(w)]
    if not charts:
        return list(widgets), []
    date_filter = dashboard_filters.map_filter(spec, source, LABEL, "date", charts)
    values = {date_filter["id"]: {"date_from": start.isoformat(), "date_to": end.isoformat()}}

    out, unbounded = [], []
    for widget in widgets:
        if not _is_chart(widget):
            out.append(widget)
            continue
        sql, params, applied, _ = dashboard_filters.apply(widget["sql"], source, [date_filter],
                                                          values, widget["id"])
        # Bound values only exist for a database connection, and there the bound SQL cannot be
        # saved without them. OpenPages writes its conditions as literals, which can.
        if applied and not params:
            out.append({**widget, "sql": sql})
        else:
            out.append(widget)
            unbounded.append(str(widget.get("title") or "")[:120])
    return out, unbounded
