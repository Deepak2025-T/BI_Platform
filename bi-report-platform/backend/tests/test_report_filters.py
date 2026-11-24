"""The filters a detail report opens with.

A page of twenty counts invites exactly one question - "yes, but for my part of the business" -
and without a filter the answer is "build another report", which in front of a client is the same
as no. So each of the four carries the business entity, the window, and the two fields its own
subject is divided by.

These pin the two ways a column is chosen, and the rule that matters more than either: a filter
that reaches no chart is not offered. A control someone sets, that changes nothing on the page, is
worse than one that was never there.
"""

import pytest

from app import report_filters
from app.datasources import DataSource
from app.openpages_detail_reports import REPORTS
from app.report_filters import ENTITY, WINDOW, Wanted

TYPE = "openpages.Loss Event"
SQL = ("SELECT [Loss Event].[OPSS-Ev:Status], COUNT([Loss Event].[Resource ID]) "
       "FROM [Loss Event] GROUP BY [Loss Event].[OPSS-Ev:Status]")


@pytest.fixture
def source(monkeypatch) -> DataSource:
    # Both of these reach OpenPages and have tests of their own; here the subject is the choosing.
    monkeypatch.setattr(report_filters.dashboard_filters, "column_values",
                        lambda src, table, column, limit=200: ["/Group/Retail", "/Group/Markets"])
    monkeypatch.setattr(report_filters.dashboard_filters, "table_columns",
                        lambda src, table: [("Location", "text"), ("OPSS-Ev:Status", "text")])
    return DataSource(id=7, name="GRC", db_type="openpages", version="v1", tables=[TYPE])


def widget(wid="w1", sql=SQL):
    return {"id": wid, "title": "By status", "sql": sql, "chart": {"type": "bar"}}


def test_the_business_entity_costs_no_model_call(source, monkeypatch):
    """[Location] is a system field on every object type, so the column is known before anyone is
    asked. Twenty charts would otherwise be twenty questions with one answer."""
    monkeypatch.setattr(report_filters.dashboard_filters, "map_filter",
                        lambda *a, **k: pytest.fail("asked the model for a field it already knew"))
    [built] = report_filters.build(None, source, [widget()], (ENTITY,))
    assert built["label"] == "Business entity"
    assert built["columns"]["w1"]["column"] == "Location"
    assert built["options"] == ["/Group/Markets", "/Group/Retail"]


def test_a_named_field_is_chosen_per_chart(source, monkeypatch):
    """"Residual rating" is one field name on one installation and another on the next, so the
    column is picked from the fields that chart's object types really have."""
    asked = []

    def fake(spec, src, label, kind, widgets, filter_id=None):
        asked.append((label, kind))
        return {"id": "f2", "label": label, "kind": kind, "options": [],
                "columns": {w["id"]: {"table": TYPE, "column": "OPSS-Ev:Status"} for w in widgets}}
    monkeypatch.setattr(report_filters.dashboard_filters, "map_filter", fake)
    [built] = report_filters.build(None, source, [widget()], (Wanted("Loss event status"),))
    assert asked == [("Loss event status", "category")]
    assert built["columns"]["w1"]["column"] == "OPSS-Ev:Status"


def test_a_filter_that_reaches_no_chart_is_not_offered(source, monkeypatch):
    monkeypatch.setattr(report_filters.dashboard_filters, "map_filter",
                        lambda *a, **k: {"id": "f3", "label": "Owner", "kind": "category",
                                         "options": [], "columns": {}})
    assert report_filters.build(None, source, [widget()], (Wanted("Owner"),)) == []


def test_a_filter_that_cannot_be_worked_out_costs_the_report_nothing(source, monkeypatch):
    """A model that would not answer, or a field list that would not load. The report is still
    built - one filter fewer is a small loss and a failed build is a total one."""
    def boom(*a, **k):
        raise RuntimeError("the model timed out")
    monkeypatch.setattr(report_filters.dashboard_filters, "map_filter", boom)
    built = report_filters.build(None, source, [widget()], (Wanted("Owner"), ENTITY))
    assert [f["label"] for f in built] == ["Business entity"]


def test_text_tiles_are_not_charts_to_filter(source, monkeypatch):
    monkeypatch.setattr(report_filters.dashboard_filters, "map_filter",
                        lambda *a, **k: pytest.fail("asked the model with no chart to filter"))
    assert report_filters.build(None, source, [{"id": "t1", "kind": "text"}], (Wanted("Owner"),)) == []


def test_every_detail_report_asks_for_at_least_three(source):
    """Two shared with every report, two of its own - so the thinnest of them still opens with
    four controls over the page."""
    for report in REPORTS:
        assert len(report.filters) >= 2, report.id
        assert len((ENTITY, WINDOW, *report.filters)) >= 3, report.id
        assert len(set(report.filters)) == len(report.filters), f"{report.id} repeats a filter"
        for label in report.filters:
            assert label[0].isupper() and label.lower() != label, f"{report.id}: {label!r}"
