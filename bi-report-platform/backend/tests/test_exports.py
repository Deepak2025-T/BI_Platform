"""
Taking a dashboard away with you: the PowerPoint deck, and the words behind OpenPages enum codes.

The deck is checked for what a slide actually holds (a chart, a table, a number), because a deck
that opens but shows nothing is the failure worth catching. The enum labelling is checked both
ways: results come back labelled, and a filter's choice turns back into the code the SQL needs.
"""

from pptx import Presentation
from pptx.util import Inches

from app.connections.openpages import OpenPagesClient
from app.ppt_export import MAX_TABLE_ROWS, dashboard_deck


# ---------- PowerPoint ----------

def widget(wid: str, title: str, kind: str, x: str = "", y: list[str] | None = None, **extra) -> dict:
    return {"id": wid, "title": title, "chart": {"type": kind, "x": x, "y": y or []}, "sql": "", **extra}


def result(wid: str, columns: list[str], rows: list[list], **extra) -> dict:
    return {"id": wid, "ok": True, "columns": columns, "rows": rows, **extra}


def deck_of(widgets: list[dict], results: list[dict], values: dict | None = None,
            filters: list[dict] | None = None) -> Presentation:
    config = {"kind": "dashboard", "widgets": widgets, "filters": filters or []}
    data = dashboard_deck("Audit Plan Item Overview", config, "Timus demo", results, values or {})
    import io
    return Presentation(io.BytesIO(data))


def kinds(slide) -> list[str]:
    return ["chart" if s.has_chart else "table" if s.has_table else "text" for s in slide.shapes]


def test_a_cover_slide_then_one_slide_per_chart():
    widgets = [widget("a", "Plan items by status", "pie", "Status", ["Count_Resource ID"]),
               widget("b", "Plan items", "kpi", "", ["Count_Resource ID"])]
    results = [result("a", ["Status", "Count_Resource ID"], [["Planned", 3], ["Completed", 28]]),
               result("b", ["Count_Resource ID"], [[38]])]
    deck = deck_of(widgets, results)
    assert len(deck.slides) == 3
    assert "Audit Plan Item Overview" in deck.slides[0].shapes[0].text_frame.text
    assert "Timus demo" in deck.slides[0].shapes[1].text_frame.text


def test_a_chart_becomes_a_powerpoint_chart_with_its_numbers():
    rows = [["Planned", 3], ["Completed", 28]]
    deck = deck_of([widget("a", "By status", "bar", "Status", ["Count_Resource ID"])],
                   [result("a", ["Status", "Count_Resource ID"], rows)])
    chart = next(s.chart for s in deck.slides[1].shapes if s.has_chart)
    assert list(chart.plots[0].categories) == ["Planned", "Completed"]
    assert list(chart.series[0].values) == [3.0, 28.0]


def test_a_pie_slice_carries_its_own_colour():
    # Every slice the same colour would be a pie of one block.
    deck = deck_of([widget("a", "By status", "pie", "Status", ["Count_Resource ID"])],
                   [result("a", ["Status", "Count_Resource ID"], [["Planned", 3], ["Completed", 28]])])
    chart = next(s.chart for s in deck.slides[1].shapes if s.has_chart)
    colours = [p.format.fill.fore_color.rgb for p in chart.series[0].points]
    assert len(set(colours)) == 2


def test_the_dashboard_s_own_palette_is_used():
    deck = deck_of([widget("a", "By status", "bar", "Status", ["n"], style={"palette": ["#112233", "#445566"]})],
                   [result("a", ["Status", "n"], [["Planned", 3]])])
    chart = next(s.chart for s in deck.slides[1].shapes if s.has_chart)
    assert str(chart.series[0].format.fill.fore_color.rgb) == "112233"


def test_a_number_tile_becomes_one_big_figure():
    deck = deck_of([widget("a", "Total plan items", "kpi")], [result("a", ["Count_Resource ID"], [[38]])])
    texts = [s.text_frame.text for s in deck.slides[1].shapes if s.has_text_frame]
    assert "38" in texts


def test_a_table_becomes_a_table_and_says_what_was_left_out():
    rows = [[f"Plan {i}", i] for i in range(MAX_TABLE_ROWS + 6)]
    deck = deck_of([widget("a", "Plans by effort", "table")], [result("a", ["Name", "Effort"], rows)])
    slide = deck.slides[1]
    assert "table" in kinds(slide)
    table = next(s.table for s in slide.shapes if s.has_table)
    assert len(table.rows) == MAX_TABLE_ROWS + 1  # the heading row, then as many as fit
    assert any(f"of {len(rows)} rows" in s.text_frame.text for s in slide.shapes if s.has_text_frame)


def test_a_chart_that_could_not_run_says_so_instead_of_being_dropped():
    deck = deck_of([widget("a", "Ageing analysis", "bar", "Bucket", ["n"])],
                   [{"id": "a", "ok": False, "error": "no column called [OPSS-ActItem:Aging Bucket]"}])
    assert len(deck.slides) == 2
    assert any("Aging Bucket" in s.text_frame.text for s in deck.slides[1].shapes if s.has_text_frame)


def test_a_chart_with_no_rows_says_so():
    deck = deck_of([widget("a", "By status", "pie", "Status", ["n"])], [result("a", ["Status", "n"], [])])
    assert any("no rows" in s.text_frame.text for s in deck.slides[1].shapes if s.has_text_frame)


def test_the_filters_the_viewer_had_are_written_on_the_cover():
    deck = deck_of([widget("a", "By status", "pie", "Status", ["n"])],
                   [result("a", ["Status", "n"], [["Planned", 3]])],
                   values={"f1": {"values": ["Planned"]}},
                   filters=[{"id": "f1", "label": "Plan item status", "kind": "category"}])
    cover = " ".join(s.text_frame.text for s in deck.slides[0].shapes if s.has_text_frame)
    assert "Plan item status: Planned" in cover


def test_text_tiles_get_no_slide_of_their_own():
    widgets = [{"id": "t", "kind": "text", "title": "Section", "text": "Notes"},
               widget("a", "By status", "pie", "Status", ["n"])]
    deck = deck_of(widgets, [result("a", ["Status", "n"], [["Planned", 3]])])
    assert len(deck.slides) == 2


def test_the_slides_are_widescreen():
    deck = deck_of([widget("a", "By status", "pie", "Status", ["n"])],
                   [result("a", ["Status", "n"], [["Planned", 3]])])
    assert round(deck.slide_width / deck.slide_height, 2) == round(Inches(16) / Inches(9), 2)


# ---------- OpenPages enum codes ----------

PLAN_ITEM = {"name": "Audit Plan Item", "fieldDefinitions": {"fieldDefinition": [
    {"name": "IAM-PlanItem-FG:Status", "dataType": "ENUM_TYPE", "enumValues": {"enumValue": [
        {"name": "1", "localizedLabel": "Planned"}, {"name": "4", "localizedLabel": "Completed"}]}},
    {"name": "Name", "dataType": "STRING_TYPE"},
]}}
ISSUE = {"name": "SOXIssue", "fieldDefinitions": {"fieldDefinition": [
    {"name": "OPSS-Iss:Status", "dataType": "ENUM_TYPE", "enumValues": {"enumValue": [
        {"name": "Open", "localizedLabel": "Open"}, {"name": "Closed", "localizedLabel": "Closed"}]}},
]}}


def client_with(*types: dict) -> OpenPagesClient:
    """A client that answers from these type definitions and never goes near a network."""
    c = OpenPagesClient.__new__(OpenPagesClient)
    c._types = {t["name"]: t for t in types}
    return c


def test_a_coded_enum_comes_back_as_the_words_people_read():
    c = client_with(PLAN_ITEM)
    sql = ("SELECT [Audit Plan Item].[IAM-PlanItem-FG:Status], COUNT([Audit Plan Item].[Resource ID]) "
           "FROM [Audit Plan Item] GROUP BY [Audit Plan Item].[IAM-PlanItem-FG:Status]")
    columns = ["IAM-PlanItem-FG:Status", "Count_Resource ID"]
    rows = [[1, 3], [4, 28]]
    c._label_enums(sql, ["", ""], columns, rows)
    assert rows == [["Planned", 3], ["Completed", 28]]


def test_an_installation_that_stores_the_words_is_left_alone():
    c = client_with(ISSUE)
    sql = "SELECT [SOXIssue].[OPSS-Iss:Status] FROM [SOXIssue]"
    rows = [["Open"], ["Closed"]]
    c._label_enums(sql, [""], ["OPSS-Iss:Status"], rows)
    assert rows == [["Open"], ["Closed"]]


def test_a_value_the_definition_does_not_mention_is_left_as_it_is():
    # Enum values get retired; a row still holding one must not come back blank.
    c = client_with(PLAN_ITEM)
    sql = "SELECT [Audit Plan Item].[IAM-PlanItem-FG:Status] FROM [Audit Plan Item]"
    rows = [[9], [None], [1]]
    c._label_enums(sql, [""], ["IAM-PlanItem-FG:Status"], rows)
    assert rows == [[9], [None], ["Planned"]]


def test_a_count_column_is_never_relabelled():
    c = client_with(PLAN_ITEM)
    sql = ("SELECT COUNT([Audit Plan Item].[Resource ID]), [Audit Plan Item].[IAM-PlanItem-FG:Status] "
           "FROM [Audit Plan Item] GROUP BY [Audit Plan Item].[IAM-PlanItem-FG:Status]")
    rows = [[1, 1], [4, 4]]
    c._label_enums(sql, ["", ""], ["Count_Resource ID", "IAM-PlanItem-FG:Status"], rows)
    assert rows == [[1, "Planned"], [4, "Completed"]]


def test_a_field_that_two_types_share_is_labelled_on_the_right_one():
    c = client_with(PLAN_ITEM, ISSUE)
    sql = ("SELECT [SOXIssue].[OPSS-Iss:Status], [Audit Plan Item].[IAM-PlanItem-FG:Status] "
           "FROM [SOXIssue] JOIN [Audit Plan Item] ON PARENT([SOXIssue])")
    rows = [["Open", 1]]
    c._label_enums(sql, ["", ""], ["OPSS-Iss:Status", "IAM-PlanItem-FG:Status"], rows)
    assert rows == [["Open", "Planned"]]


# ---------- Filters on a coded enum ----------

class FakeSource:
    """Just enough of a DataSource for the two helpers that translate filter values."""
    is_openpages = True

    def __init__(self, client):
        self.client = client


def test_a_filter_offers_the_words_and_sends_back_the_code():
    from app.datasources import openpages_labels, openpages_stored
    source = FakeSource(client_with(PLAN_ITEM))
    labels = openpages_labels(source, "Audit Plan Item", "IAM-PlanItem-FG:Status")
    assert labels == {"Planned": "1", "Completed": "4"}
    assert openpages_stored(source, "Audit Plan Item", "IAM-PlanItem-FG:Status", "Completed") == "4"


def test_a_value_with_no_code_behind_it_goes_through_unchanged():
    from app.datasources import openpages_stored
    source = FakeSource(client_with(ISSUE))
    assert openpages_stored(source, "SOXIssue", "OPSS-Iss:Status", "Open") == "Open"
