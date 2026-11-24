"""Charts grouped on a date come back by month, without anyone having to ask.

A planned dashboard says "Loss Events by Month of Occurrence" and writes SQL that groups on the
date field. OpenPages has no date functions, so that query returns one row per timestamp: ninety
points on an axis built for twelve, each labelled 2025-04-01T00:00:00.000-04:00. The reader sees a
line with one spike in it and no way to tell what the spike is.

Nothing in a plan says "this column holds dates", so this is read from the column's name and the
chart's own title. These are the guards on that reading: it fires where it should, it leaves alone
everything it is not sure about, and where it fires on a column that turns out not to hold dates
the fold keeps the values exactly as they were.
"""

from app import date_charts, date_rollup


def chart(title, x, kind="bar", **extra):
    return {"id": "w1", "title": title, "chart": {"type": kind, "x": x, "y": ["Count_Resource ID"]},
            **extra}


# ---------- when it fires ----------

def test_a_chart_grouped_on_a_date_is_folded_to_months():
    [w] = date_charts.with_rollups([chart("Loss Events by Month of Occurrence",
                                          "OPSS-LossEvent:Date of Occurrence", "line")])
    assert w["rollup"] == {"column": "OPSS-LossEvent:Date of Occurrence", "to": "month",
                           "format": "mm/yy"}


def test_the_openpages_group_prefix_does_not_hide_the_word_date():
    assert date_charts.column_holds_dates("OPSS-Risk:Creation Date")
    assert date_charts.column_holds_dates("Last Modification Date")
    assert date_charts.column_holds_dates("Completed")


def test_the_period_comes_from_what_the_chart_calls_itself():
    assert date_charts.period_for("Risks by Quarter Raised") == "quarter"
    assert date_charts.period_for("Loss by Year") == "year"
    assert date_charts.period_for("Tests by Month of Test Date") == "month"
    # A week cannot be written in mm/yy, and an axis whose labels are ambiguous is worse than a
    # coarser one, so a weekly chart is drawn by month.
    assert date_charts.period_for("Tests by Week of Completion") == "month"
    # Grouped on a date but saying no period: months, which is what these reports are read in.
    assert date_charts.period_for("Loss events over time") == "month"


# ---------- when it leaves well alone ----------

def test_a_widget_that_already_has_a_fold_keeps_its_own():
    mine = {"column": "Creation Date", "to": "year", "format": "yyyy"}
    [w] = date_charts.with_rollups([chart("Risks by Year", "Creation Date", rollup=mine)])
    assert w["rollup"] is mine


def test_tables_and_kpis_are_never_folded():
    """A table shows records, one row each - folding it would add them together. A KPI is one
    number and has no categories to fold at all."""
    for kind in ("table", "matrix", "kpi"):
        [w] = date_charts.with_rollups([chart("Control tests", "Creation Date", kind)])
        assert "rollup" not in w, kind


def test_a_column_whose_name_says_nothing_about_dates_is_left_alone():
    for column in ("OPSS-Risk:Status", "Business Entity", "Name", "Days to Discover", ""):
        [w] = date_charts.with_rollups([chart("Risks by status", column)])
        assert "rollup" not in w, column


def test_the_widget_itself_is_not_written_into():
    """The plan is read in more than one place, so a fold is added to a copy."""
    original = chart("Loss events by month", "Date of Occurrence")
    date_charts.with_rollups([original])
    assert "rollup" not in original


# ---------- and when the reading is wrong ----------

def test_a_column_named_like_a_date_that_holds_something_else_survives_the_fold():
    """The one way this can be wrong, and it costs nothing: date_rollup keeps a value it cannot
    read as a date exactly as it is, so the chart comes back as it would have anyway."""
    rows = [["Overdue", 4], ["Within period", 9]]
    folded = date_rollup.apply(["Review Period", "Count_Resource ID"], rows,
                               {"column": "Review Period", "to": "month", "format": "mm/yy"})
    assert folded["rows"] == rows
