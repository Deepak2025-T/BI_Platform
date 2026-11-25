"""Totalling a result by a category, after the query has run.

Five charts of one loss report came back as "the query didn't work": Total Gross Loss by Business
Entity, the same by month, Total Net Loss by month, Gross Loss against Recovered by entity, and
Total Impact Amount by Effect Category. Every one of them is a sum per group, and the OpenPages
Query Service can write neither half - no SUM, and GROUP BY only beside its own COUNT.

The query that does run is the one with no grouping at all, one row per record. These guard the
fold that turns it into the chart that was asked for, and the cases it must not touch.
"""

from app import group_total

COLUMNS = ["Location", "Gross Loss", "Status"]
ROWS = [["/Group/Retail", 10000, "Open"],
        ["/Group/Markets", 2000, "Open"],
        ["/Group/Retail", 20000, "Approved"],
        ["/Group/Retail", "4,000", "Open"]]
BAR = {"type": "bar", "x": "Location", "y": ["Gross Loss"]}


# ---------- what it folds ----------

def test_rows_sharing_a_category_become_one_row_with_the_total():
    spec = group_total.group_spec(BAR, COLUMNS, ROWS)
    assert spec == {"column": "Location", "to": "sum", "order": "desc"}
    out = group_total.apply(COLUMNS, ROWS, spec)
    assert out["columns"] == COLUMNS
    assert [r[:2] for r in out["rows"]] == [["/Group/Retail", 34000], ["/Group/Markets", 2000]]
    assert out["row_count"] == 2


def test_the_biggest_comes_first():
    """"Total gross loss by business entity, biggest first" is how these are asked for, and a
    bar chart that is not ranked is read wrong: the eye takes the first bar for the largest."""
    out = group_total.apply(COLUMNS, ROWS, group_total.group_spec(BAR, COLUMNS, ROWS))
    assert [r[1] for r in out["rows"]] == [34000, 2000]


def test_an_amount_written_as_text_is_added_like_any_other():
    """An OpenPages currency arrives as a string often enough to matter: 4,000 is four thousand."""
    out = group_total.apply(COLUMNS, ROWS, {"column": "Location", "to": "sum"})
    assert dict((r[0], r[1]) for r in out["rows"])["/Group/Retail"] == 34000


def test_a_whole_total_is_shown_as_a_whole_number():
    out = group_total.apply(COLUMNS, [["a", 1, "x"], ["a", 2, "x"]], {"column": "Location", "to": "sum"})
    assert out["rows"][0][1] == 3, "3, not 3.0"


def test_what_is_not_a_number_comes_from_the_first_row_of_its_group():
    """A group of records has no single status to show. The first one's is kept rather than
    blanked, so a column that was there is still there."""
    out = group_total.apply(COLUMNS, ROWS, {"column": "Location", "to": "sum"})
    assert out["rows"][0][2] == "Open"


# ---------- what it leaves alone ----------

def test_a_result_that_already_holds_one_row_per_category_is_untouched():
    """What a GROUP BY would have produced. Folding it would do nothing and risk reordering it."""
    rows = [["/Group/Retail", 10000, "Open"], ["/Group/Markets", 2000, "Open"]]
    assert group_total.group_spec(BAR, COLUMNS, rows) is None


def test_a_result_with_nothing_to_add_is_untouched():
    """Counting by a category is something the Query Service can do itself, so a result with no
    amount in it is a list of records and folding it would lose them."""
    rows = [["/Group/Retail", "Open"], ["/Group/Retail", "Approved"]]
    assert group_total.group_spec({"type": "bar", "x": "Location"}, ["Location", "Status"], rows) is None


def test_a_table_is_never_folded():
    """A table shows records. Adding its rows together is exactly what nobody wants from one."""
    for kind in ("table", "matrix", "kpi"):
        assert group_total.group_spec({**BAR, "type": kind}, COLUMNS, ROWS) is None, kind


def test_a_chart_whose_category_column_is_not_in_the_result_is_untouched():
    assert group_total.group_spec({"type": "bar", "x": "Owner"}, COLUMNS, ROWS) is None


def test_a_spec_whose_column_is_gone_leaves_the_result_as_it_is():
    """A field renamed since the report was built: the rows are shown as they came back, which a
    reader can see is wrong, rather than folded into totals that hide it."""
    assert group_total.apply(COLUMNS, ROWS, {"column": "Owner", "to": "sum"}) is None
    assert group_total.apply(COLUMNS, ROWS, "sum") is None


def test_the_rows_handed_in_are_not_written_into():
    before = [list(r) for r in ROWS]
    group_total.apply(COLUMNS, ROWS, {"column": "Location", "to": "sum"})
    assert ROWS == before
