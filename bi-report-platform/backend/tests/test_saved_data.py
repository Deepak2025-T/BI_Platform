"""
Opening a report shows the numbers it already has.

A dashboard of forty charts used to run forty queries every time anybody opened it, and the page
filled in one spinner at a time. The report now keeps what it last ran and serves that, so the
charts are there when the page is. The tests below are about where that line falls: what is served
from the saved copy, and what still has to go to the database.
"""

import sqlite3
import uuid

import pytest

from app.database import SessionLocal
from app.models import Report, ReportSnapshot

SQL = "SELECT SUM(amount) AS total FROM sales_log"


def total(answer: dict) -> float:
    return answer["widgets"][0]["rows"][0][0]


def add_sale(path: str, amount: float):
    con = sqlite3.connect(path)
    con.execute("INSERT INTO sales_log (amount) VALUES (?)", (amount,))
    con.commit()
    con.close()


@pytest.fixture
def shop(tmp_path, client, manager):
    path = (tmp_path / f"saved_{uuid.uuid4().hex[:6]}.db").as_posix()
    con = sqlite3.connect(path)
    con.executescript("CREATE TABLE sales_log (id INTEGER PRIMARY KEY, amount REAL);"
                      "INSERT INTO sales_log (amount) VALUES (100), (50);")
    con.commit()
    con.close()
    c = client.post("/api/connections", headers=manager, json={
        "name": f"Saved {uuid.uuid4().hex[:6]}", "db_type": "sqlite", "database": path}).json()
    client.put(f"/api/connections/{c['id']}", headers=manager, json={"allowed_tables": ["main.sales_log"]})
    yield {"path": path, "source_id": c["id"]}
    client.delete(f"/api/connections/{c['id']}", headers=manager)


@pytest.fixture
def dashboard(client, user, shop):
    """One report with one chart. Saving gives the chart an id of its own, so the tests take the
    id from the report rather than assuming the one they sent."""
    widget = {"id": "t1", "title": "Total", "sql": SQL, "chart": {"type": "kpi", "x": "", "y": ["total"]}}
    res = client.post("/api/assistant/save", headers=user, json={
        "source_id": shop["source_id"], "title": "Shop total", "widgets": [widget]})
    assert res.status_code == 201, res.text
    report = res.json()
    return {**report, "wid": report["config"]["widgets"][0]["id"]}


def open_report(client, headers, report_id, refresh=False, filters=None):
    res = client.post(f"/api/reports/{report_id}/data", headers=headers,
                      json={"filters": filters or {}, "refresh": refresh})
    assert res.status_code == 200, res.text
    return res.json()


# ---------- What is served from the saved copy ----------

def test_a_report_keeps_its_numbers_when_it_is_saved(client, user, dashboard):
    """The first person to open a report should not be the one who pays for it. The queries ran
    to build it, so what they produced is kept with it."""
    with SessionLocal() as db:
        snaps = db.query(ReportSnapshot).filter(ReportSnapshot.report_id == dashboard["id"]).all()
    assert len(snaps) == 1 and snaps[0].trigger == "open"
    assert snaps[0].data["widgets"][0]["rows"] == [[150]]


def test_opening_it_serves_those_numbers_instead_of_querying_again(client, user, dashboard, shop):
    """The point of the whole change: the database is not asked again, which is why the charts
    are there at once. Proved by changing the database underneath and seeing the report unmoved."""
    add_sale(shop["path"], 25)
    answer = open_report(client, user, dashboard["id"])
    assert total(answer) == 150, "a second open must not re-run the query"
    assert answer["snapshot_at"], "and must say the numbers are the saved ones"


def test_refresh_runs_the_queries_and_replaces_what_was_saved(client, user, dashboard, shop):
    add_sale(shop["path"], 25)
    assert total(open_report(client, user, dashboard["id"], refresh=True)) == 175
    # ...and the next person to open it gets the new numbers, not the ones from before.
    assert total(open_report(client, user, dashboard["id"])) == 175


def test_editing_a_chart_throws_the_saved_numbers_away(client, user, dashboard, shop):
    """A saved copy of a question nobody is asking any more is worse than no saved copy: it would
    answer the new chart with the old chart's numbers."""
    add_sale(shop["path"], 25)
    config = {**dashboard["config"],
              "widgets": [{**dashboard["config"]["widgets"][0], "sql": "SELECT COUNT(*) AS total FROM sales_log"}]}
    client.put(f"/api/reports/{dashboard['id']}", headers=user, json={"config": config})
    answer = open_report(client, user, dashboard["id"])
    assert total(answer) == 3, "the edited chart counts rows, and there are three now"
    assert answer["snapshot_at"] is None, "it was run just now, so it is not saved data"
    # Having run it, the report keeps it: the next open is served again.
    assert open_report(client, user, dashboard["id"])["snapshot_at"]


def test_a_chart_added_later_is_run_and_then_kept(client, user, dashboard):
    config = {**dashboard["config"], "widgets": dashboard["config"]["widgets"] + [
        {"id": "t2", "title": "Rows", "sql": "SELECT COUNT(*) AS n FROM sales_log",
         "chart": {"type": "kpi", "x": "", "y": ["n"]}}]}
    client.put(f"/api/reports/{dashboard['id']}", headers=user, json={"config": config})
    both = [dashboard["wid"], "t2"]
    assert [w["id"] for w in open_report(client, user, dashboard["id"])["widgets"]] == both
    assert [w["id"] for w in open_report(client, user, dashboard["id"])["widgets"]] == both


# ---------- What still goes to the database ----------

def test_a_filtered_view_always_runs_live(client, user, dashboard, shop):
    """A filter is one person's own question, not the picture everybody shares, so it is never
    answered from the copy and never overwrites it."""
    wid = dashboard["wid"]
    filters = [{"id": "f1", "label": "Amount", "kind": "category",
                "columns": {wid: {"table": "main.sales_log", "column": "amount"}}}]
    client.put(f"/api/reports/{dashboard['id']}", headers=user,
               json={"config": {**dashboard["config"], "filters": filters}})
    add_sale(shop["path"], 25)
    answer = open_report(client, user, dashboard["id"], filters={"f1": {"values": ["100"]}})
    assert answer["snapshot_at"] is None, "a filtered view is run, never served from the copy"
    assert total(answer) == 100, "only the sale of 100"
    # The shared copy is untouched by somebody else's filter: still the numbers from before.
    assert total(open_report(client, user, dashboard["id"])) == 150


def test_a_run_where_nothing_worked_is_not_kept(client, user, manager, dashboard, shop):
    """A database that was briefly unreachable must not leave the report showing errors for good."""
    config = {**dashboard["config"],
              "widgets": [{**dashboard["config"]["widgets"][0], "sql": "SELECT total FROM missing_table"}]}
    client.put(f"/api/reports/{dashboard['id']}", headers=user, json={"config": config})
    answer = open_report(client, user, dashboard["id"])
    assert answer["widgets"][0]["ok"] is False
    with SessionLocal() as db:
        kept = db.query(ReportSnapshot).filter(ReportSnapshot.report_id == dashboard["id"]).all()
    assert all(s.data["widgets"][0].get("ok") for s in kept), "errors are shown, never saved"


# ---------- Share links ----------

def test_a_share_link_is_served_the_same_saved_numbers(client, user, dashboard, shop):
    client.post(f"/api/reports/{dashboard['id']}/publish", headers=user, json={})
    share = client.post(f"/api/reports/{dashboard['id']}/share", headers=user, json={})
    assert share.status_code == 201, share.text
    token = share.json()["token"]
    add_sale(shop["path"], 25)
    res = client.post(f"/api/public/reports/{token}/data", json={"filters": {}})
    assert res.status_code == 200, res.text
    assert total(res.json()) == 150 and res.json()["snapshot_at"]
    assert res.json()["source"] == "", "a visitor is never told which database it reads"


# ---------- The refresh history stays about refreshes ----------

def test_opening_a_report_does_not_put_a_point_on_its_history(client, user, dashboard, shop):
    """Otherwise every open after an edit would look like a change in the numbers."""
    # Turning the schedule on refreshes once, which is the first point.
    client.put(f"/api/reports/{dashboard['id']}/schedule", headers=user,
               json={"every": "daily", "history_days": 90})
    add_sale(shop["path"], 25)
    open_report(client, user, dashboard["id"], refresh=True)
    for _ in range(3):
        open_report(client, user, dashboard["id"])
    points = client.get(f"/api/reports/{dashboard['id']}/history", headers=user).json()["widgets"]
    assert [p["value"] for p in points[dashboard["wid"]]] == [150, 175], \
        "two refreshes, two points - the three opens in between are not measurements"


def test_the_saved_copy_belongs_to_one_report_only(client, user, dashboard, shop):
    """A sanity check on the lookup: snapshots are found by report id, and a second report on the
    same database must not be served the first one's numbers."""
    widget = {"id": "t1", "title": "Rows", "sql": "SELECT COUNT(*) AS total FROM sales_log",
              "chart": {"type": "kpi", "x": "", "y": ["total"]}}
    other = client.post("/api/assistant/save", headers=user, json={
        "source_id": shop["source_id"], "title": "Row count", "widgets": [widget]}).json()
    try:
        assert total(open_report(client, user, other["id"])) == 2
        assert total(open_report(client, user, dashboard["id"])) == 150
    finally:
        with SessionLocal() as db:
            db.delete(db.get(Report, other["id"]))
            db.commit()
