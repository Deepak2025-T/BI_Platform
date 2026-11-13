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


def test_quarter_and_year_have_their_own_shapes():
    rows = [["2026-02-11", 1], ["2026-05-02", 2], ["2027-01-09", 4]]
    quarters = date_rollup.apply(COLUMNS, rows, {"column": "Creation Date", "to": "quarter"})
    assert quarters["rows"] == [["Q1 2026", 1], ["Q2 2026", 2], ["Q1 2027", 4]]
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
