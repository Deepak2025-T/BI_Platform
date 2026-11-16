"""
Asking the few questions a request leaves open, before a report is built from it.

No AI model is involved, so every answer here can be checked exactly: the test is that a request
which already says something is never asked about it again, and that the questions name the values
the database really holds.
"""

import sqlite3
import uuid

import pytest

from app.database import SessionLocal
from app.datasources import get_source
from app.prompt_clarify import apply_style, clarify, colour_for_values


@pytest.fixture(scope="module")
def grc(tmp_path_factory) -> str:
    path = (tmp_path_factory.mktemp("clarify") / "grc.db").as_posix()
    con = sqlite3.connect(path)
    con.executescript("""
        CREATE TABLE risk (id INTEGER PRIMARY KEY, risk_status TEXT, owner_name TEXT, exposure REAL);
        CREATE TABLE control (id INTEGER PRIMARY KEY, effectiveness TEXT);
        INSERT INTO risk (risk_status, owner_name, exposure) VALUES
            ('Open', 'Asha', 10), ('Closed', 'Ben', 20), ('Draft', 'Cara', 30);
        INSERT INTO control (effectiveness) VALUES ('Effective'), ('Partial');
    """)
    con.commit()
    con.close()
    return path


@pytest.fixture(scope="module")
def source(client, manager, grc):
    c = client.post("/api/connections", headers=manager, json={
        "name": f"Clarify {uuid.uuid4().hex[:6]}", "db_type": "sqlite", "database": grc}).json()
    client.put(f"/api/connections/{c['id']}", headers=manager,
               json={"allowed_tables": ["main.risk", "main.control"]})
    db = SessionLocal()
    try:
        yield get_source(db, c["id"]), c["id"]
    finally:
        db.close()
        client.delete(f"/api/connections/{c['id']}", headers=manager)


def ids(result) -> list[str]:
    return [q["id"] for q in result["questions"]]


# ---------------------------------------------------------------- the two scenarios

def test_a_bare_request_is_asked_the_three_open_questions(source):
    """"Build a Risk Status Chart" says what it is about and nothing else."""
    src, _ = source
    result = clarify(src, "Build a Risk Status Chart")

    assert ids(result) == ["chart_type", "measure", "colours"]
    assert result["subject"]["table"] == "main.risk"
    assert result["subject"]["column"] == "risk_status"
    # The colour question offers the statuses the table really holds, not invented ones.
    assert result["questions"][2]["options"][0]["adds"].count(" - ") == 3
    assert "Open - Orange" in result["questions"][2]["options"][0]["adds"]


def test_a_request_that_says_everything_is_asked_nothing(source):
    """The shape, the measure and the colours are all in the sentence, so the build starts."""
    src, _ = source
    result = clarify(src, "Build a Risk Status Pie Chart showing record counts. "
                          "Open - Orange, Closed - Green, Draft - Blue.")
    assert result["questions"] == []


# ---------------------------------------------------------------- only what is still open

def test_naming_the_shape_leaves_only_the_rest(source):
    src, _ = source
    assert ids(clarify(src, "Build a Risk Status donut")) == ["measure", "colours"]


def test_choosing_shapes_in_more_options_counts_as_naming_them(source):
    """A shape picked in the form is as decided as one written in the sentence."""
    src, _ = source
    result = clarify(src, "Build a Risk Status report", {"charts": ["bar"]})
    assert "chart_type" not in ids(result)


def test_saying_how_many_leaves_the_measure_alone(source):
    src, _ = source
    assert "measure" not in ids(clarify(src, "How many risks there are by risk status"))


def test_colours_are_not_asked_about_twice(source):
    """Colours written into the request are already the answer."""
    src, _ = source
    assert "colours" not in ids(clarify(src, "Risk status report, Open - Orange, Closed - Green"))


def test_a_column_with_no_short_list_of_values_is_not_offered_colours(source):
    """One name per row is not a status, so there is nothing worth colouring by hand."""
    src, _ = source
    result = clarify(src, "Risks by owner name")
    assert result["subject"]["column"] == "owner_name"
    assert "colours" not in ids(result)


def test_a_request_about_nothing_in_the_database_is_asked_what_it_covers(source):
    src, _ = source
    result = clarify(src, "Build me a report")
    assert result["subject"] is None
    assert ids(result)[0] == "subject"
    assert {o["label"] for o in result["questions"][0]["options"]} == {"risk", "control"}


def test_never_more_than_four_questions(source):
    src, _ = source
    for prompt in ("Build me a report", "Build a Risk Status Chart", "risk", "control effectiveness"):
        assert len(clarify(src, prompt)["questions"]) <= 4


def test_every_option_can_be_turned_into_a_request(source):
    """The person sees what their answers add before anything is built, so each option has to
    carry its own words, its own shapes and its own look - and nothing else."""
    src, _ = source
    for question in clarify(src, "Build a Risk Status Chart")["questions"]:
        assert question["options"], question["id"]
        for option in question["options"]:
            assert set(option) == {"id", "label", "hint", "adds", "charts", "style"}
            assert isinstance(option["adds"], str)
            assert all(c in ("kpi", "bar", "line", "area", "pie", "table") for c in option["charts"])


# ---------------------------------------------------------------- colours

def test_a_status_keeps_the_colour_people_reach_for():
    assert colour_for_values(["Open", "Closed", "Draft"]) == [
        ("Open", "orange"), ("Closed", "green"), ("Draft", "blue")]


def test_a_rating_scale_reads_as_traffic_lights():
    by_value = dict(colour_for_values(["Minor", "Moderate", "Significant", "Major"]))
    assert by_value["Minor"] == "green"
    assert by_value["Moderate"] == "yellow"
    assert by_value["Major"] == "red"


def test_values_nobody_named_still_get_a_colour_each():
    colours = [c for _, c in colour_for_values(["Alpha", "Beta", "Gamma", "Delta"])]
    assert len(set(colours)) == 4


# ---------------------------------------------------------------- applying the look

def test_a_donut_is_a_pie_until_the_look_is_applied():
    widgets = [{"chart": {"type": "pie", "x": "s", "y": ["n"]}},
               {"chart": {"type": "bar", "x": "s", "y": ["n"]}}]
    apply_style(widgets, {"donut": True, "ringLegend": True})
    assert widgets[0]["chart"]["type"] == "donut"
    assert widgets[0]["style"]["ringLegend"] is True
    # A ring legend means nothing on a bar chart, so it is not put there.
    assert widgets[1]["chart"]["type"] == "bar"
    assert "style" not in widgets[1]


def test_bars_on_their_side_only_reach_bar_charts():
    widgets = [{"chart": {"type": "bar", "x": "s", "y": ["n"]}},
               {"chart": {"type": "line", "x": "s", "y": ["n"]}},
               {"chart": {"type": "kpi", "x": "", "y": ["n"]}}]
    apply_style(widgets, {"horizontal": True, "showValues": True})
    assert widgets[0]["style"] == {"horizontal": True, "showValues": True}
    assert widgets[1]["style"] == {"showValues": True}
    # A number tile is already nothing but its number.
    assert "style" not in widgets[2]


def test_a_look_already_chosen_is_never_overwritten():
    widgets = [{"chart": {"type": "bar", "x": "s", "y": ["n"]}, "style": {"horizontal": False}}]
    apply_style(widgets, {"horizontal": True})
    assert widgets[0]["style"]["horizontal"] is False


def test_no_look_asked_for_changes_nothing():
    widgets = [{"chart": {"type": "pie", "x": "s", "y": ["n"]}}]
    apply_style(widgets, {})
    apply_style(widgets, None)
    assert widgets == [{"chart": {"type": "pie", "x": "s", "y": ["n"]}}]


# ---------------------------------------------------------------- over HTTP

def test_the_endpoint_answers_without_an_ai_model(client, user, source):
    """No model id is asked for, because none is used: the questions have to arrive instantly."""
    _, source_id = source
    r = client.post("/api/assistant/clarify", headers=user,
                    json={"source_id": source_id, "prompt": "Build a Risk Status Chart"})
    assert r.status_code == 200
    body = r.json()
    assert [q["id"] for q in body["questions"]] == ["chart_type", "measure", "colours"]
    assert body["subject"]["label"] == "risk status"


def test_the_endpoint_needs_signing_in(client, source):
    _, source_id = source
    r = client.post("/api/assistant/clarify", json={"source_id": source_id, "prompt": "anything"})
    assert r.status_code == 401
