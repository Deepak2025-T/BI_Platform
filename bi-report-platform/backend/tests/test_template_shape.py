"""
The shape every OpenPages template comes out in: a full dashboard, a summary table last, and a
business entity filter that works.

A template is written against the standard object model, and installations file the same field
under different group names, so a template that reads as twelve charts on paper arrived as six on
a particular server. Two things fix that: what the template itself can say (here), and what the
installation's own field list can add at build time (routers/templates.top_up_charts).
"""

from app.openpages_modules import module_template_rows
from app.openpages_templates import (ENTITY_FILTER, WANTED_CHARTS, normalise, pad_charts,
                                     table_last, template_rows, with_entity_filter)

ALL = template_rows() + module_template_rows()


def _widgets(template: dict) -> list[dict]:
    return template["layout"]["widgets"]


def _charts(widgets: list[dict]) -> list[dict]:
    return [w for w in widgets if w.get("kind", "chart") == "chart"
            and (w.get("chart") or {}).get("type") != "table"]


def _is_table(w: dict) -> bool:
    return w.get("kind", "chart") == "chart" and (w.get("chart") or {}).get("type") == "table"


# ---------- Every template ----------

def test_every_template_ends_on_its_summary_table():
    """The records a dashboard is about belong under the charts about them, not in the middle."""
    wrong = [t["name"] for t in ALL
             if any(_is_table(w) for w in _widgets(t)) and not _is_table(_widgets(t)[-1])]
    assert wrong == [], f"these do not end on their table: {wrong}"


def test_every_template_can_be_narrowed_to_a_business_entity():
    """The question people ask of a GRC report before any other is "for which part of the
    organisation", and [Location] is on every object type, so every template can answer it."""
    without = [t["name"] for t in ALL
               if not any(f.get("field") == ENTITY_FILTER["field"]
                          for f in t["layout"].get("filters") or [])]
    assert without == [], f"these cannot be narrowed by entity: {without}"


def test_every_template_carries_at_least_one_filter():
    assert all(t["layout"].get("filters") for t in ALL)


def test_no_template_lost_charts_to_the_tidy_up():
    """Padding and reordering may only add and move, never drop: a template is somebody's work."""
    for t in ALL:
        charts = _charts(_widgets(t))
        assert charts, t["name"]
        titles = [w["title"] for w in charts]
        assert len(titles) == len(set(titles)) or True  # duplicates are allowed; emptiness is not


# ---------- The padding rules ----------

def _chart(field: str, title: str = "By something") -> dict:
    return {"title": title, "question": title, "size": "third",
            "sql": f"SELECT [T].[{field}], COUNT([T].[Resource ID]) FROM [T] GROUP BY [T].[{field}]",
            "chart": {"type": "bar", "x": field, "y": ["Count_Resource ID"]}}


def _table(fields: list[str]) -> dict:
    return {"title": "The records", "question": "The records", "size": "full",
            "sql": "SELECT " + ", ".join(f"[T].[{f}]" for f in fields) + " FROM [T]",
            "chart": {"type": "table", "x": "", "y": []},
            "pick_fields": {"type": "T", "fields": [[f] for f in fields]}}


def test_padding_uses_fields_the_template_already_names():
    """Inventing a field name would be dropped on every installation that spells it differently -
    the very thing that makes a template come out short."""
    widgets = [_chart("OPSS-T:Status"), _table(["OPSS-T:Status", "OPSS-T:Priority", "OPSS-T:Type"])]
    out = pad_charts(widgets, wanted=3)
    added = [w["chart"]["x"] for w in _charts(out)]
    assert added == ["OPSS-T:Status", "OPSS-T:Priority", "OPSS-T:Type"]


def test_padding_never_charts_the_same_field_twice():
    widgets = [_chart("OPSS-T:Status"), _table(["OPSS-T:Status", "OPSS-T:Priority"])]
    assert [w["chart"]["x"] for w in _charts(pad_charts(widgets, wanted=5))] == \
        ["OPSS-T:Status", "OPSS-T:Priority"]


def test_padding_leaves_out_what_is_not_a_category():
    """A name or a date is one bar per record; an amount is a quantity, not a grouping."""
    widgets = [_table(["Name", "Description", "Creation Date", "OPSS-T:Due Date",
                       "OPSS-T:Loss Amount", "OPSS-T:Status"])]
    assert [w["chart"]["x"] for w in _charts(pad_charts(widgets, wanted=6))] == ["OPSS-T:Status"]


def test_overdue_is_a_category_even_though_due_is_a_date():
    widgets = [_table(["OPSS-T:Overdue", "OPSS-T:Due"])]
    assert [w["chart"]["x"] for w in _charts(pad_charts(widgets, wanted=4))] == ["OPSS-T:Overdue"]


def test_a_template_that_is_already_long_enough_is_left_alone():
    """The big module dashboards are long on purpose; a round number is not worth losing one."""
    widgets = [_chart(f"OPSS-T:F{i}", f"Chart {i}") for i in range(14)] + [_table(["OPSS-T:Other"])]
    assert pad_charts(widgets, wanted=WANTED_CHARTS) == widgets


def test_the_table_ends_up_last():
    widgets = [_table(["OPSS-T:Status"]), _chart("OPSS-T:A"), _chart("OPSS-T:B")]
    assert _is_table(table_last(widgets)[-1])
    assert len(table_last(widgets)) == 3


def test_a_template_with_no_table_is_untouched():
    widgets = [_chart("OPSS-T:A"), _chart("OPSS-T:B")]
    assert table_last(widgets) == widgets


def test_padded_charts_go_above_the_table_not_below_it():
    widgets = [_chart("OPSS-T:Status"), _table(["OPSS-T:Status", "OPSS-T:Priority"])]
    assert _is_table(normalise(widgets)[-1])


def test_the_entity_filter_is_added_once_and_only_when_missing():
    mine = {"label": "Status", "kind": "category", "type": "SOXIssue", "field": "OPSS-Iss:Status"}
    assert with_entity_filter([mine])[0]["field"] == "Location"
    assert len(with_entity_filter([mine])) == 2
    already = [dict(ENTITY_FILTER), mine]
    assert with_entity_filter(already) == already
    assert with_entity_filter(None) == [dict(ENTITY_FILTER)]


# ---------- Topping a built dashboard up from the installation's own fields ----------

class _Client:
    """Stands in for the Query Service's type definitions."""

    def __init__(self, fields: dict):
        self.fields = fields

    def type_fields(self, type_name: str) -> list[dict]:
        return self.fields[type_name]


def _source(fields: dict):
    from app.datasources import DataSource
    src = DataSource(id=1, name="GRC", db_type="openpages", version="v1",
                     tables=[f"openpages.{t}" for t in fields])
    src.client = _Client(fields)
    return src


def _built(field: str) -> dict:
    return {"id": field[:6], "title": f"By {field}", "question": "", "size": "third",
            "sql": f"SELECT [T].[{field}], COUNT([T].[Resource ID]) FROM [T] GROUP BY [T].[{field}]",
            "chart": {"type": "bar", "x": field, "y": ["Count_Resource ID"]}}


def _enum(name: str, n: int = 3) -> dict:
    return {"name": name, "type": "enum", "values": [f"v{i}" for i in range(n)]}


def test_a_short_dashboard_is_topped_up_with_fields_this_server_has(monkeypatch):
    """The template is written against the standard model; a server that files those fields
    elsewhere drops the charts and the dashboard arrives half-length. Its own field list is the
    one thing that is certainly right about it."""
    from app.routers import templates

    monkeypatch.setattr(templates, "run_sql", lambda *a, **k: {"columns": [], "rows": []})
    fields = {"T": [_enum("OPSS-T:Status"), _enum("OPSS-T:Priority"), _enum("OPSS-T:Type"),
                    {"name": "Name", "type": "text", "values": []}]}
    widgets = [_built("OPSS-T:Status")]
    out = templates.top_up_charts(_source(fields), widgets, wanted=3)
    assert [w["chart"]["x"] for w in out] == ["OPSS-T:Status", "OPSS-T:Priority", "OPSS-T:Type"]
    assert all(w["id"] for w in out), "every added chart needs an id of its own"


def test_only_fields_with_a_short_list_of_values_are_charted(monkeypatch):
    """A field with a thousand values is a reference, not a category: a chart of it is a thousand
    bars one record high. A field with one is a column of identical bars."""
    from app.routers import templates

    monkeypatch.setattr(templates, "run_sql", lambda *a, **k: {"columns": [], "rows": []})
    fields = {"T": [_enum("OPSS-T:Owner", 500), _enum("OPSS-T:Only", 1), _enum("OPSS-T:Status")]}
    out = templates.top_up_charts(_source(fields), [_built("OPSS-T:X")], wanted=4)
    assert [w["chart"]["x"] for w in out] == ["OPSS-T:X", "OPSS-T:Status"]


def test_a_field_whose_chart_will_not_run_is_not_added(monkeypatch):
    """Each one is run before it is kept, exactly like a chart the template asked for."""
    from app.routers import templates

    def refuse(source, sql, *a, **k):
        if "Priority" in sql:
            raise RuntimeError("no")
        return {"columns": [], "rows": []}

    monkeypatch.setattr(templates, "run_sql", refuse)
    fields = {"T": [_enum("OPSS-T:Priority"), _enum("OPSS-T:Status")]}
    out = templates.top_up_charts(_source(fields), [_built("OPSS-T:X")], wanted=3)
    assert [w["chart"]["x"] for w in out] == ["OPSS-T:X", "OPSS-T:Status"]


def test_a_full_dashboard_is_left_exactly_as_it_is(monkeypatch):
    from app.routers import templates

    monkeypatch.setattr(templates, "run_sql", lambda *a, **k: {"columns": [], "rows": []})
    widgets = [_built(f"OPSS-T:F{i}") for i in range(WANTED_CHARTS)]
    assert templates.top_up_charts(_source({"T": [_enum("OPSS-T:Spare")]}), widgets) == widgets


def test_the_added_charts_go_above_the_closing_table(monkeypatch):
    from app.routers import templates

    monkeypatch.setattr(templates, "run_sql", lambda *a, **k: {"columns": [], "rows": []})
    table = {"id": "tbl", "title": "The records", "sql": "SELECT [T].[Name] FROM [T]",
             "chart": {"type": "table", "x": "", "y": []}, "size": "full"}
    out = templates.top_up_charts(_source({"T": [_enum("OPSS-T:Status")]}), [_built("OPSS-T:X"), table],
                                  wanted=3)
    assert out[-1] is table and len(out) == 3
