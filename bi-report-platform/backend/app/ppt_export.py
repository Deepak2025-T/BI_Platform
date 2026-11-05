"""
PowerPoint export of a dashboard: a title slide, then one slide per chart.

Charts become real PowerPoint charts rather than pictures, so the numbers behind them are in the
file and anyone can restyle a slide or drop it into their own deck. Number tiles become a single
large figure, and tables become a PowerPoint table.

The colours are the ones the dashboard uses on screen (the chart palette saved on each tile, or the
app's default palette), so a slide looks like the tile it came from.
"""

import datetime as dt
import io

from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE, XL_LEGEND_POSITION
from pptx.enum.text import PP_ALIGN
from pptx.util import Emu, Inches, Pt

from .dashboard_filters import is_active

# The same palette the charts use in the browser (see DataChart.tsx CHART_COLORS).
PALETTE = ["00B4D8", "0D3B66", "F5A623", "7A8BA3", "2A9D8F", "A63D40", "6D597A", "1E7F4F"]
INK, MUTED, RULE = "0D3B66", "5A6B7B", "D7E2EA"

# A 16:9 slide, and the box the body of a slide sits in.
SLIDE_W, SLIDE_H = Inches(13.333), Inches(7.5)
MARGIN = Inches(0.6)
BODY_TOP = Inches(1.5)
BODY_W = SLIDE_W - 2 * MARGIN
BODY_H = SLIDE_H - BODY_TOP - Inches(0.5)

# A table slide holds this many rows before the rest is left to the Excel export, which has them all.
MAX_TABLE_ROWS = 14
MAX_TABLE_COLUMNS = 8
# A chart of hundreds of categories is a smear; the largest are the ones worth showing.
MAX_CATEGORIES = 25

CHART_TYPES = {
    "bar": XL_CHART_TYPE.COLUMN_CLUSTERED,
    "column": XL_CHART_TYPE.COLUMN_CLUSTERED,
    "line": XL_CHART_TYPE.LINE_MARKERS,
    "area": XL_CHART_TYPE.AREA,
    "pie": XL_CHART_TYPE.PIE,
    "donut": XL_CHART_TYPE.DOUGHNUT,
}


def _text(frame, value: str, size: int, *, bold: bool = False, color: str = INK,
          align=PP_ALIGN.LEFT) -> None:
    frame.text = value
    p = frame.paragraphs[0]
    p.alignment = align
    run = p.runs[0] if p.runs else p.add_run()
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = RGBColor.from_string(color)


def _box(slide, left, top, width, height, value: str, size: int, **kw):
    shape = slide.shapes.add_textbox(left, top, width, height)
    shape.text_frame.word_wrap = True
    _text(shape.text_frame, value, size, **kw)
    return shape


def _blank(deck: Presentation):
    return deck.slides.add_slide(deck.slide_layouts[6])  # the layout with nothing on it


def _heading(slide, title: str, subtitle: str = "") -> None:
    _box(slide, MARGIN, Inches(0.45), BODY_W, Inches(0.6), title or "Chart", 26, bold=True)
    if subtitle:
        _box(slide, MARGIN, Inches(1.05), BODY_W, Inches(0.35), subtitle, 12, color=MUTED)
    line = slide.shapes.add_shape(1, MARGIN, Inches(1.42), BODY_W, Emu(9525))  # 1 = rectangle
    line.fill.solid()
    line.fill.fore_color.rgb = RGBColor.from_string(RULE)
    line.line.fill.background()
    line.shadow.inherit = False


def _palette(widget: dict) -> list[str]:
    saved = [str(c).lstrip("#").upper() for c in ((widget.get("style") or {}).get("palette") or [])]
    good = [c for c in saved if len(c) == 6 and all(ch in "0123456789ABCDEF" for ch in c)]
    return good or PALETTE


def _numeric(value) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).replace(",", "").strip())
    except ValueError:
        return None


def _series(columns: list[str], rows: list[list], chart: dict) -> tuple[str, list[str], list[tuple[str, list]]]:
    """(category column, categories, [(series name, values)]) for one chart's result.

    The saved chart says which column is the axis and which hold the numbers. When it doesn't say,
    or says something this result doesn't have, the first text column is the axis and every column
    of numbers is a series - the same fallback the charts use in the browser."""
    x = str(chart.get("x") or "")
    wanted = [str(c) for c in (chart.get("y") or []) if str(c) in columns]
    if x not in columns:
        x = next((c for i, c in enumerate(columns) if any(_numeric(r[i]) is None for r in rows[:20])), columns[0])
    if not wanted:
        wanted = [c for i, c in enumerate(columns)
                  if c != x and rows and all(_numeric(r[i]) is not None for r in rows[:20])]
    if not wanted:
        return x, [], []
    xi = columns.index(x)
    picked = rows[:MAX_CATEGORIES]
    categories = [("" if r[xi] is None else str(r[xi]))[:60] for r in picked]
    series = [(name, [_numeric(r[columns.index(name)]) for r in picked]) for name in wanted]
    return x, categories, series


def _chart_slide(slide, widget: dict, columns: list[str], rows: list[list]) -> bool:
    kind = str((widget.get("chart") or {}).get("type") or "bar").lower()
    chart_type = CHART_TYPES.get(kind)
    if chart_type is None:
        return False
    _, categories, series = _series(columns, rows, widget.get("chart") or {})
    if not categories or not series:
        return False
    data = CategoryChartData()
    data.categories = categories
    for name, values in series:
        data.add_series(name, values)
    graphic = slide.shapes.add_chart(chart_type, MARGIN, BODY_TOP, BODY_W, BODY_H, data)
    chart = graphic.chart
    chart.font.size = Pt(12)
    colours = _palette(widget)
    if kind in ("pie", "donut"):
        chart.has_legend = True
        chart.legend.position = XL_LEGEND_POSITION.RIGHT
        chart.legend.include_in_layout = False
        # A pie has one series, and each slice is a point of it that carries its own colour.
        for i, point in enumerate(chart.series[0].points):
            point.format.fill.solid()
            point.format.fill.fore_color.rgb = RGBColor.from_string(colours[i % len(colours)])
    else:
        chart.has_legend = len(series) > 1
        if chart.has_legend:
            chart.legend.position = XL_LEGEND_POSITION.BOTTOM
            chart.legend.include_in_layout = False
        for i, plot_series in enumerate(chart.series):
            plot_series.format.fill.solid()
            plot_series.format.fill.fore_color.rgb = RGBColor.from_string(colours[i % len(colours)])
    return True


def _kpi_slide(slide, columns: list[str], rows: list[list]) -> bool:
    """One big number: the first number in the result."""
    value = next((v for row in rows for v in row if _numeric(v) is not None), None)
    if value is None:
        return False
    number = _numeric(value)
    shown = f"{number:,.0f}" if number == int(number) else f"{number:,.2f}"
    _box(slide, MARGIN, Inches(2.4), BODY_W, Inches(1.8), shown, 96, bold=True, align=PP_ALIGN.CENTER)
    if columns:
        _box(slide, MARGIN, Inches(4.2), BODY_W, Inches(0.5), str(columns[0]), 16, color=MUTED,
             align=PP_ALIGN.CENTER)
    return True


def _table_slide(slide, columns: list[str], rows: list[list]) -> bool:
    if not columns:
        return False
    shown_columns = columns[:MAX_TABLE_COLUMNS]
    shown_rows = rows[:MAX_TABLE_ROWS]
    height = min(BODY_H, Inches(0.32) * (len(shown_rows) + 1) + Inches(0.1))
    table = slide.shapes.add_table(len(shown_rows) + 1, len(shown_columns), MARGIN, BODY_TOP,
                                   BODY_W, height).table
    for c, name in enumerate(shown_columns):
        _text(table.cell(0, c).text_frame, str(name)[:40], 11, bold=True)
    for r, row in enumerate(shown_rows, start=1):
        for c in range(len(shown_columns)):
            value = row[c] if c < len(row) else None
            _text(table.cell(r, c).text_frame, "" if value is None else str(value)[:60], 10)
    return True


def _filter_text(f: dict, value: dict) -> str:
    if f.get("kind") == "date":
        return f"{value.get('date_from') or 'start'} to {value.get('date_to') or 'today'}"
    return ", ".join(value.get("values") or [])


def dashboard_deck(title: str, config: dict, source_name: str, results: list[dict], values: dict) -> bytes:
    """The dashboard as a .pptx file. `results` and `values` are what the viewer itself showed, so
    the deck carries the same filtered numbers."""
    deck = Presentation()
    deck.slide_width, deck.slide_height = SLIDE_W, SLIDE_H

    widgets = [w for w in config.get("widgets", []) if w.get("kind", "chart") != "text"]
    filters = {f["id"]: f for f in config.get("filters") or [] if isinstance(f, dict) and f.get("id")}
    by_id = {r["id"]: r for r in results}

    cover = _blank(deck)
    _box(cover, MARGIN, Inches(2.4), BODY_W, Inches(1.2), title or "Dashboard", 40, bold=True)
    lines = [f"Data: {source_name}", f"Exported {dt.datetime.now().strftime('%d %b %Y, %H:%M')}"]
    lines += [f"{filters[k].get('label', '')}: {_filter_text(filters[k], v)}"
              for k, v in values.items() if k in filters and is_active(filters[k], v)]
    _box(cover, MARGIN, Inches(3.7), BODY_W, Inches(2.0), "\n".join(lines), 14, color=MUTED)

    for w in widgets:
        res = by_id.get(w["id"], {})
        slide = _blank(deck)
        notes = []
        if res.get("not_filtered"):
            notes.append("not filtered by " + ", ".join(filters[i].get("label", "")
                                                        for i in res["not_filtered"] if i in filters))
        if res.get("truncated"):
            notes.append("the first rows only")
        _heading(slide, w.get("title", ""), "; ".join(notes))
        if not res.get("ok"):
            _box(slide, MARGIN, BODY_TOP, BODY_W, Inches(1.0),
                 f"This chart's query couldn't run: {res.get('error', 'not run')}", 14, color=MUTED)
            continue
        columns, rows = list(res.get("columns") or []), list(res.get("rows") or [])
        kind = str((w.get("chart") or {}).get("type") or "").lower()
        if not rows:
            _box(slide, MARGIN, BODY_TOP, BODY_W, Inches(1.0), "This chart has no rows to show.", 14, color=MUTED)
            continue
        drawn = (_kpi_slide(slide, columns, rows) if kind == "kpi"
                 else _chart_slide(slide, w, columns, rows) if kind in CHART_TYPES
                 else False)
        if not drawn:
            # Anything a slide can't draw - a table, a heat map, a chart of nothing but text -
            # is still worth having as its rows.
            _table_slide(slide, columns, rows)
            if len(rows) > MAX_TABLE_ROWS or len(columns) > MAX_TABLE_COLUMNS:
                _box(slide, MARGIN, SLIDE_H - Inches(0.6), BODY_W, Inches(0.35),
                     f"Showing {min(len(rows), MAX_TABLE_ROWS)} of {len(rows)} rows. "
                     f"The Excel export has all of them.", 11, color=MUTED)

    buf = io.BytesIO()
    deck.save(buf)
    return buf.getvalue()
