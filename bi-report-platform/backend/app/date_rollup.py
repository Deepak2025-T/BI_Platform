"""Folding a result's date column up to a month, quarter or year, after the query has run.

Database connections group dates in the query itself (visual_query's `bucket`, which compiles to
TO_CHAR, DATE_FORMAT or STRFTIME). IBM OpenPages cannot: its Query Service SQL has COUNT and
nothing else — no date functions, no CASE, no subqueries — so a count per month simply cannot be
written. The query returns one row per date, and the rows are folded here instead.

A widget asks for it with a "rollup" key:

    {"column": "OPSS-Risk:Creation Date", "to": "month", "format": "mm/yyyy"}

The column keeps its name and place, so the chart's own `x` needs no change; its values become
period labels and rows that land in the same period are added together. Rows whose value is not a
date are kept as they are and sorted after the dated ones, so nothing is dropped silently.
"""

from __future__ import annotations

import datetime as dt
import re

PERIODS = ("month", "quarter", "year")
DEFAULT_FORMATS = {"month": "mm/yyyy", "quarter": "Qq yyyy", "year": "yyyy"}

# "2026-11-03", "2026-11-03T06:00:00Z", "2026/11/03 06:00" and the day-first and US spellings.
_ISO = re.compile(r"^(\d{4})[-/](\d{1,2})[-/](\d{1,2})")
_SLASHED = re.compile(r"^(\d{1,2})[-/](\d{1,2})[-/](\d{4})")


def _parse(value) -> dt.date | None:
    """The date in a cell, or None when it does not hold one."""
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    text = str(value or "").strip()
    if not text:
        return None
    match = _ISO.match(text)
    if match:
        year, month, day = (int(g) for g in match.groups())
    else:
        match = _SLASHED.match(text)
        if not match:
            return None
        first, second, year = (int(g) for g in match.groups())
        # 13/01/2026 can only be day first; 01/13/2026 can only be month first. When both readings
        # work the day-first one is used, which is what OpenPages and the rest of this app show.
        day, month = (first, second) if first > 12 or second <= 12 else (second, first)
    try:
        return dt.date(year, month, day)
    except ValueError:
        return None


def label_of(day: dt.date, to: str, fmt: str) -> str:
    """The label one date gets. `fmt` is the shape people asked for, e.g. mm/yyyy or yyyy-mm."""
    quarter = (day.month + 2) // 3
    pieces = {"mm": f"{day.month:02d}", "m": str(day.month), "yyyy": f"{day.year:04d}",
              "yy": f"{day.year % 100:02d}", "q": str(quarter)}
    if to == "year":
        pieces = {k: v for k, v in pieces.items() if k.startswith("y")}
    out, i = [], 0
    keys = sorted(pieces, key=len, reverse=True)
    while i < len(fmt):
        for key in keys:
            if fmt[i:i + len(key)] == key:
                out.append(pieces[key])
                i += len(key)
                break
        else:
            out.append(fmt[i])
            i += 1
    return "".join(out)


def _sort_key(day: dt.date, to: str) -> tuple:
    if to == "year":
        return (day.year, 0)
    if to == "quarter":
        return (day.year, (day.month + 2) // 3)
    return (day.year, day.month)


def _add(left, right):
    """Two cells from the same period, added when they are numbers and kept when they are not."""
    if left is None:
        return right
    if isinstance(left, bool) or isinstance(right, bool):
        return left
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return left + right
    return left


def apply(columns: list[str], rows: list[list], spec: dict) -> dict | None:
    """The result folded to periods, or None when the spec doesn't fit this result and it should be
    left alone (a column that isn't there, a period nobody recognises)."""
    if not isinstance(spec, dict):
        return None
    column = str(spec.get("column") or "")
    to = str(spec.get("to") or "month").strip().lower()
    if to not in PERIODS or column not in columns:
        return None
    fmt = str(spec.get("format") or DEFAULT_FORMATS[to])
    index = columns.index(column)
    newest_first = str(spec.get("order") or "").strip().lower() == "desc"

    folded: dict[str, list] = {}
    keys: dict[str, tuple] = {}
    for row in rows:
        day = _parse(row[index])
        if day is None:
            # Not a date: its own label, after every period, in the order it arrived.
            label = str(row[index] or "")
            key = (9999, 99, label)
        else:
            label = label_of(day, to, fmt)
            key = _sort_key(day, to)
        if label in folded:
            merged = folded[label]
            for i, cell in enumerate(row):
                if i != index:
                    merged[i] = _add(merged[i], cell)
        else:
            folded[label] = [label if i == index else cell for i, cell in enumerate(row)]
            keys[label] = key

    ordered = sorted(folded, key=lambda label: keys[label], reverse=newest_first)
    return {"columns": list(columns), "rows": [folded[label] for label in ordered],
            "row_count": len(ordered)}
