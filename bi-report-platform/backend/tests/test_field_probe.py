"""Asking the connection which fields hold something, before a report is planned around them.

A loss report is mostly about money, and on this installation none of the money could be read:
Gross Loss, Net Loss and Recovery Amount on the event, Actual Loss on the impacts, Actual Recovery
Amount on the recoveries. Every one exists, has the Currency type, and came back empty for every
record, while every ordinary field beside them came back filled. Nothing in a field list says so,
and the first anyone knew was a report with eight charts missing.
"""

import pytest

from app import field_probe
from app.datasources import DataSource
from app.field_probe import Field

EVENT_FIELDS = [("Name", "string"), ("OPSS-LossEv:Gross Loss", "currency"),
                ("OPSS-LossEv:Business Line", "enum")]
GROSS = Field("LossEvent", "Gross Loss")
LINE = Field("LossEvent", "Business Line")
MISSING = Field("LossEvent", "Recovered In Full")


@pytest.fixture
def source() -> DataSource:
    return DataSource(id=7, name="GRC", db_type="openpages", version="v1",
                      tables=["openpages.LossEvent"])


@pytest.fixture
def connection(monkeypatch):
    """A connection whose Gross Loss column exists and is empty, as this installation's is."""
    monkeypatch.setattr(field_probe, "table_columns", lambda src, qualified: EVENT_FIELDS)

    def rows_for(source, sql, params=None, **kw):
        if "Gross Loss" in sql:
            return {"columns": ["Gross Loss"], "rows": [[None], [""], [None]]}
        return {"columns": ["Business Line"], "rows": [["Commercial Banking"], [None]]}
    monkeypatch.setattr(field_probe, "run_sql", rows_for)


def test_a_field_filed_under_its_group_is_still_found(source, connection):
    """OpenPages reports "Gross Loss" as "OPSS-LossEv:Gross Loss" on some connections and as the
    bare name on others, and a report cannot know which it is talking to."""
    assert field_probe.real_column(source, "LossEvent", "Gross Loss") == "OPSS-LossEv:Gross Loss"
    assert field_probe.real_column(source, "LossEvent", "Name") == "Name"
    assert field_probe.real_column(source, "LossEvent", "Recovered In Full") is None


def test_a_column_that_is_there_and_empty_counts_as_unreadable(source, connection):
    found, empty = field_probe.readable(source, (GROSS, LINE))
    assert found == [LINE] and empty == [GROSS]


def test_a_field_the_type_does_not_have_counts_as_unreadable(source, connection):
    """Which is what it is, as far as a chart is concerned."""
    _, empty = field_probe.readable(source, (MISSING,))
    assert empty == [MISSING]


def test_the_prompt_is_told_which_fields_to_use_and_which_to_leave(source, connection):
    note, unreadable = field_probe.advice(source, (GROSS, LINE))
    assert "[LossEvent].[Business Line]" in note and "hold figures" in note
    assert "[LossEvent].[Gross Loss]" in note and "came back empty" in note
    assert unreadable == ["[LossEvent].[Gross Loss]"]


def test_where_no_amount_can_be_read_the_report_is_told_to_count_instead(source, connection):
    """Eight charts that cannot exist are worth less than fifteen that can. The report is still a
    report; it is just not about money, and the page says why."""
    note, unreadable = field_probe.advice(source, (GROSS,))
    assert "No amount on this connection can be read at all" in note
    assert "counts alone" in note
    assert unreadable == ["[LossEvent].[Gross Loss]"]


def test_nothing_is_said_when_every_field_can_be_read(source, connection):
    """The prompt is long enough already; a paragraph saying "all is well" earns no room in it."""
    assert field_probe.advice(source, (LINE,)) == ("", [])
    assert field_probe.advice(source, ()) == ("", [])


def test_a_connection_that_will_not_answer_costs_the_report_nothing(source, monkeypatch):
    """The field is reported unreadable, which is the safe way round: the report is built from
    counts rather than from charts that would have failed one at a time."""
    monkeypatch.setattr(field_probe, "table_columns", lambda src, qualified: EVENT_FIELDS)

    def refuse(*a, **k):
        raise RuntimeError("OP-60002: The query failed to be transformed into SQL")
    monkeypatch.setattr(field_probe, "run_sql", refuse)
    found, empty = field_probe.readable(source, (GROSS, LINE))
    assert not found and empty == [GROSS, LINE]
