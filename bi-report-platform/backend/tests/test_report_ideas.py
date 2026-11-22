"""
What the Build page recommends when a database is chosen.

Nothing here involves an AI model: a recommendation is worked out from the connection's own
tables or object types and from the person's own past requests, so every test can check exactly
why a suggestion appeared and exactly what it would build.
"""

import sqlite3
import uuid

import pytest

from app.database import SessionLocal
from app.datasources import DataSource, get_source
from app.models import Report, User
from app.report_ideas import MAX_IDEAS, Recipe, _affinity, _title_of, recommend


@pytest.fixture(scope="module")
def shop(tmp_path_factory) -> str:
    path = (tmp_path_factory.mktemp("recs") / "shop.db").as_posix()
    con = sqlite3.connect(path)
    con.executescript("""
        CREATE TABLE orders (id INTEGER PRIMARY KEY, region TEXT, status TEXT,
                             revenue REAL, order_date DATE);
        CREATE TABLE people (id INTEGER PRIMARY KEY, full_name TEXT, department TEXT);
        INSERT INTO orders (region, status, revenue, order_date)
            VALUES ('North', 'paid', 100, '2024-01-15');
        INSERT INTO people (full_name, department) VALUES ('Asha', 'Sales');
    """)
    con.commit()
    con.close()
    return path


@pytest.fixture(scope="module")
def source(client, manager, shop):
    c = client.post("/api/connections", headers=manager, json={
        "name": f"Shop {uuid.uuid4().hex[:6]}", "db_type": "sqlite", "database": shop}).json()
    client.put(f"/api/connections/{c['id']}", headers=manager,
               json={"allowed_tables": ["main.orders", "main.people"]})
    db = SessionLocal()
    try:
        yield get_source(db, c["id"]), c["id"]
    finally:
        db.close()
        client.delete(f"/api/connections/{c['id']}", headers=manager)


def _user(db, email="user@example.com") -> User:
    return db.query(User).filter(User.email == email).one()


def _openpages(types: list[str]) -> DataSource:
    """An OpenPages connection sharing exactly these object types, and nothing else."""
    return DataSource(id=9001, name="GRC", db_type="openpages", version="v1",
                      tables=[f"openpages.{t}" for t in types])


def _recommend(source_id, *, email="user@example.com", src=None):
    db = SessionLocal()
    try:
        return recommend(db, _user(db, email), src or get_source(db, source_id))
    finally:
        db.close()


# ---------- What the connection can carry ----------

def test_a_connection_nobody_has_used_still_recommends_something(source):
    """The point of the panel: a database chosen for the first time is not a blank box."""
    _, source_id = source
    ideas = _recommend(source_id)
    assert ideas, "a table with a number, a date and something to group by should suggest a report"
    assert all(i["prompt"] and i["title"] and i["why"] for i in ideas)


def test_a_recommendation_names_columns_the_table_really_has(source):
    _, source_id = source
    # Only the suggestions worked out from the connection: a card offering back something this
    # person asked for earlier is their own wording, not ours to make claims about.
    subjects = [i for i in _recommend(source_id) if i["reason"] == "subject"]
    orders = next(i for i in subjects if "orders" in i["title"].lower())
    assert "revenue" in orders["prompt"] and "region" in orders["prompt"]
    assert "full name" not in orders["prompt"], "a free-text column makes a useless grouping"


def test_a_table_with_a_date_and_an_amount_gets_a_kpi_scorecard(source):
    """The common KPIs - this month against last, year to date, the trend - on real columns."""
    _, source_id = source
    ideas = _recommend(source_id)
    card = next(i for i in ideas if i["reason"] == "kpi")
    assert card["title"] == "Orders KPI scorecard" and "[orders]" in card["prompt"]
    assert "revenue" in card["prompt"] and "order date" in card["prompt"] and card["kpis"]
    # People has no amount and no date, so it gets no scorecard.
    assert not any(i["reason"] == "kpi" and "people" in i["title"].lower() for i in ideas)
    subject = next(i for i in ideas if i["reason"] == "subject")
    assert subject["kpis"], "a subject card says what it measures"


def test_an_openpages_connection_is_only_asked_about_what_it_shares():
    """A suggestion about vendors on a connection with no vendors is noise, and worse, it would
    fail every chart in it."""
    ideas = _recommend(None, src=_openpages(["SOXRisk", "SOXControl"]))
    subjects = {i["subject"] for i in ideas}
    assert {"risk", "control"} <= subjects
    assert not {"vendor", "policy", "loss event"} & subjects


def test_an_openpages_recommendation_asks_for_a_whole_report():
    risk = next(i for i in _recommend(None, src=_openpages(["SOXRisk"])) if i["subject"] == "risk")
    assert "[SOXRisk]" in risk["prompt"], "the request should name the object type it was built from"
    assert risk["charts"] >= 8, "a subject report is KPI cards plus breakdowns, not one chart"
    assert "residual" in risk["prompt"] and "status" in risk["prompt"]


def test_a_wide_connection_is_also_offered_one_page_across_subjects():
    ideas = _recommend(None, src=_openpages(["SOXRisk", "SOXControl", "SOXIssue", "ActionItem"]))
    breadth = [i for i in ideas if i["reason"] == "breadth"]
    assert breadth, "four subjects on one connection is worth an overview across them"
    assert "tab for each subject" in breadth[0]["prompt"]


def test_a_connection_with_one_subject_is_not_offered_an_overview_of_it():
    assert not [i for i in _recommend(None, src=_openpages(["SOXRisk"])) if i["reason"] == "breadth"]


def test_there_are_never_more_than_a_handful():
    ideas = _recommend(None, src=_openpages(["SOXRisk", "SOXControl", "SOXIssue", "ActionItem",
                                             "LossEvent", "KeyRiskIndicator", "SOXProcess", "Policy"]))
    assert len(ideas) <= MAX_IDEAS


# ---------- What the person asked for before ----------

def test_a_subject_asked_about_but_never_built_comes_first(client, user, source):
    """The most useful thing to recommend is the report someone keeps asking questions around
    and has not built yet."""
    _, source_id = source
    chat = client.post("/api/chats", headers=user,
                       json={"source_id": source_id, "title": "Looking at people"}).json()
    db = SessionLocal()
    try:
        from app.models import ChatMessage
        for _ in range(3):
            db.add(ChatMessage(conversation_id=chat["id"], status="ok",
                               question="how many people are in each department"))
        db.commit()
    finally:
        db.close()
    try:
        subjects = [i for i in _recommend(source_id) if i["reason"] == "subject"]
        assert subjects[0]["subject"] == "people", f"asked about three times, never built: {subjects}"
        assert "3 times" in subjects[0]["why"]
    finally:
        client.delete(f"/api/chats/{chat['id']}", headers=user)


def test_a_report_already_built_is_offered_back_as_itself(client, user, source):
    """What someone built before is the strongest signal there is, so it is offered as a card of
    its own rather than as a subject suggestion they would have to retype."""
    _, source_id = source
    res = client.post("/api/reports", headers=user, json={
        "title": "Orders", "prompt": "Build an orders overview with 4 KPIs and 6 charts by region",
        "config": {"kind": "dashboard", "source_id": source_id, "widgets": []}})
    assert res.status_code == 201, res.text
    try:
        ideas = _recommend(source_id)
        mine = [i for i in ideas if i["reason"] == "history"]
        assert mine, f"a report built on this connection should come back as a card: {ideas}"
        assert mine[0]["prompt"].startswith("Build an orders overview")
        assert mine[0]["title"] == "Orders overview with 4 KPIs and 6 charts by region"
        assert mine[0]["charts"] == 10, "4 KPIs and 6 charts"
    finally:
        client.delete(f"/api/reports/{res.json()['id']}", headers=user)


def test_another_persons_reports_are_never_read(client, user, manager, source):
    """A recommendation has to be about your own work. Someone else's prompt leaking into your
    suggestions would also leak what they are working on."""
    _, source_id = source
    res = client.post("/api/reports", headers=manager, json={
        "title": "Secret", "prompt": "Build a confidential payroll overview by department",
        "config": {"kind": "dashboard", "source_id": source_id, "widgets": []}})
    try:
        assert not any("payroll" in i["prompt"].lower() for i in _recommend(source_id))
    finally:
        client.delete(f"/api/reports/{res.json()['id']}", headers=manager)


def test_a_request_about_another_connection_does_not_count(source):
    """Past requests are per connection: what you asked of the sales database says nothing about
    what to build on the risk one."""
    _, source_id = source
    db = SessionLocal()
    try:
        user = _user(db)
        r = Report(title="Elsewhere", prompt="Build a risks overview with ratings and domains",
                   config={"kind": "dashboard", "source_id": source_id + 500, "widgets": []},
                   owner_id=user.id)
        db.add(r)
        db.commit()
        rid = r.id
    finally:
        db.close()
    try:
        assert not any(i["reason"] == "history" and "risks overview" in i["prompt"]
                       for i in _recommend(source_id))
    finally:
        db = SessionLocal()
        db.delete(db.get(Report, rid))
        db.commit()
        db.close()


def test_recent_asks_count_for_more_than_old_ones():
    recipe = Recipe(subject="risk", title="Risks", words=("risk",), kpis=(), charts=())
    just_asked, _ = _affinity(["about risk"] + ["something else"] * 10, recipe)
    asked_long_ago, _ = _affinity(["something else"] * 10 + ["about risk"], recipe)
    assert just_asked > asked_long_ago
    assert _affinity(["nothing of the sort"], recipe) == (0.0, 0)


def test_a_card_is_named_after_the_request_not_the_whole_paragraph():
    long = ("Please build a control effectiveness dashboard. It should have eight KPI cards and "
            "twelve charts covering everything.")
    assert _title_of(long) == "Control effectiveness dashboard"
    assert len(_title_of("x" * 400)) <= 61


# ---------- The endpoint ----------

def test_the_endpoint_answers_without_a_model(client, user, source):
    _, source_id = source
    res = client.get("/api/assistant/report-ideas", headers=user, params={"source_id": source_id})
    assert res.status_code == 200, res.text
    ideas = res.json()["ideas"]
    assert ideas and all({"id", "title", "why", "reason", "prompt", "charts"} <= set(i) for i in ideas)


def test_signing_in_is_required(client, source):
    _, source_id = source
    assert client.get("/api/assistant/report-ideas", params={"source_id": source_id}).status_code == 401
