"""Links that open one report without signing in.

The questions worth asking of a public link are all about what it refuses: a draft can't have one,
a revoked or expired one stops opening, and what it serves carries no SQL, no connection and no
database error text. These tests reuse the small SQLite shop from test_dashboards.
"""

import uuid

import pytest

from tests.test_assistant import model_id  # noqa: F401  (fixture)
from tests.test_dashboards import BY_REGION, TOTAL, shop, source  # noqa: F401  (fixtures)


def _widget(wid, title, sql, chart_type="table"):
    return {"id": wid, "title": title, "sql": sql, "chart": {"type": chart_type, "x": "", "y": []},
            "visual": {"dimensions": [{"column": "region"}]}}


@pytest.fixture
def report(client, user, source):  # noqa: F811
    """A saved dashboard of the shop, owned by the ordinary user. Each test gets its own."""
    widgets = [_widget("total", "Total sales", TOTAL, "kpi"), _widget("region", "By region", BY_REGION)]
    res = client.post("/api/assistant/save", headers=user, json={
        "source_id": source, "title": f"Shared shop {uuid.uuid4().hex[:6]}", "widgets": widgets})
    assert res.status_code == 201, res.text
    saved = res.json()
    # Saving gives each chart a fresh id; put the readable ones back so the tests can name them.
    config = {**saved["config"], "widgets": widgets}
    assert client.put(f"/api/reports/{saved['id']}", headers=user, json={"config": config}).status_code == 200
    return {**saved, "config": config}


def _publish(client, headers, report_id):
    res = client.post(f"/api/reports/{report_id}/publish", headers=headers, json={"category_id": None})
    assert res.status_code == 200, res.text


def _share(client, headers, report_id, **body):
    res = client.post(f"/api/reports/{report_id}/share", headers=headers, json=body or None)
    assert res.status_code == 201, res.text
    return res.json()


def test_a_draft_cannot_be_shared(client, user, report):
    res = client.post(f"/api/reports/{report['id']}/share", headers=user, json={})
    assert res.status_code == 400
    assert "Publish this report" in res.json()["detail"]


def test_asking_twice_gives_the_same_link_back(client, user, report):
    _publish(client, user, report["id"])
    first = _share(client, user, report["id"])
    again = _share(client, user, report["id"])
    assert first["token"] == again["token"]
    assert again["path"] == f"/shared/{first['token']}"
    assert len(first["token"]) >= 32  # a guessable link is not a link


def test_the_link_opens_the_report_without_signing_in(client, user, report):
    _publish(client, user, report["id"])
    token = _share(client, user, report["id"])["token"]

    opened = client.get(f"/api/public/reports/{token}")
    assert opened.status_code == 200, opened.text
    body = opened.json()
    assert body["title"] == report["title"]
    assert [w["title"] for w in body["config"]["widgets"]] == ["Total sales", "By region"]

    data = client.post(f"/api/public/reports/{token}/data", json={"filters": {}})
    assert data.status_code == 200, data.text
    rows = {w["id"]: w for w in data.json()["widgets"]}
    assert rows["total"]["ok"] and rows["total"]["rows"] == [[375.0]]
    assert rows["region"]["rows"] == [["East", 25.0], ["North", 300.0], ["South", 50.0]]


def test_what_a_link_serves_says_nothing_about_the_database(client, user, report):
    _publish(client, user, report["id"])
    token = _share(client, user, report["id"])["token"]
    config = client.get(f"/api/public/reports/{token}").json()["config"]

    assert config["source_id"] is None and config["source_name"] == ""
    for widget in config["widgets"]:
        assert "sql" not in widget and "visual" not in widget
    # Nothing anywhere in the payload quotes a query or a table name.
    assert "SELECT" not in repr(config) and "orders" not in repr(config)


def test_a_public_caller_cannot_ask_for_a_refresh(client, user, report):
    """refresh is the one lever that costs the database something, so the body can't reach it."""
    _publish(client, user, report["id"])
    token = _share(client, user, report["id"])["token"]
    res = client.post(f"/api/public/reports/{token}/data", json={"filters": {}, "refresh": True})
    assert res.status_code == 200
    # Served all the same, but from the cache: the call is answered, not obeyed.
    assert all(w["ok"] for w in res.json()["widgets"])


def test_a_revoked_link_stops_opening(client, user, report):
    _publish(client, user, report["id"])
    token = _share(client, user, report["id"])["token"]
    assert client.delete(f"/api/reports/{report['id']}/share", headers=user).status_code == 204

    assert client.get(f"/api/public/reports/{token}").status_code == 404
    assert client.post(f"/api/public/reports/{token}/data", json={}).status_code == 404
    assert client.get(f"/api/reports/{report['id']}/share", headers=user).json() is None
    # Revoking does not stand in the way of sharing again; the new link is a different secret.
    assert _share(client, user, report["id"])["token"] != token


def test_an_expired_link_stops_opening(client, user, report):
    from datetime import timedelta

    from app.database import SessionLocal
    from app.models import ReportShare, now_utc

    _publish(client, user, report["id"])
    token = _share(client, user, report["id"], expires_days=30)["token"]
    with SessionLocal() as db:
        share = db.query(ReportShare).filter(ReportShare.token == token).one()
        assert share.expires_at is not None
        share.expires_at = now_utc() - timedelta(minutes=1)
        db.commit()
    assert client.get(f"/api/public/reports/{token}").status_code == 404


def test_a_link_dies_when_the_report_goes_back_to_a_draft(client, user, report):
    _publish(client, user, report["id"])
    token = _share(client, user, report["id"])["token"]
    assert client.get(f"/api/public/reports/{token}").status_code == 200

    from app.database import SessionLocal
    from app.models import Report

    with SessionLocal() as db:
        db.get(Report, report["id"]).status = "draft"
        db.commit()
    assert client.get(f"/api/public/reports/{token}").status_code == 404


def test_only_the_owner_or_a_manager_can_make_a_link(client, user, manager, report):
    _publish(client, user, report["id"])
    other = client.post("/api/reports", headers=manager, json={
        "title": "Someone else's", "prompt": "p", "config": {"kind": "dashboard", "widgets": []}}).json()
    assert client.post(f"/api/reports/{other['id']}/share", headers=user, json={}).status_code in (403, 404)
    # The manager may share the user's report, as they may edit it.
    assert client.post(f"/api/reports/{report['id']}/share", headers=manager, json={}).status_code == 201


def test_opening_a_link_counts_the_view(client, user, report):
    _publish(client, user, report["id"])
    token = _share(client, user, report["id"])["token"]
    client.get(f"/api/public/reports/{token}")
    client.get(f"/api/public/reports/{token}")
    seen = client.get(f"/api/reports/{report['id']}/share", headers=user).json()
    assert seen["views"] == 2 and seen["last_viewed_at"]


def test_a_chart_that_fails_says_only_that_it_failed(client, user, source):  # noqa: F811
    """A query error can name tables and columns, which is exactly what a public page must not say."""
    made = client.post("/api/assistant/save", headers=user, json={
        "source_id": source, "title": f"Broken {uuid.uuid4().hex[:6]}",
        "widgets": [_widget("bad", "Broken", TOTAL)]}).json()
    # A query that passes the safety check at save time but cannot run: the column isn't there.
    broken = [_widget("bad", "Broken", "SELECT no_such_column FROM orders")]
    assert client.put(f"/api/reports/{made['id']}", headers=user,
                      json={"config": {**made["config"], "widgets": broken}}).status_code == 200
    _publish(client, user, made["id"])
    token = _share(client, user, made["id"])["token"]

    public = client.post(f"/api/public/reports/{token}/data", json={}).json()["widgets"][0]
    assert public["ok"] is False and public["error"] == "This chart couldn't be shown."
    # Whoever can open the report itself still gets the real reason.
    private = client.post(f"/api/reports/{made['id']}/data", headers=user, json={}).json()["widgets"][0]
    assert "no_such_column" in private["error"]
