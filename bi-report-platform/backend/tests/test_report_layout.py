"""
One shape for every report: counts at the top, charts three to a row, records at the bottom.

This is what makes a click on a chart work at all - the selection filters the summary table, so a
report whose table is in the middle answers "which ones?" above the question. It is also why the
rule is enforced here rather than only asked of the model: a plan that comes back in a different
order is not a failure the model reports, it is a dashboard that quietly reads differently.
"""

from app.report_layout import CHART_SIZE, KPI_SIZE, TABLE_SIZE, shape


def kpi(name, **extra):
    return {"id": name, "title": name, "chart": {"type": "kpi"}, **extra}


def bar(name, **extra):
    return {"id": name, "title": name, "chart": {"type": "bar"}, **extra}


def table(name, **extra):
    return {"id": name, "title": name, "chart": {"type": "table"}, **extra}


def heading(name, **extra):
    return {"id": name, "title": name, "kind": "text", "text": name, **extra}


def ids(widgets):
    return [w["id"] for w in widgets]


# ---------- reading order ----------

def test_counts_rise_to_the_top_and_records_sink_to_the_bottom():
    out = shape([table("records"), bar("by status"), kpi("total"), bar("by type")])
    assert ids(out) == ["total", "by status", "by type", "records"]


def test_charts_of_one_kind_keep_the_order_they_were_written_in():
    """The plan's own sequence still decides which breakdown comes first - this sorts the kinds
    apart, it does not rearrange within them."""
    out = shape([bar("first"), bar("second"), bar("third"), kpi("count")])
    assert ids(out) == ["count", "first", "second", "third"]


def test_a_report_already_in_shape_is_left_exactly_as_it_is():
    widgets = [kpi("a"), bar("b"), table("c")]
    assert ids(shape(widgets)) == ["a", "b", "c"]


def test_nothing_given_is_changed():
    """Pure, so a caller can compare before and after - and so a template defined once at import
    time is not quietly rewritten for the next reader."""
    original = [table("records"), kpi("total")]
    before = [dict(w) for w in original]
    shape(original)
    assert original == before


# ---------- headings and tabs are boundaries ----------

def test_a_heading_keeps_the_charts_that_belong_under_it():
    """Reordering across a heading would file charts under the wrong one, which is worse than the
    order it was trying to fix."""
    out = shape([heading("Losses"), bar("loss by type"), table("loss records"),
                 heading("Controls"), bar("control by status"), kpi("controls")])
    assert ids(out) == ["Losses", "loss by type", "loss records",
                        "Controls", "controls", "control by status"]


def test_each_tab_is_ordered_against_itself():
    """A table at the end of tab one does not belong after tab three."""
    out = shape([table("t1 records", page="one"), kpi("t1 count", page="one"),
                 table("t2 records", page="two"), kpi("t2 count", page="two")])
    assert ids(out) == ["t1 count", "t1 records", "t2 count", "t2 records"]


def test_tabs_keep_the_order_they_first_appear_in():
    out = shape([bar("b", page="two"), bar("a", page="one")])
    assert [w["page"] for w in out] == ["two", "one"]


# ---------- widths ----------

def test_three_charts_to_a_row():
    out = shape([bar("a"), bar("b"), bar("c")])
    assert [w["size"] for w in out] == [CHART_SIZE] * 3


def test_a_summary_table_gets_the_full_width_and_counts_a_quarter():
    out = shape([kpi("count"), bar("by status"), table("records")])
    assert [w["size"] for w in out] == [KPI_SIZE, CHART_SIZE, TABLE_SIZE]


def test_a_width_set_by_hand_is_brought_into_line():
    """The point of the house layout is that every report reads the same; a half-width chart left
    alone would leave a gap beside it where the third chart of that row should be."""
    assert shape([bar("wide", size="full")])[0]["size"] == CHART_SIZE


def test_a_heading_is_not_given_a_chart_width():
    out = shape([heading("Losses", size="full"), bar("b")])
    assert out[0]["size"] == "full"


# ---------- nothing to do ----------

def test_an_empty_report_is_fine():
    assert shape([]) == []
    assert shape(None) == []
