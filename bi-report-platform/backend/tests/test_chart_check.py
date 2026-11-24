"""A chart that cannot be drawn says so instead of being drawn as something else.

Field names differ between OpenPages installations, and a query naming the wrong one does not
fail: the column comes back, with every cell in it empty. "Running Total of Gross Loss" arrived as
seven dates beside a blank column, and because there were no numbers in it, it was drawn as a
table - a tile that looks built, says nothing, and never tells anyone a field name is wrong.
"""

from app import chart_check

ROWS = [["30/06/2026", None], ["06/07/2026", ""], ["09/07/2026", None]]
COLUMNS = ["Occurrence Date", "Gross Loss"]


def test_a_chart_whose_number_came_back_empty_names_the_column():
    problem = chart_check.measure_problem({"type": "line", "y": ["Gross Loss"]}, COLUMNS, ROWS)
    assert problem and "Gross Loss" in problem
    assert "named something else" in problem, "the message has to say what to do about it"


def test_every_shape_that_draws_a_number_is_checked():
    for kind in chart_check.MEASURED:
        assert chart_check.measure_problem({"type": kind}, COLUMNS, ROWS), kind


def test_a_table_is_not_checked():
    """A table shows records. A column of blanks in one is a field worth questioning, but the
    tile is still doing its job, and refusing to draw it would lose the records too."""
    for kind in ("table", "matrix"):
        assert chart_check.measure_problem({"type": kind}, COLUMNS, ROWS) is None, kind


def test_one_number_anywhere_is_enough():
    rows = [["30/06/2026", None], ["06/07/2026", 1200]]
    assert chart_check.measure_problem({"type": "bar"}, COLUMNS, rows) is None


def test_a_number_written_as_text_counts():
    """An OpenPages amount arrives as a string often enough to matter."""
    rows = [["a", "1,200"], ["b", "300.5"]]
    assert chart_check.measure_problem({"type": "bar"}, COLUMNS, rows) is None


def test_a_result_with_no_rows_is_not_a_problem_of_this_kind():
    """Nothing happened in the window. That is an answer, and an empty chart says it."""
    assert chart_check.measure_problem({"type": "bar"}, COLUMNS, []) is None


def test_a_result_full_of_text_says_what_it_did_return():
    """Not empty, just not numbers - the query grouped where it should have counted. Naming the
    columns is what lets someone see that at a glance."""
    rows = [["LE_0108", "Open"], ["LE_0109", "Closed"]]
    problem = chart_check.measure_problem({"type": "pie"}, ["Name", "Status"], rows)
    assert problem and "Name, Status" in problem
