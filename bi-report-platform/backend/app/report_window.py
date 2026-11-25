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

And a bound only stays if it answers. A date field can be spelled differently on this
installation, hold nothing, or not compare the way the Query Service wants, and none of those
fails: the query runs and matches no row. Nor does an empty window - three quiet months read
exactly the same. So any bound that leaves a chart with nothing is dropped and the chart named:
an empty tile says nothing about either case, and the records outside the window are the only
thing worth putting in front of a reader.
"""

from __future__ import annotations

import datetime as dt

from . import dashboard_filters
from .ai.providers import ModelSpec
from .datasources import DataSource, run_sql

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
        if applied and not params and _bound_still_answers(source, sql):
            out.append({**widget, "sql": sql})
        else:
            out.append(widget)
            unbounded.append(str(widget.get("title") or "")[:120])
    return out, unbounded


def _rows(source: DataSource, sql: str) -> int | None:
    """How many rows this query returns, or None when it will not run. The unbounded query was
    already run to build the chart, so asking for it again is answered from the result cache."""
    try:
        return len(run_sql(source, sql)["rows"])
    except Exception:  # a query the service refused, a connection that would not answer
        return None


def _bound_still_answers(source: DataSource, after: str) -> bool:
    """Whether the bound is one worth keeping.

    A date field can be spelled differently here, hold nothing, or not compare the way the Query
    Service wants, and none of those fails - the query runs and matches no row. A whole report of
    zeros is the result, which is the worst thing this could do: a chart that read 207 now reads 0
    and nothing says why.

    So the bound has to earn its place: it is kept only where the bounded query still answers.
    A bound that empties a chart is dropped and the chart named, whether the window is the reason
    or a misread field is. An empty tile tells a reader nothing either way, and a page of them
    tells them nothing twenty times over - where there is nothing in the window, the records
    outside it are the only thing worth putting in front of someone.
    """
    bounded = _rows(source, after)
    return bool(bounded)
