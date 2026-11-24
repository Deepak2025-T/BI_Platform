"""Folding a result's dates to a period after the query has run.

This is what an IBM OpenPages chart uses instead of grouping by month in SQL: its Query Service has
COUNT and no date functions, so "SELECT [SOXRisk].[Creation Date], COUNT(...)" comes back one row
per date and the months are worked out here.
"""

import datetime as dt

from app import date_rollup

COLUMNS = ["Creation Date", "Count_Resource ID"]
MONTH = {"column": "Creation Date", "to": "month", "format": "mm/yyyy"}


def test_counts_are_added_up_per_month():
    rows = [["2026-09-28", 3], ["2026-10-02", 5], ["2026-10-19", 4], ["2026-11-01", 2]]
    out = date_rollup.apply(COLUMNS, rows, MONTH)
    assert out["columns"] == COLUMNS
    assert out["rows"] == [["09/2026", 3], ["10/2026", 9], ["11/2026", 2]]
    assert out["row_count"] == 3


def test_months_come_back_in_date_order_not_alphabetical():
    rows = [["2027-01-04", 1], ["2026-02-11", 1], ["2026-12-30", 1]]
    out = date_rollup.apply(COLUMNS, rows, MONTH)
    assert [r[0] for r in out["rows"]] == ["02/2026", "12/2026", "01/2027"]


def test_newest_first_when_asked():
    rows = [["2026-02-11", 1], ["2026-12-30", 2]]
    out = date_rollup.apply(COLUMNS, rows, {**MONTH, "order": "desc"})
    assert [r[0] for r in out["rows"]] == ["12/2026", "02/2026"]


def test_timestamps_dates_and_day_first_text_all_parse():
    rows = [["2026-10-02T06:30:00Z", 1], [dt.date(2026, 10, 9), 1],
            [dt.datetime(2026, 10, 20, 9, 0), 1], ["21/10/2026", 1]]
    out = date_rollup.apply(COLUMNS, rows, MONTH)
    assert out["rows"] == [["10/2026", 4]]


def test_a_spec_with_no_format_labels_months_the_short_way():
    """What a chart shows when nothing asks for anything else. An axis is read at a glance and
    the year is only there to tell one January from the next, so the two digits are enough -
    and they are half the width, which is the difference between an axis that fits and one that
    writes its labels over each other."""
    rows = [["2026-09-28", 3], ["2026-10-02", 5]]
    out = date_rollup.apply(COLUMNS, rows, {"column": "Creation Date", "to": "month"})
    assert out["rows"] == [["09/26", 3], ["10/26", 5]]


def test_quarter_and_year_have_their_own_shapes():
    rows = [["2026-02-11", 1], ["2026-05-02", 2], ["2027-01-09", 4]]
    quarters = date_rollup.apply(COLUMNS, rows, {"column": "Creation Date", "to": "quarter"})
    assert quarters["rows"] == [["Q1 26", 1], ["Q2 26", 2], ["Q1 27", 4]]
    years = date_rollup.apply(COLUMNS, rows, {"column": "Creation Date", "to": "year"})
    assert years["rows"] == [["2026", 3], ["2027", 4]]


def test_a_value_that_is_not_a_date_is_kept_and_sorted_last():
    rows = [["2026-10-02", 2], ["Not recorded", 7]]
    out = date_rollup.apply(COLUMNS, rows, MONTH)
    assert out["rows"] == [["10/2026", 2], ["Not recorded", 7]]


def test_other_columns_ride_along_and_text_is_not_summed():
    columns = ["Creation Date", "OPSS-Risk:Status", "Count_Resource ID"]
    rows = [["2026-10-02", "Open", 2], ["2026-10-19", "Open", 3]]
    out = date_rollup.apply(columns, rows, MONTH)
    assert out["rows"] == [["10/2026", "Open", 5]]


def test_a_spec_that_does_not_fit_leaves_the_result_alone():
    assert date_rollup.apply(COLUMNS, [["2026-10-02", 1]], {"column": "Nope", "to": "month"}) is None
    assert date_rollup.apply(COLUMNS, [["2026-10-02", 1]], {"column": "Creation Date", "to": "fortnight"}) is None
    assert date_rollup.apply(COLUMNS, [["2026-10-02", 1]], "month") is None


# ---------- the two shapes a date is shown in ----------

def test_a_date_in_a_table_keeps_its_day_and_one_on_a_label_does_not():
    """The rule for every report: a table is a list of records and the day is the point of it, so
    dd/mm/yyyy. A chart axis is read at a glance and the day there is noise that costs the axis
    its room, so mm/yy. The same two shapes the browser uses, so an exported deck reads the way
    the report read on screen."""
    assert date_rollup.table_text("2026-05-04T08:46:45.000-04:00") == "04/05/2026"
    assert date_rollup.label_text("2026-05-04T08:46:45.000-04:00") == "05/26"
    assert date_rollup.table_text(dt.date(2026, 11, 3)) == "03/11/2026"
    assert date_rollup.label_text(dt.date(2026, 11, 3)) == "11/26"


def test_a_value_that_is_not_a_date_comes_back_as_it_reads():
    for value in ("Open", "11/25", "Q1 26", 2026, None):
        assert date_rollup.table_text(value) == ("" if value is None else str(value))
        assert date_rollup.label_text(value) == ("" if value is None else str(value))
