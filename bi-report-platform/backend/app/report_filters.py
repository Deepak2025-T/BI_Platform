"""The filters a detail report opens with.

A detail report is twenty tiles of counts, and the first question anyone asks of it is "yes, but
for my part of the business". Without filters the answer is "build another report", which in front
of a client is the same as no.

So each of the four is given the handful of filters its subject is actually read by: the business
entity first, because every object in OpenPages hangs under one, then the two or three fields that
divide its own records - a loss by category and status, a risk by its residual rating.

Two ways of choosing the column, and the cheaper one is used wherever it works. [Location] is a
system field on every object type, holding the path the record sits under, so a business-entity
filter needs no model at all: the field is the same on every chart. The rest are named in the
words people use rather than as field names - "Residual rating" is OPSS-Rsk:Residual Risk Rating
on one installation and something else on the next - so the column is chosen per chart by
dashboard_filters.map_filter, which checks every answer against the fields that chart's object
types really have and drops the ones that are not there.

A filter that reaches no chart is dropped rather than shown: a control someone sets and that
changes nothing on the page is worse than one that was never offered.
"""

from __future__ import annotations

from dataclasses import dataclass

from . import dashboard_filters
from .ai.providers import ModelSpec
from .datasources import DataSource

# The business-entity path every OpenPages object carries. Known, so it costs no model call.
LOCATION = "Location"


@dataclass(frozen=True)
class Wanted:
    """One filter to put on the report: what it is called and what it filters on."""

    label: str
    kind: str = "category"
    # Set where the field is the same on every object type, as [Location] is. Empty means the
    # column is chosen per chart from the fields that chart's types actually have.
    field: str = ""


# Every detail report starts with these. The entity first because it is the division people
# actually work in; the window second so a three-month report can be read a fortnight at a time.
ENTITY = Wanted("Business entity", "category", LOCATION)
WINDOW = Wanted("Date range", "date")


def _is_chart(widget: dict) -> bool:
    return bool(widget.get("sql")) and widget.get("kind") != "text"


def _by_field(source: DataSource, charts: list[dict], want: Wanted) -> dict | None:
    """A filter on a field every object type has: each chart filtered on the first type it reads."""
    picks = {}
    for widget in charts:
        read = dashboard_filters.query_tables(widget["sql"], source)
        if read:
            picks[widget["id"]] = {"table": read[0], "column": want.field}
    if not picks:
        return None
    return dashboard_filters.make_filter(source, want.label, want.kind, charts, picks)


def build(spec: ModelSpec, source: DataSource, widgets: list[dict],
          wanted: tuple[Wanted, ...]) -> list[dict]:
    """The filters for this report's config, in the order asked for, minus the ones that reach no
    chart on it. Never raises: a filter that cannot be worked out is simply not offered."""
    charts = [w for w in widgets if _is_chart(w)]
    if not charts:
        return []
    out = []
    for want in wanted:
        try:
            built = (_by_field(source, charts, want) if want.field
                     else dashboard_filters.map_filter(spec, source, want.label, want.kind, charts))
        except Exception:  # a model that would not answer, a field list that would not load
            continue
        if built and built.get("columns"):
            out.append(built)
    return out
