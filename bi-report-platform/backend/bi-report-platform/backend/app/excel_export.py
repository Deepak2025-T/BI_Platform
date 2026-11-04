"""
Excel export of a dashboard: an "About" sheet (source, filters, which charts each filter applied
to), then one sheet per chart with its result rows.

Text is always written as text, so a value such as "=HYPERLINK(...)" from a database never becomes
a formula in the file.
"""

import datetime as dt
import io
import re

import xlsxwriter

from .dashboard_filters import is_active

_BAD_SHEET_CHARS = re.compile(r"[\[\]:*?/\\]")


def _sheet_name(title: str, used: set[str]) -> str:
    base = _BAD_SHEET_CHARS.sub(" ", title).strip().strip("'")[:31] or "Chart"
    name, n = base, 2
    while name.lower() in used:
        suffix = f" ({n})"
        name, n = base[:31 - len(suffix)] + suffix, n + 1
    used.add(name.lower())
    return name


def _write(ws, row: int, col: int, value):
    if value is None:
        return
    if isinstance(value, bool):
        ws.write_boolean(row, col, value)
    elif isinstance(value, (int, float)):
        ws.write_number(row, col, value)
    else:
        ws.write_string(row, col, str(value))


def _filter_text(f: dict, value: dict) -> str:
    if f.get("kind") == "date":
        return f"{value.get('date_from') or 'start'} to {value.get('date_to') or 'today'}"
    return ", ".join(value.get("values") or [])


def dashboard_workbook(title: str, config: dict, source_name: str, results: list[dict], values: dict) -> bytes:
    buf = io.BytesIO()
    wb = xlsxwriter.Workbook(buf, {"in_memory": True, "strings_to_formulas": False, "strings_to_urls": False,
                                   "strings_to_numbers": False})
    bold = wb.add_format({"bold": True})
    head = wb.add_format({"bold": True, "bg_color": "#E6F6FA", "bottom": 1})
    big = wb.add_format({"bold": True, "font_size": 14})

    widgets = [w for w in config.get("widgets", []) if w.get("kind", "chart") != "text"]  # text tiles have no data
    filters = {f["id"]: f for f in config.get("filters") or [] if isinstance(f, dict) and f.get("id")}
    by_id = {r["id"]: r for r in results}

    about = wb.add_worksheet("About")
    used = {"about"}
    about.set_column(0, 0, 22)
    about.set_column(1, 1, 70)
    about.write_string(0, 0, title, big)
    rows = [("Data", source_name),
            ("Exported", dt.datetime.now().strftime("%Y-%m-%d %H:%M"))]
    for f, v in [(filters[k], v) for k, v in values.items() if k in filters and is_active(filters[k], v)]:
        rows.append((f"Filter: {f.get('label', '')}", _filter_text(f, v)))
    r = 2
    for k, v in rows:
        about.write_string(r, 0, k, bold)
        about.write_string(r, 1, v)
        r += 1
    r += 1
    about.write_string(r, 0, "Sheet", head)
    about.write_string(r, 1, "Chart", head)

    sheet_names = [_sheet_name(w.get("title", ""), used) for w in widgets]
    for w, name in zip(widgets, sheet_names):
        r += 1
        res = by_id.get(w["id"], {})
        notes = []
        if res.get("not_filtered"):
            notes.append("not filtered by " + ", ".join(filters[i].get("label", "") for i in res["not_filtered"] if i in filters))
        if res.get("ok") is False:
            notes.append("the query couldn't run")
        about.write_string(r, 0, name)
        about.write_string(r, 1, w.get("title", "") + (f" ({'; '.join(notes)})" if notes else ""))

        ws = wb.add_worksheet(name)
        if not res.get("ok"):
            ws.write_string(0, 0, f"This chart's query couldn't run: {res.get('error', 'not run')}")
            continue
        columns, data = res["columns"], res["rows"]
        for c, col in enumerate(columns):
            ws.write_string(0, c, col, head)
        for i, row in enumerate(data, start=1):
            for c, value in enumerate(row):
                _write(ws, i, c, value)
        for c, col in enumerate(columns):
            width = max([len(col)] + [len(str(row[c])) for row in data[:200] if row[c] is not None])
            ws.set_column(c, c, min(max(width + 2, 8), 50))
        ws.freeze_panes(1, 0)
        if columns:
            ws.autofilter(0, 0, max(len(data), 1), len(columns) - 1)
        if res.get("truncated"):
            ws.write_string(len(data) + 2, 0, f"Only the first {len(data)} rows are included.")
    wb.close()
    return buf.getvalue()
