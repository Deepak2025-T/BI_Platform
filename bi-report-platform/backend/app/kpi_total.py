"""Making a number tile be one number.

"Total gross loss in the window" is a sum, and IBM OpenPages cannot write one: its Query Service
has COUNT and nothing else - no SUM, no CASE, no subqueries. So the query that comes back is the
only one that can be written, a plain SELECT of every loss event and its amount, and what reaches
the tile is seven hundred rows.

Seven hundred rows is not a number tile. fit_chart sees that and quietly turns the tile into a
table, which is why a dashboard that asked for "Total Gross Loss" shows a list of event names with
an empty amount column beside them - the one shape of answer nobody wanted.

So the rows are added up here instead, the same way dates are folded in date_rollup: the query
stays as written, and the result is reduced to the one row the tile was always meant to hold. The
spec is kept on the widget, so a refresh does it again:

    {"column": "OPSS-LossEvent:Gross Loss", "to": "sum"}

Where there is no number to add - a tile counting records that the Query Service could not count
because the count needed a join - the rows themselves are the answer, and the tile shows how many
there were.
"""

from __future__ import annotations

COUNT_LABEL = "Count"


def _number(value):
    """The value as a number, or None when it is not one. Text is tried too, because an OpenPages
    amount arrives as a string often enough to matter."""
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def _numeric_columns(columns: list[str], rows: list[list]) -> list[str]:
    """The columns every filled cell of which is a number. A column of blanks is not one: that is
    the field whose name was wrong, and adding it up would say the total is nought."""
    out = []
    for i, name in enumerate(columns):
        filled = [r[i] for r in rows[:200] if i < len(r) and r[i] not in (None, "")]
        if filled and all(_number(v) is not None for v in filled):
            out.append(name)
    return out


def total_spec(chart: dict | None, columns: list[str], rows: list[list]) -> dict | None:
    """What this result has to be reduced to, or None to leave it exactly as it came back.

    Only a tile that asked to be one number and came back as many rows is touched, so nothing that
    already works can be changed by this.
    """
    if not isinstance(chart, dict) or chart.get("type") != "kpi":
        return None
    if len(rows) <= 1 or not columns:
        return None
    numeric = _numeric_columns(columns, rows)
    # What the tile said it measures wins, where that column holds numbers.
    wanted = [str(c) for c in (chart.get("y") or []) if str(c) in numeric]
    if wanted:
        return {"column": wanted[0], "to": "sum"}
    if numeric:
        return {"column": numeric[0], "to": "sum"}
    return {"column": "", "to": "count"}


def apply(columns: list[str], rows: list[list], spec: dict) -> dict | None:
    """The result as one row, or None when the spec doesn't fit this result and it should be left
    alone - which is what happens when a field has been renamed since the report was built."""
    if not isinstance(spec, dict):
        return None
    to = str(spec.get("to") or "sum").strip().lower()
    if to == "count":
        return {"columns": [COUNT_LABEL], "rows": [[len(rows)]], "row_count": 1}
    column = str(spec.get("column") or "")
    if to != "sum" or column not in columns:
        return None
    i = columns.index(column)
    numbers = [_number(r[i]) for r in rows if i < len(r)]
    total = sum(n for n in numbers if n is not None)
    # A whole number is shown as one: "713", not "713.0".
    return {"columns": [column], "rows": [[int(total) if total == int(total) else total]],
            "row_count": 1}
