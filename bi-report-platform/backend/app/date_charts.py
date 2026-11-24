"""Making a chart that is "by month" actually come back by month.

A chart grouped on a date column returns one row per distinct value, and an OpenPages date is a
timestamp to the millisecond with an offset on the end. So "Loss Events by Month of Occurrence"
arrives as ninety points labelled 2025-04-01T00:00:00.000-04:00, which is unreadable and is not a
month breakdown at all - it is every record, drawn one per pixel.

date_rollup can fold those rows up after the query has run, and the OpenPages templates ask it to
by hand. A planned dashboard cannot: the model writes the SQL, and nothing in the plan says this
column holds dates. So the fold is worked out here instead, from the two things that are known -
the name of the column the chart groups by, and the period the chart's own title names.

Deliberately narrow. A widget that already carries a rollup is left alone, a table or a KPI is
left alone, and a column whose name says nothing about dates is left alone. Where it does fire and
the values turn out not to be dates after all, date_rollup keeps them exactly as they are, so the
worst case is a fold that changes nothing.
"""

from __future__ import annotations

import re

# The format every chart shows a month in. Charts are read at a glance and the year matters only
# for telling one January from the next, so "11/25" says everything "11/2025" does in half the
# width - which is the difference between an axis that fits and one that overlaps itself.
MONTH_FORMAT = "mm/yy"
QUARTER_FORMAT = "Qq yy"
YEAR_FORMAT = "yyyy"

_FORMATS = {"month": MONTH_FORMAT, "quarter": QUARTER_FORMAT, "year": YEAR_FORMAT}

# A column whose name carries one of these holds a date. Worked from the name because it is all
# there is before the query runs; "day" and "days" are left out on purpose, since "Days to
# Discover" is a number of days and not a date.
_DATE_COLUMN = re.compile(
    r"\b(date|dated|month|monthly|quarter|quarterly|year|yearly|annual|time|timestamp"
    r"|created|creation|modified|modification|occurred|occurrence|discovered|raised|logged"
    r"|opened|closed|completed|scheduled|reported|reviewed|due|deadline|period)\b", re.I)

# What the chart calls itself, when it names a period of its own. Week is read as month: a week
# cannot be labelled in mm/yy, and a chart whose labels are ambiguous is worse than a coarser one.
_PERIOD_WORDS = (
    (re.compile(r"\b(quarter|quarterly|q[1-4]\b)", re.I), "quarter"),
    (re.compile(r"\b(year|yearly|annual|annually)\b", re.I), "year"),
    (re.compile(r"\b(month|monthly|week|weekly|day|daily|date|over time|trend)\b", re.I), "month"),
)

# A chart with no categories to fold.
_NOT_FOLDED = ("table", "matrix", "kpi", "gauge", "text")


def column_holds_dates(column: str) -> bool:
    """Whether a column of this name holds dates. The OpenPages group prefix is dropped first, so
    "OPSS-LossEvent:Date of Occurrence" is read as "Date of Occurrence"."""
    name = str(column or "")
    after_prefix = name.split(":", 1)[-1] if ":" in name else name
    return bool(_DATE_COLUMN.search(after_prefix))


def period_for(*text: str) -> str:
    """The period a chart's own words ask for, defaulting to months."""
    joined = " ".join(t for t in text if t)
    for pattern, period in _PERIOD_WORDS:
        if pattern.search(joined):
            return period
    return "month"


def rollup_for(widget: dict) -> dict | None:
    """The fold this widget needs, or None to leave it exactly as it is."""
    if not isinstance(widget, dict) or widget.get("rollup"):
        return None
    chart = widget.get("chart")
    if not isinstance(chart, dict) or chart.get("type") in _NOT_FOLDED:
        return None
    column = chart.get("x") or ""
    if not column or not column_holds_dates(column):
        return None
    period = period_for(widget.get("title", ""), widget.get("question", ""))
    return {"column": column, "to": period, "format": _FORMATS[period]}


def with_rollups(widgets):
    """Every widget, with a month fold added to the ones grouped on a date."""
    out = []
    for widget in widgets or []:
        rollup = rollup_for(widget)
        out.append({**widget, "rollup": rollup} if rollup else widget)
    return out
