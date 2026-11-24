"""A number tile is one number.

"Total gross loss in the window" is a sum, and the OpenPages Query Service cannot write one - it
has COUNT and nothing else. So the query comes back as every loss event and its amount, seven
hundred rows, and fit_chart turns the tile into a table: a list of event names with an empty
amount column beside it, which is the one answer nobody asked for.

These guard the fold that happens instead, and - more importantly - everything it must not touch.
A tile that already works must come out of this unchanged.
"""

from app import kpi_total

KPI = {"type": "kpi", "x": "", "y": ["Gross Loss"]}
COLUMNS = ["Name", "Gross Loss"]
ROWS = [["LE_0108", 1200], ["LE_0109", 300.5], ["LE_0116", "2,000"]]


# ---------- what it folds ----------

def test_a_number_tile_that_came_back_as_many_rows_is_added_up():
    spec = kpi_total.total_spec(KPI, COLUMNS, ROWS)
    assert spec == {"column": "Gross Loss", "to": "sum"}
    out = kpi_total.apply(COLUMNS, ROWS, spec)
    assert out == {"columns": ["Gross Loss"], "rows": [[3500.5]], "row_count": 1}


def test_a_whole_total_is_shown_as_a_whole_number():
    out = kpi_total.apply(COLUMNS, [["a", 700], ["b", 13]], {"column": "Gross Loss", "to": "sum"})
    assert out["rows"] == [[713]], "713, not 713.0"


def test_the_column_the_tile_says_it_measures_is_the_one_added_up():
    columns = ["Name", "Recovered", "Gross Loss"]
    rows = [["a", 1, 10], ["b", 2, 20]]
    spec = kpi_total.total_spec({"type": "kpi", "y": ["Gross Loss"]}, columns, rows)
    assert spec["column"] == "Gross Loss"
    assert kpi_total.apply(columns, rows, spec)["rows"] == [[30]]


def test_rows_with_no_number_in_them_are_counted_instead():
    """A tile whose count the Query Service could not write - a count that needed a join - comes
    back as the records themselves. How many there are is the number that was wanted."""
    rows = [["LE_0108", "Open"], ["LE_0109", "Open"], ["LE_0116", "Closed"]]
    spec = kpi_total.total_spec(KPI, ["Name", "Status"], rows)
    assert spec == {"column": "", "to": "count"}
    assert kpi_total.apply(["Name", "Status"], rows, spec) == {
        "columns": ["Count"], "rows": [[3]], "row_count": 1}


# ---------- what it leaves alone ----------

def test_a_tile_that_already_holds_one_number_is_untouched():
    assert kpi_total.total_spec(KPI, ["Count_Resource ID"], [[91]]) is None


def test_nothing_but_a_number_tile_is_touched():
    for kind in ("bar", "line", "pie", "donut", "table", "heatmap"):
        assert kpi_total.total_spec({"type": kind, "y": ["Gross Loss"]}, COLUMNS, ROWS) is None, kind
    assert kpi_total.total_spec(None, COLUMNS, ROWS) is None


def test_a_column_of_blanks_is_not_added_up():
    """The field name was wrong, and the column came back empty. Adding it up would put a
    confident nought on the page, which reads as a fact; counting the records does not."""
    rows = [["LE_0108", None], ["LE_0109", ""]]
    spec = kpi_total.total_spec(KPI, COLUMNS, rows)
    assert spec == {"column": "", "to": "count"}


def test_a_spec_whose_column_is_gone_leaves_the_result_as_it_is():
    """A field renamed since the report was built. The rows are shown as they came back, which a
    reader can see is wrong, rather than folded into a number that hides it."""
    assert kpi_total.apply(COLUMNS, ROWS, {"column": "Net Loss", "to": "sum"}) is None
    assert kpi_total.apply(COLUMNS, ROWS, "sum") is None


def test_text_that_is_not_a_number_never_counts_towards_a_total():
    out = kpi_total.apply(COLUMNS, [["a", 10], ["b", "not recorded"]],
                          {"column": "Gross Loss", "to": "sum"})
    assert out["rows"] == [[10]]
