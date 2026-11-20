"""Splitting a long report into one page per section heading."""

from app.dashboard_pages import FIRST_PAGE, pages_from_sections, split_by_headings


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


# ---------------------------------------------------------------- filters that belong to one tab

from app.dashboard_pages import ONE_PAGE, page_of, pages_of          # noqa: E402
from app.report_data import filters_for                              # noqa: E402


def test_a_report_with_no_pages_has_one_implied_one():
    """Every report saved before pages existed, and every short one since."""
    pages = pages_of({})
    assert [p["id"] for p in pages] == [ONE_PAGE]
    assert page_of(pages, {"id": "a"}) == ONE_PAGE


def test_a_tile_naming_a_deleted_page_falls_to_the_first():
    """A tile can be orphaned by an edit; it can never become invisible."""
    pages = [{"id": "p1", "name": "One"}, {"id": "p2", "name": "Two"}]
    assert page_of(pages, {"page": "gone"}) == "p1"
    assert page_of(pages, {"page": "p2"}) == "p2"


_PAGES = [{"id": "p1", "name": "Overview"}, {"id": "p2", "name": "Controls"}]


def test_a_filter_on_the_whole_report_reaches_every_tab():
    config = {"pages": _PAGES, "filters": [{"id": "f1", "label": "Date"}]}
    for widget in ({"id": "w", "page": "p1"}, {"id": "w", "page": "p2"}):
        assert [f["id"] for f in filters_for(config, widget)] == ["f1"]


def test_a_filter_given_a_tab_leaves_the_other_tabs_alone():
    """Two tabs can sit at two different dates at once, which is the point of it."""
    config = {"pages": _PAGES, "filters": [{"id": "f1", "label": "Date"},
                                           {"id": "f2", "label": "Status", "page": "p2"}]}
    assert [f["id"] for f in filters_for(config, {"id": "w", "page": "p1"})] == ["f1"]
    assert [f["id"] for f in filters_for(config, {"id": "w", "page": "p2"})] == ["f1", "f2"]


def test_a_tab_filter_reaches_the_tiles_that_never_named_a_page():
    """Those tiles are drawn on the first page, so they are filtered by the first page's filters."""
    config = {"pages": _PAGES, "filters": [{"id": "f2", "label": "Status", "page": "p1"}]}
    assert [f["id"] for f in filters_for(config, {"id": "w"})] == ["f2"]


def test_nothing_changes_for_a_report_whose_filters_name_no_page():
    """The common case stays the cheap case: the list is handed back as it is."""
    filters = [{"id": "f1"}, {"id": "f2"}]
    config = {"pages": _PAGES, "filters": filters}
    assert filters_for(config, {"id": "w", "page": "p2"}) == filters


# ---------- Tabs the request itself asked for ----------

def _charts(n: int) -> list[dict]:
    return [{"id": f"w{i}", "title": f"Chart {i}"} for i in range(n)]


def test_charts_are_put_on_the_tab_the_request_named():
    widgets = _charts(4)
    pages = pages_from_sections(widgets, ["Risk", "Risk", "Control", "Control"])
    assert [p["name"] for p in pages] == ["Risk", "Control"]
    assert [w["page"] for w in widgets] == [pages[0]["id"], pages[0]["id"], pages[1]["id"], pages[1]["id"]]


def test_the_tabs_come_out_in_the_order_they_were_asked_for():
    widgets = _charts(3)
    pages = pages_from_sections(widgets, ["Issues", "Risk", "Issues"])
    assert [p["name"] for p in pages] == ["Issues", "Risk"]


def test_a_tab_named_twice_in_different_words_is_one_tab():
    """A model that writes "Risk profile" once and "risk  profile" the next time meant one tab,
    and two tabs of the same name is the thing people notice first."""
    widgets = _charts(3)
    pages = pages_from_sections(widgets, ["Risk profile", "risk  profile", "Controls"])
    assert [p["name"] for p in pages] == ["Risk profile", "Controls"]
    assert widgets[0]["page"] == widgets[1]["page"]


def test_the_charts_of_a_tab_are_put_together():
    """A report filters by tab on screen whatever the order, but it prints and exports in the
    order the list is in, and interleaved is how that comes out wrong."""
    widgets = _charts(4)
    pages = pages_from_sections(widgets, ["A", "B", "A", "B"])
    assert [w["id"] for w in widgets] == ["w0", "w2", "w1", "w3"]
    assert [w["page"] for w in widgets] == [pages[0]["id"]] * 2 + [pages[1]["id"]] * 2


def test_one_tab_is_no_tabs():
    """A report of one page is a report of one page: a lone tab is a click with nothing behind it."""
    widgets = _charts(2)
    assert pages_from_sections(widgets, ["Everything", "Everything"]) == []
    assert all("page" not in w for w in widgets)


def test_a_plan_that_named_no_tabs_is_left_alone():
    widgets = _charts(3)
    assert pages_from_sections(widgets, ["", "", ""]) == []
    assert all("page" not in w for w in widgets)


def test_tabs_are_refused_unless_every_chart_landed_on_one():
    """Half an answer would scatter the unnamed charts onto a tab they were never meant for,
    which is worse than the single page they would otherwise have shared."""
    widgets = _charts(3)
    assert pages_from_sections(widgets, ["Risk", "", "Control"]) == []
    assert all("page" not in w for w in widgets)


def test_a_mismatched_plan_changes_nothing():
    widgets = _charts(3)
    assert pages_from_sections(widgets, ["Risk", "Control"]) == []
    assert all("page" not in w for w in widgets)
