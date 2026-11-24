"""The window a detail report names is the window its queries run over.

"Loss events report for past 3 months" built a report titled "Last 3 Months" whose charts drew
bars in July of the year before, and whose two number tiles disagreed with each other: 91 events
in the window beside 189 open ones, counted over all time. Every query had been asked to respect
the window and some of them had.

So it is applied rather than asked for. These pin that: the bound reaches every chart that has a
date to bound on, it is written as a date-range filter writes it, the charts that have no such
date are named rather than hidden, and the widgets handed in are not written into.
"""

import datetime as dt

import pytest

from app import dashboard_filters, report_window
from app.datasources import DataSource

START, END = dt.date(2026, 8, 26), dt.date(2026, 11, 24)

TYPE = "openpages.Loss Event"
DATED = ("SELECT [Loss Event].[OPSS-Ev:Status], COUNT([Loss Event].[Resource ID]) "
         "FROM [Loss Event] GROUP BY [Loss Event].[OPSS-Ev:Status]")
UNDATED = ("SELECT [SOXControl].[OPSS-Ctl:Control Type], COUNT([SOXControl].[Resource ID]) "
           "FROM [SOXControl] GROUP BY [SOXControl].[OPSS-Ctl:Control Type]")


@pytest.fixture
def source() -> DataSource:
    return DataSource(id=7, name="GRC", db_type="openpages", version="v1",
                      tables=[TYPE, "openpages.SOXControl"])


@pytest.fixture
def mapped(monkeypatch):
    """The column each chart is bounded on, as map_filter would have chosen it - except that here
    the choice is fixed, so the test is about the bound and not about the model."""
    def fake(spec, src, label, kind, widgets, filter_id=None):
        assert kind == "date", "a window is a date range"
        return {"id": "win", "label": label, "kind": kind, "options": [],
                "columns": {w["id"]: {"table": TYPE, "column": "OPSS-Ev:Date of Occurrence"}
                            for w in widgets if "Loss Event" in w["sql"]}}
    monkeypatch.setattr(report_window.dashboard_filters, "map_filter", fake)


def widget(wid, sql, title):
    return {"id": wid, "title": title, "sql": sql, "chart": {"type": "bar", "x": "", "y": []}}


def test_the_bound_goes_into_the_query_itself(source, mapped):
    [w], unbounded = report_window.bake(None, source, [widget("w1", DATED, "By status")], START, END)
    assert "[Loss Event].[OPSS-Ev:Date of Occurrence] >= '2026-08-26'" in w["sql"]
    # The last day of the window is in it: the bound is "before the next day", not "before today".
    assert "[Loss Event].[OPSS-Ev:Date of Occurrence] < '2026-11-25'" in w["sql"]
    assert not unbounded


def test_the_rest_of_the_query_survives_the_bound(source, mapped):
    [w], _ = report_window.bake(None, source, [widget("w1", DATED, "By status")], START, END)
    assert w["sql"].startswith("SELECT [Loss Event].[OPSS-Ev:Status], COUNT(")
    assert w["sql"].rstrip().endswith("GROUP BY [Loss Event].[OPSS-Ev:Status]")
    assert w["title"] == "By status" and w["chart"] == {"type": "bar", "x": "", "y": []}


def test_a_chart_whose_records_carry_no_date_is_named_rather_than_hidden(source, mapped):
    """A control has no loss date of its own. Bounding it on someone else's would be a lie, and
    leaving it silently unbounded is what made two tiles on one report disagree."""
    widgets = [widget("w1", DATED, "By status"), widget("w2", UNDATED, "Controls by type")]
    out, unbounded = report_window.bake(None, source, widgets, START, END)
    assert unbounded == ["Controls by type"]
    assert out[1]["sql"] == UNDATED


def test_the_widgets_handed_in_are_not_written_into(source, mapped):
    original = widget("w1", DATED, "By status")
    report_window.bake(None, source, [original], START, END)
    assert original["sql"] == DATED


def test_a_text_tile_rides_through_untouched(source, mapped):
    heading = {"id": "t1", "kind": "text", "title": "Overview", "text": "..."}
    out, unbounded = report_window.bake(None, source, [heading, widget("w1", DATED, "By status")],
                                        START, END)
    assert out[0] is heading and not unbounded


def test_nothing_to_bound_asks_the_model_nothing(source, monkeypatch):
    """A plan of headings only. The column choice costs a model call, so it is not made."""
    monkeypatch.setattr(report_window.dashboard_filters, "map_filter",
                        lambda *a, **k: pytest.fail("asked the model with no chart to bound"))
    out, unbounded = report_window.bake(None, source, [{"id": "t1", "kind": "text"}], START, END)
    assert out == [{"id": "t1", "kind": "text"}] and not unbounded


def test_the_bound_is_the_one_a_date_filter_would_have_written(source, mapped):
    """Not a second way of writing a date condition: the same one, so anything the Query Service
    accepts from a filter it accepts here."""
    [w], _ = report_window.bake(None, source, [widget("w1", DATED, "By status")], START, END)
    date_filter = {"id": "win", "label": "Date range", "kind": "date", "columns":
                   {"w1": {"table": TYPE, "column": "OPSS-Ev:Date of Occurrence"}}}
    same, _, _, _ = dashboard_filters.apply(
        DATED, source, [date_filter],
        {"win": {"date_from": START.isoformat(), "date_to": END.isoformat()}}, "w1")
    assert w["sql"] == same
