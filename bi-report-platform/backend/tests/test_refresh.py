"""Automatic report refresh: schedules, snapshots, and picking up changes in the database."""

import datetime as dt
import sqlite3
import uuid

import pytest
from sqlalchemy import update

from app.database import SessionLocal
from app.models import Report, ReportSnapshot
from app.history import KEEP_SNAPSHOTS
from app.refresh import next_run, run_due

SQL = "SELECT SUM(amount) AS total FROM sales_log"


def total(data: dict) -> float:
    return data["widgets"][0]["rows"][0][0]


@pytest.fixture
def shop(tmp_path, client, manager):
    """A small database that the tests change, with a connection to it."""
    path = (tmp_path / f"shop_{uuid.uuid4().hex[:6]}.db").as_posix()
    con = sqlite3.connect(path)
    con.executescript("CREATE TABLE sales_log (id INTEGER PRIMARY KEY, amount REAL); INSERT INTO sales_log (amount) VALUES (100), (50);")
    con.commit()
    con.close()
    c = client.post("/api/connections", headers=manager, json={"name": f"Shop {uuid.uuid4().hex[:6]}", "db_type": "sqlite", "database": path}).json()
    client.put(f"/api/connections/{c['id']}", headers=manager, json={"allowed_tables": ["main.sales_log"]})
    yield {"path": path, "source_id": c["id"]}
    client.delete(f"/api/connections/{c['id']}", headers=manager)


def add_sale(path: str, amount: float):
    con = sqlite3.connect(path)
    con.execute("INSERT INTO sales_log (amount) VALUES (?)", (amount,))
    con.commit()
    con.close()


@pytest.fixture
def dashboard(client, user, shop):
    widget = {"id": "t1", "title": "Total", "sql": SQL, "chart": {"type": "kpi", "x": "", "y": ["total"]}}
    return client.post("/api/assistant/save", headers=user, json={"source_id": shop["source_id"], "title": "Shop total",
                                                                  "widgets": [widget]}).json()


def data(client, headers, report_id, refresh=False):
    res = client.post(f"/api/reports/{report_id}/data", headers=headers, json={"filters": {}, "refresh": refresh})
    assert res.status_code == 200, res.text
    return res.json()


# ---------- When the next refresh happens ----------

def local(*args) -> dt.datetime:
    return dt.datetime(*args).astimezone()  # server time zone, like next_run


def test_interval_schedules():
    now = dt.datetime(2026, 10, 16, 10, 0, tzinfo=dt.timezone.utc)
    assert next_run("15min", "08:00", 0, now) == now + dt.timedelta(minutes=15)
    assert next_run("hourly", "08:00", 0, now) == now + dt.timedelta(hours=1)
    assert next_run("6hours", "08:00", 0, now) == now + dt.timedelta(hours=6)
    assert next_run("off", "08:00", 0, now) is None


def test_daily_runs_today_or_tomorrow():
    assert next_run("daily", "08:00", 0, local(2026, 10, 16, 7, 0)).astimezone() == local(2026, 10, 16, 8, 0)
    assert next_run("daily", "08:00", 0, local(2026, 10, 16, 8, 0)).astimezone() == local(2026, 10, 17, 8, 0)


def test_weekly_runs_on_the_chosen_day():
    friday = local(2026, 10, 16, 12, 0)  # 16 Oct 2026 is a Friday
    assert next_run("weekly", "09:30", 0, friday).astimezone() == local(2026, 10, 19, 9, 30)  # Monday
    assert next_run("weekly", "13:00", 4, friday).astimezone() == local(2026, 10, 16, 13, 0)  # later today
    assert next_run("weekly", "11:00", 4, friday).astimezone() == local(2026, 10, 23, 11, 0)  # next week


# ---------- Schedules ----------

def test_only_the_owner_or_a_manager_schedules(client, manager, dashboard):
    # A manager's draft isn't visible to others; the user's draft can be scheduled by a manager.
    res = client.put(f"/api/reports/{dashboard['id']}/schedule", headers=manager, json={"every": "daily", "at": "07:30"})
    assert res.status_code == 200
    assert client.put(f"/api/reports/{dashboard['id']}/schedule", headers=manager,
                      json={"every": "daily", "at": "25:00"}).status_code == 422


def test_turning_on_refreshes_once(client, user, dashboard):
    body = client.put(f"/api/reports/{dashboard['id']}/schedule", headers=user, json={"every": "hourly"}).json()
    assert body["report"]["refresh_every"] == "hourly" and body["report"]["next_refresh_at"]
    assert body["report"]["last_refreshed_at"] and body["snapshot"]["data"]["widgets"][0]["rows"] == [[150.0]]


def test_viewers_see_the_snapshot_until_the_next_refresh(client, user, dashboard, shop):
    client.put(f"/api/reports/{dashboard['id']}/schedule", headers=user, json={"every": "daily", "at": "06:00"})
    first = data(client, user, dashboard["id"])
    assert total(first) == 150 and first["snapshot_at"]

    add_sale(shop["path"], 25)
    assert total(data(client, user, dashboard["id"])) == 150  # still the snapshot

    refreshed = data(client, user, dashboard["id"], refresh=True)  # the Refresh button
    assert total(refreshed) == 175 and refreshed["snapshot_at"] >= first["snapshot_at"]
    assert total(data(client, user, dashboard["id"])) == 175  # and everyone now sees it


def test_scheduler_picks_up_database_changes(client, user, dashboard, shop):
    client.put(f"/api/reports/{dashboard['id']}/schedule", headers=user, json={"every": "15min"})
    add_sale(shop["path"], 1000)
    with SessionLocal() as db:
        before = db.get(Report, dashboard["id"]).updated_at
        past = dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=1)
        db.execute(update(Report).where(Report.id == dashboard["id"]).values(next_refresh_at=past, updated_at=Report.updated_at))
        db.commit()

    assert run_due() >= 1
    assert run_due() == 0  # already claimed and moved on: not refreshed twice
    assert total(data(client, user, dashboard["id"])) == 1150

    with SessionLocal() as db:
        r = db.get(Report, dashboard["id"])
        assert r.updated_at == before  # a refresh isn't an edit
        nxt = r.next_refresh_at.replace(tzinfo=dt.timezone.utc) if r.next_refresh_at.tzinfo is None else r.next_refresh_at
        assert nxt > dt.datetime.now(dt.timezone.utc)


def test_editing_charts_refreshes_the_snapshot(client, user, dashboard):
    client.put(f"/api/reports/{dashboard['id']}/schedule", headers=user, json={"every": "daily"})
    config = {**dashboard["config"], "widgets": dashboard["config"]["widgets"] + [
        {"id": "t2", "title": "Count", "sql": "SELECT COUNT(*) AS n FROM sales_log", "chart": {"type": "kpi", "x": "", "y": ["n"]}}]}
    client.put(f"/api/reports/{dashboard['id']}", headers=user, json={"config": config})
    ids = [w["id"] for w in data(client, user, dashboard["id"])["widgets"]]
    assert ids == [dashboard["config"]["widgets"][0]["id"], "t2"]


def test_refresh_now_and_failures_are_recorded(client, user, manager, dashboard, shop):
    client.put(f"/api/reports/{dashboard['id']}/schedule", headers=user, json={"every": "daily"})
    a = client.post(f"/api/reports/{dashboard['id']}/refresh", headers=user).json()
    b = client.post(f"/api/reports/{dashboard['id']}/refresh", headers=user).json()
    assert a["snapshot"]["id"] == b["snapshot"]["id"]  # a second click right away reuses the refresh

    client.delete(f"/api/connections/{shop['source_id']}", headers=manager)
    with SessionLocal() as db:
        db.execute(update(Report).where(Report.id == dashboard["id"]).values(last_refreshed_at=None))
        db.commit()
    res = client.post(f"/api/reports/{dashboard['id']}/refresh", headers=user)
    assert res.status_code == 502 and "no longer exists" in res.json()["detail"]
    assert "no longer exists" in client.get(f"/api/reports/{dashboard['id']}", headers=user).json()["last_refresh_error"]


def test_turning_off_goes_back_to_live_data(client, user, dashboard, shop):
    client.put(f"/api/reports/{dashboard['id']}/schedule", headers=user, json={"every": "daily"})
    off = client.put(f"/api/reports/{dashboard['id']}/schedule", headers=user, json={"every": "off"}).json()
    assert off["report"]["next_refresh_at"] is None
    add_sale(shop["path"], 5)
    live = data(client, user, dashboard["id"], refresh=True)
    assert live["snapshot_at"] is None and total(live) == 155


def test_without_history_only_the_newest_snapshots_are_kept(client, user, dashboard):
    client.put(f"/api/reports/{dashboard['id']}/schedule", headers=user, json={"every": "daily", "history_days": 0})
    for _ in range(KEEP_SNAPSHOTS + 3):
        data(client, user, dashboard["id"], refresh=True)
    with SessionLocal() as db:
        assert db.query(ReportSnapshot).filter(ReportSnapshot.report_id == dashboard["id"]).count() == KEEP_SNAPSHOTS


# ---------- History: summaries, thinning, trends and comparisons ----------

from app.history import thin, widget_summary  # noqa: E402


def test_widget_summaries():
    kpi = {"chart": {"type": "kpi", "x": "", "y": ["total"]}}
    assert widget_summary(kpi, {"ok": True, "columns": ["total"], "rows": [[150]]}) == {"value": 150}
    bar = {"chart": {"type": "bar", "x": "status", "y": ["n"]}}
    assert widget_summary(bar, {"ok": True, "columns": ["status", "n"], "rows": [["Open", 20], [None, 3]]}) == \
        {"values": {"Open": 20, "(blank)": 3}}
    table = {"chart": {"type": "table", "x": "", "y": []}}
    assert widget_summary(table, {"ok": True, "columns": ["name", "status"], "rows": [["a", "Open"], ["b", "x"]]}) is None
    assert widget_summary(kpi, {"ok": False, "error": "boom"}) is None


def test_thinning_keeps_recent_hourly_then_daily(client, user, dashboard):
    now = dt.datetime.now(dt.timezone.utc)
    ages = ([dt.timedelta(minutes=m) for m in range(0, 120, 10)]                  # 12 in the last 2 hours
            + [dt.timedelta(days=3, minutes=m) for m in (0, 10, 20)]               # 3 in one hour, 3 days ago
            + [dt.timedelta(days=12, hours=h) for h in (1, 2, 3)]                  # 3 on one day, 12 days ago
            + [dt.timedelta(days=40)])                                              # older than 30 days
    with SessionLocal() as db:
        report = db.get(Report, dashboard["id"])
        report.history_days = 30
        for age in sorted(ages, reverse=True):
            db.add(ReportSnapshot(report_id=report.id, created_at=now - age, trigger="schedule", data={}))
        db.commit()
        thin(db, report, now)
        db.commit()
        kept = sorted(now - (s.created_at if s.created_at.tzinfo else s.created_at.replace(tzinfo=dt.timezone.utc))
                      for s in db.query(ReportSnapshot).filter(ReportSnapshot.report_id == report.id))
    assert len([a for a in kept if a < dt.timedelta(days=1)]) == 12  # the last day: all of them
    three_days = [a for a in kept if dt.timedelta(days=2) < a < dt.timedelta(days=4)]
    twelve_days = [a for a in kept if dt.timedelta(days=11) < a < dt.timedelta(days=13)]
    assert len(three_days) <= 2 and len(twelve_days) == 1  # one per hour / one per day (hour buckets are local time)
    assert all(a < dt.timedelta(days=30) for a in kept)


def test_history_and_compare(client, user, shop, dashboard):
    rid = dashboard["id"]
    client.put(f"/api/reports/{rid}/schedule", headers=user, json={"every": "daily", "history_days": 90})  # refreshes: 150
    add_sale(shop["path"], 25)
    data(client, user, rid, refresh=True)  # 175
    add_sale(shop["path"], 5)
    data(client, user, rid, refresh=True)  # 180

    h = client.get(f"/api/reports/{rid}/history", headers=user).json()
    assert h["history_days"] == 90
    wid = dashboard["config"]["widgets"][0]["id"]
    assert [p["value"] for p in h["widgets"][wid]] == [150, 175, 180]

    prev = client.get(f"/api/reports/{rid}/history/compare", headers=user).json()
    assert prev["widgets"][0]["rows"] == [[175]]
    oldest = client.get(f"/api/reports/{rid}/history/compare", headers=user, params={"at": "2000-01-01T00:00:00"}).json()
    assert oldest["widgets"][0]["rows"] == [[150]]

    # Editing the chart's query starts its history afresh.
    report = client.get(f"/api/reports/{rid}", headers=user).json()
    report["config"]["widgets"][0]["sql"] = "SELECT COUNT(*) AS total FROM sales_log"
    client.put(f"/api/reports/{rid}", headers=user, json={"config": report["config"]})
    assert client.get(f"/api/reports/{rid}/history", headers=user).json()["widgets"] == {}
    assert client.get(f"/api/reports/{rid}/history/compare", headers=user).json()["widgets"] == []


def test_history_needs_a_dashboard_and_a_valid_retention(client, user, make_report, dashboard):
    classic = make_report(user)
    assert client.get(f"/api/reports/{classic['id']}/history", headers=user).status_code == 400
    res = client.put(f"/api/reports/{dashboard['id']}/schedule", headers=user, json={"every": "daily", "history_days": 7})
    assert res.status_code == 422
    res = client.put(f"/api/reports/{dashboard['id']}/schedule", headers=user, json={"every": "daily", "history_days": 365})
    assert res.json()["report"]["history_days"] == 365
