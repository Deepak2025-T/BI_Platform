"""
Drilling into a chart built from fields, and the pictures people put on reports.

Drilling matters most for what it refuses: the columns come from the saved chart, so a request
can only say which value was clicked, never which column to group by or filter on.
"""

import sqlite3
import uuid

import pytest

PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000000a"
    "49444154789c6360000002000100ffff03000006000557bfabd40000000049454e44ae426082")


@pytest.fixture(scope="module")
def shop(tmp_path_factory) -> str:
    path = (tmp_path_factory.mktemp("drill") / "shop.db").as_posix()
    con = sqlite3.connect(path)
    con.executescript("""
        CREATE TABLE orders (id INTEGER PRIMARY KEY, region TEXT, product TEXT, amount REAL, order_date DATE);
        INSERT INTO orders (region, product, amount, order_date) VALUES
            ('North', 'Pro',   100, '2024-01-15'),
            ('North', 'Pro',    40, '2024-02-10'),
            ('North', 'Team',   60, '2024-02-20'),
            ('South', 'Pro',    50, '2024-02-28'),
            ('South', 'Team',   25, '2024-03-05');
    """)
    con.commit()
    con.close()
    return path


@pytest.fixture(scope="module")
def source(client, manager, shop) -> int:
    c = client.post("/api/connections", headers=manager, json={
        "name": f"Drill {uuid.uuid4().hex[:6]}", "db_type": "sqlite", "database": shop}).json()
    client.put(f"/api/connections/{c['id']}", headers=manager, json={"allowed_tables": ["main.orders"]})
    yield c["id"]
    client.delete(f"/api/connections/{c['id']}", headers=manager)


def _visual(drill):
    return {"table": "main.orders",
            "dimensions": [{"column": "region", "alias": "Region"}],
            "drill": drill,
            "measures": [{"column": "amount", "agg": "sum", "alias": "Total"}],
            "filters": [], "order": [{"ref": "Total", "dir": "desc"}], "limit": 500}


@pytest.fixture(scope="module")
def report(client, user, source) -> int:
    """A chart grouped by region, with product as the level under it."""
    widget = {"id": "w1", "title": "Sales by region", "question": "",
              "sql": 'SELECT "region" AS "Region", SUM("amount") AS "Total" FROM "main"."orders" GROUP BY "region"',
              "chart": {"type": "bar", "x": "Region", "y": ["Total"]},
              "visual": _visual([{"column": "product", "alias": "Product"}])}
    r = client.post("/api/assistant/save", headers=user, json={
        "source_id": source, "title": "Drill demo", "widgets": [widget]}).json()
    # assistant/save gives widgets new ids, so put the readable one back.
    config = {**r["config"], "widgets": [widget]}
    client.put(f"/api/reports/{r['id']}", headers=user, json={"config": config})
    return r["id"]


def _drill(client, headers, report_id, values, widget_id="w1"):
    return client.post(f"/api/reports/{report_id}/drill", headers=headers,
                       json={"widget_id": widget_id, "values": values, "filters": {}})


def test_drilling_regroups_inside_the_value_that_was_clicked(client, user, report):
    res = _drill(client, user, report, ["North"])
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["columns"] == ["Product", "Total"]
    assert body["chart"]["x"] == "Product"          # the chart now reads the new column
    assert body["depth"] == 1 and body["levels"] == 1
    # Only North's orders, grouped by product: Pro 140, Team 60.
    assert sorted(body["rows"]) == [["Pro", 140.0], ["Team", 60.0]]


def test_the_totals_are_the_whole_level_not_one_bar_split_up(client, user, report):
    """South has two products; drilling re-runs the query rather than reusing what was drawn."""
    rows = _drill(client, user, report, ["South"]).json()["rows"]
    assert sorted(rows) == [["Pro", 50.0], ["Team", 25.0]]


def test_drilling_past_the_last_level_is_refused(client, user, report):
    assert _drill(client, user, report, ["North", "Pro"]).status_code == 400


def test_a_chart_with_no_levels_cannot_be_drilled(client, user, source):
    widget = {"id": "flat", "title": "Flat", "question": "",
              "sql": 'SELECT "region" AS "Region", SUM("amount") AS "Total" FROM "main"."orders" GROUP BY "region"',
              "chart": {"type": "bar", "x": "Region", "y": ["Total"]}, "visual": _visual([])}
    r = client.post("/api/assistant/save", headers=user, json={
        "source_id": source, "title": "Flat demo", "widgets": [widget]}).json()
    client.put(f"/api/reports/{r['id']}", headers=user, json={"config": {**r["config"], "widgets": [widget]}})
    res = _drill(client, user, r["id"], ["North"], widget_id="flat")
    assert res.status_code == 400
    assert "drill" in res.json()["detail"].lower()


def test_an_unknown_chart_is_not_found(client, user, report):
    assert _drill(client, user, report, ["North"], widget_id="nope").status_code == 404


def test_signing_in_is_required_to_drill(client, report):
    assert _drill(client, {}, report, ["North"]).status_code == 401


# ---------- Pictures ----------

def _upload(client, headers, name="logo.png", content=PNG, kind="image/png"):
    return client.post("/api/uploads", headers=headers, files={"file": (name, content, kind)})


def test_a_picture_can_be_uploaded_and_read_back(client, user):
    res = _upload(client, user)
    assert res.status_code == 201, res.text
    url = res.json()["url"]
    got = client.get(url)
    assert got.status_code == 200
    assert got.content == PNG
    assert got.headers["content-type"].startswith("image/png")


def test_an_uploaded_picture_cannot_load_or_run_anything(client, user):
    """The headers are what make an uploaded SVG safe to open directly."""
    got = client.get(_upload(client, user).json()["url"])
    assert "default-src 'none'" in got.headers["content-security-policy"]
    assert got.headers["x-content-type-options"] == "nosniff"


def test_only_pictures_are_accepted(client, user):
    res = _upload(client, user, name="sneaky.html", content=b"<script>alert(1)</script>", kind="text/html")
    assert res.status_code == 400
    assert "PNG" in res.json()["detail"]


def test_an_unknown_picture_is_not_found(client):
    assert client.get("/api/uploads/not_a_real_name.png").status_code == 404


def test_uploading_needs_an_account(client):
    assert _upload(client, {}).status_code == 401
