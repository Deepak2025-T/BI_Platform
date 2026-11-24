"""Saying a chart could not be drawn, rather than drawing something else instead.

A field name differs between OpenPages installations - OPSS-Ev:Gross Loss on one, something else
on the next - and a query that names the wrong one does not fail. It comes back with the column
there and every cell in it empty. So "Running Total of Gross Loss" arrived as seven dates beside a
blank column, was seen to have no numbers in it, and was quietly drawn as a table: a tile that
looks built, says nothing, and gives the reader no idea that a field name is wrong.

A chart that was asked for as a chart needs a number. Where the number is not there, this says so
and names the column that came back empty, so it lands in the report's "failed" list with the one
fact that lets someone fix it. The report is still built - one named gap is worth far more than
twenty tiles of which one is lying.
"""

from __future__ import annotations

# The chart shapes that draw a number. A table and a matrix show records, so they need none.
MEASURED = ("kpi", "bar", "line", "area", "pie", "donut", "combo", "heatmap", "gauge")


def _is_number(value) -> bool:
    if isinstance(value, bool) or value is None:
        return False
    if isinstance(value, (int, float)):
        return True
    try:
        float(str(value).replace(",", "").strip())
        return True
    except (TypeError, ValueError):
        return False


def _empty_columns(columns: list[str], rows: list[list]) -> list[str]:
    return [name for i, name in enumerate(columns)
            if all(i >= len(r) or r[i] in (None, "") for r in rows)]


def measure_problem(chart: dict | None, columns: list[str], rows: list[list]) -> str | None:
    """Why this result cannot be the chart that was asked for, or None when it can.

    Only a chart that needs a number and came back with rows but no number is refused. An empty
    result is not a problem of this kind - nothing happened in the window, which is an answer.
    """
    if not isinstance(chart, dict) or chart.get("type") not in MEASURED:
        return None
    if not rows or not columns:
        return None
    if any(_is_number(r[i]) for i, _ in enumerate(columns) for r in rows[:200] if i < len(r)):
        return None
    blank = _empty_columns(columns, rows)
    if blank:
        names = ", ".join(blank[:3])
        return (f"{names} came back empty on this connection, so there is no number to chart. "
                "The field is probably named something else here.")
    return ("This query came back without a number in it, so there is nothing to chart. "
            f"It returned: {', '.join(columns[:4])}.")
