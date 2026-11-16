"""Splitting a long report into one page per section heading."""

from app.dashboard_pages import FIRST_PAGE, split_by_headings


def _heading(title, text=""):
    return {"kind": "text", "title": title, "text": text, "chart": {"type": "table"}}


def _chart(title):
    return {"title": title, "sql": "SELECT 1", "chart": {"type": "bar"}}


def _long(sections):
    """A report of `sections` headings with four charts under each."""
    out = []
    for name in sections:
        out.append(_heading(name))
        out += [_chart(f"{name} {i}") for i in range(4)]
    return out


def test_a_short_report_is_left_on_one_page():
    """Two sections of four charts read fine as a scroll; tabs would only add a click."""
    widgets = _long(["Risk", "Control"])
    pages, out = split_by_headings(widgets)
    assert pages == []
    assert out == widgets  # unchanged, not merely equal in length


def test_one_heading_is_not_a_split():
    """Sixteen charts under a single heading is still one subject, and so still one page."""
    widgets = [_heading("Risk")] + [_chart(f"Risk {i}") for i in range(16)]
    pages, out = split_by_headings(widgets)
    assert pages == []
    assert out == widgets


def test_a_long_report_becomes_one_page_per_section():
    widgets = _long(["Risk profile", "Control effectiveness", "Process coverage", "Business entity scope"])
    pages, out = split_by_headings(widgets)

    assert [p["name"] for p in pages] == ["Risk profile", "Control effectiveness",
                                          "Process coverage", "Business entity scope"]
    assert len({p["id"] for p in pages}) == 4
    # Every chart landed on the page of the heading it was under, and none was lost.
    assert len([w for w in out if w.get("sql")]) == 16
    by_page = {p["id"]: p["name"] for p in pages}
    for widget in out:
        if widget.get("sql"):
            assert by_page[widget["page"]] == widget["title"].rsplit(" ", 1)[0]


def test_what_sits_above_the_first_heading_opens_the_report():
    """The row of totals at the top belongs to nobody's section, so it gets the landing page."""
    widgets = [_chart("Total risks"), _chart("Open issues")] + _long(["Risk profile", "Control effectiveness",
                                                                     "Process coverage"])
    pages, out = split_by_headings(widgets)

    assert pages[0]["name"] == FIRST_PAGE
    opening = [w for w in out if w.get("page") == pages[0]["id"]]
    assert [w["title"] for w in opening] == ["Total risks", "Open issues"]


def test_a_headings_note_survives_as_a_note_without_repeating_the_tab_name():
    widgets = _long(["Risk profile", "Control effectiveness", "Process coverage"])
    widgets[0] = _heading("Risk profile", "Where the risks stand.")
    pages, out = split_by_headings(widgets)

    note = next(w for w in out if w.get("kind") == "text")
    assert note["text"] == "Where the risks stand."
    assert note["title"] == ""        # the tab says it; the page needn't say it again
    assert note["page"] == pages[0]["id"]


def test_a_heading_whose_charts_were_all_dropped_leaves_no_empty_tab():
    """Charts a connection can't answer are left out before this runs, headings and all."""
    widgets = _long(["Risk profile", "Control effectiveness", "Process coverage"]) + [_heading("Vendors")]
    pages, _ = split_by_headings(widgets)
    assert [p["name"] for p in pages] == ["Risk profile", "Control effectiveness", "Process coverage"]


def test_every_widget_keeps_its_own_fields():
    widgets = _long(["A", "B", "C"])
    _, out = split_by_headings(widgets)
    assert all(w.get("chart") for w in out)
    assert all("page" in w for w in out)
