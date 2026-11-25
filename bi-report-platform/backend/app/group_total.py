"""Totalling a result by a category, after the query has run.

"Total gross loss by business entity" is a sum per group, and the IBM OpenPages Query Service can
write neither half of it: no SUM, and GROUP BY only alongside its own COUNT. So the only query
that can be written is the one with no grouping at all -

    SELECT [Loss Event].[Location], [Loss Event].[Gross Loss] FROM [Loss Event]

- which comes back as one row per loss event. Drawn as it stands, that is a bar chart with four
hundred bars, several of them sharing a name, each as tall as a single record. Asked for with a
SUM, it is five planned charts reported as "the query didn't work".

So the rows are added up here, by the column the chart groups on, exactly as date_rollup adds them
up by month. The query stays the one that runs; the result becomes the one that was wanted. The
spec is kept on the widget so a refresh does it again:

    {"column": "Location", "to": "sum", "order": "desc"}

Rows that share a value of that column become one row: the numbers in them are added, and
anything that is not a number is taken from the first of them, since a group of records has no
single status or owner to show.
"""

from __future__ import annotations

# The chart shapes that draw one mark per category, and so need one row per category.
GROUPED = ("bar", "line", "area", "pie", "donut", "combo")


def _number(value):
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def _numeric_columns(columns: list[str], rows: list[list]) -> list[int]:
    out = []
    for i in range(len(columns)):
        filled = [r[i] for r in rows[:200] if i < len(r) and r[i] not in (None, "")]
        if filled and all(_number(v) is not None for v in filled):
            out.append(i)
    return out


def group_spec(chart: dict | None, columns: list[str], rows: list[list]) -> dict | None:
    """What this result has to be totalled by, or None to leave it exactly as it came back.

    Only a chart that draws one mark per category, whose category column repeats, and which has a
    number to add. A result that already holds one row per category is what a GROUP BY would have
    produced and is left alone.
    """
    if not isinstance(chart, dict) or chart.get("type") not in GROUPED:
        return None
    column = str(chart.get("x") or "")
    if column not in columns or len(rows) < 2:
        return None
    i = columns.index(column)
    seen = {str(r[i]) for r in rows if i < len(r)}
    if len(seen) == len(rows):
        return None  # one row per category already
    if not [n for n in _numeric_columns(columns, rows) if n != i]:
        return None  # nothing to add up
    return {"column": column, "to": "sum", "order": "desc"}


def apply(columns: list[str], rows: list[list], spec: dict) -> dict | None:
    """The result with one row per category, or None when the spec doesn't fit it - a column that
    is no longer there, which is what a renamed field looks like."""
    if not isinstance(spec, dict):
        return None
    column = str(spec.get("column") or "")
    if str(spec.get("to") or "sum").strip().lower() != "sum" or column not in columns:
        return None
    index = columns.index(column)
    numeric = [n for n in _numeric_columns(columns, rows) if n != index]
    if not numeric:
        return None

    folded: dict[str, list] = {}
    for row in rows:
        key = "" if index >= len(row) or row[index] is None else str(row[index])
        if key not in folded:
            folded[key] = list(row) + [None] * (len(columns) - len(row))
            continue
        into = folded[key]
        for i in numeric:
            left, right = _number(into[i]), _number(row[i] if i < len(row) else None)
            if right is not None:
                into[i] = (left or 0) + right

    out = list(folded.values())
    if str(spec.get("order") or "desc").strip().lower() == "desc" and numeric:
        first = numeric[0]
        out.sort(key=lambda r: _number(r[first]) or 0, reverse=True)
    # A whole number is shown as one: 30,000 rather than 30,000.0.
    for row in out:
        for i in numeric:
            value = _number(row[i])
            if value is not None:
                row[i] = int(value) if value == int(value) else value
    return {"columns": list(columns), "rows": out, "row_count": len(out)}
