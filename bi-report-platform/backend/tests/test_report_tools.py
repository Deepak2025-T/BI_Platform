"""Editing tools: duplicate a report, try SQL, ask the AI to change a chart, and hand-picked filters."""

import json
import sqlite3
import threading
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

REVISED_SQL = "SELECT region, SUM(amount) AS total FROM sales_log WHERE region = 'North' GROUP BY region"


class FakeModel(BaseHTTPRequestHandler):
    """Rewrites a chart to show only the North region."""

    def do_POST(self):  # noqa: N802
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        assert "Change requested" in body["messages"][1]["content"]
        answer = {"action": "query", "reply": "", "title": "North total", "sql": REVISED_SQL,
                  "chart": {"type": "bar", "x": "region", "y": ["total"]}}
        data = json.dumps({"message": {"role": "assistant", "content": json.dumps(answer)}}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass


@pytest.fixture(scope="module")
def model_id(client, manager):
    server = HTTPServer(("127.0.0.1", 0), FakeModel)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    m = client.post("/api/ai-models", headers=manager, json={
        "name": f"Editor model {uuid.uuid4().hex[:6]}", "provider": "ollama", "model": "fake",
        "base_url": f"http://127.0.0.1:{server.server_port}"}).json()
    yield m["id"]
    client.delete(f"/api/ai-models/{m['id']}", headers=manager)
    server.shutdown()


@pytest.fixture
def dashboard(tmp_path, client, manager, user):
    path = (tmp_path / "tools.db").as_posix()
    con = sqlite3.connect(path)
    con.executescript("""CREATE TABLE sales_log (id INTEGER PRIMARY KEY, region TEXT, sold_on TEXT, amount REAL);
        INSERT INTO sales_log (region, sold_on, amount) VALUES ('North', '2026-01-05', 100), ('South', '2026-02-10', 50),
        ('North', '2026-03-01', 25);""")
    con.commit()
    con.close()
    c = client.post("/api/connections", headers=manager, json={"name": f"Tools {uuid.uuid4().hex[:6]}", "db_type": "sqlite", "database": path}).json()
    client.put(f"/api/connections/{c['id']}", headers=manager, json={"allowed_tables": ["main.sales_log"]})
    widgets = [{"id": "w1", "title": "By region", "sql": "SELECT region, SUM(amount) AS total FROM sales_log GROUP BY region",
                "chart": {"type": "bar", "x": "region", "y": ["total"]}},
               {"id": "w2", "title": "Total", "sql": "SELECT SUM(amount) AS total FROM sales_log",
                "chart": {"type": "kpi", "x": "", "y": ["total"]}}]
    report = client.post("/api/assistant/save", headers=user, json={"source_id": c["id"], "title": "Tools", "widgets": widgets}).json()
    yield report
    client.delete(f"/api/connections/{c['id']}", headers=manager)


def test_duplicate_makes_an_editable_draft(client, user, manager, dashboard):
    client.put(f"/api/reports/{dashboard['id']}/schedule", headers=user, json={"every": "daily"})
    client.post(f"/api/reports/{dashboard['id']}/publish", headers=user)
    # A manager duplicates someone else's published report: the copy is the manager's own draft.
    res = client.post(f"/api/reports/{dashboard['id']}/duplicate", headers=manager)
    assert res.status_code == 201, res.text
    copy = res.json()
    assert copy["title"] == "Copy of Tools" and copy["status"] == "draft" and copy["owner_name"] == "Demo Manager"
    assert copy["refresh_every"] == "off" and copy["category"] is None
    assert [w["sql"] for w in copy["config"]["widgets"]] == [w["sql"] for w in dashboard["config"]["widgets"]]
    # Changing the copy leaves the original alone.
    config = {**copy["config"], "widgets": copy["config"]["widgets"][:1]}
    client.put(f"/api/reports/{copy['id']}", headers=manager, json={"title": "Mine", "config": config})
    original = client.get(f"/api/reports/{dashboard['id']}", headers=user).json()
    assert len(original["config"]["widgets"]) == 2 and original["title"] == "Tools"


def test_duplicate_with_a_title_and_classic_reports(client, user, make_report):
    classic = make_report(user, "Classic")
    copy = client.post(f"/api/reports/{classic['id']}/duplicate", headers=user, json={"title": "Classic v2"}).json()
    assert copy["title"] == "Classic v2" and copy["config"] == classic["config"]


def test_drafts_of_others_cannot_be_duplicated(client, user, manager, dashboard):
    assert client.post(f"/api/reports/{dashboard['id']}/duplicate", headers=user).status_code == 201
    mine = client.post(f"/api/reports/{dashboard['id']}/duplicate", headers=manager).json()  # manager's draft
    assert client.post(f"/api/reports/{mine['id']}/duplicate", headers=user).status_code == 404


def test_preview_sql_is_checked(client, user, manager, dashboard):
    ok = client.post(f"/api/reports/{dashboard['id']}/preview-sql", headers=user,
                     json={"sql": "SELECT region, COUNT(*) AS n FROM sales_log GROUP BY region ORDER BY region"})
    assert ok.status_code == 200 and ok.json()["rows"] == [["North", 2], ["South", 1]]
    bad = client.post(f"/api/reports/{dashboard['id']}/preview-sql", headers=user, json={"sql": "DELETE FROM sales_log"})
    assert bad.status_code == 422 and "SELECT" in bad.json()["detail"]
    other = client.post(f"/api/reports/{dashboard['id']}/preview-sql", headers=user, json={"sql": "SELECT * FROM app_users"})
    assert other.status_code == 422


def test_only_editors_can_try_sql(client, user, manager, dashboard):
    client.post(f"/api/reports/{dashboard['id']}/publish", headers=user)
    copy = client.post(f"/api/reports/{dashboard['id']}/duplicate", headers=manager).json()
    client.post(f"/api/reports/{copy['id']}/publish", headers=manager)
    res = client.post(f"/api/reports/{copy['id']}/preview-sql", headers=user, json={"sql": "SELECT 1 AS x FROM sales_log"})
    assert res.status_code == 403


def test_ask_ai_to_change_a_chart(client, user, dashboard, model_id):
    widget = {**dashboard["config"]["widgets"][0], "size": "full"}
    res = client.post(f"/api/reports/{dashboard['id']}/widgets/revise", headers=user, json={
        "model_id": model_id, "widget": widget, "instruction": "only the North region"})
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["widget"]["id"] == widget["id"] and body["widget"]["size"] == "full"
    assert body["widget"]["title"] == "North total" and "North" in body["widget"]["sql"]
    assert body["data"]["rows"] == [["North", 125.0]]


def test_filter_columns_by_hand(client, user, dashboard):
    widgets = dashboard["config"]["widgets"]
    cols = client.post(f"/api/reports/{dashboard['id']}/filters/columns", headers=user, json={"widgets": widgets}).json()
    first = widgets[0]["id"]
    assert cols[first][0]["table"] == "main.sales_log"
    assert {"region", "sold_on", "amount"} <= {c["name"] for c in cols[first][0]["columns"]}

    f = client.post(f"/api/reports/{dashboard['id']}/filters/manual", headers=user, json={
        "label": "Region", "kind": "category", "widgets": widgets,
        "columns": {first: {"table": "main.sales_log", "column": "region"},
                    widgets[1]["id"]: {"table": "main.sales_log", "column": "no_such_column"}}}).json()
    assert f["options"] == ["North", "South"]
    assert list(f["columns"]) == [first]  # the made-up column was dropped, so that chart isn't filtered

    config = {**dashboard["config"], "filters": [f]}
    client.put(f"/api/reports/{dashboard['id']}", headers=user, json={"config": config})
    data = client.post(f"/api/reports/{dashboard['id']}/data", headers=user,
                       json={"filters": {f["id"]: {"values": ["South"]}}}).json()
    assert data["widgets"][0]["rows"] == [["South", 50.0]]
    assert data["widgets"][1]["not_filtered"] == [f["id"]]


def test_date_filter_by_hand(client, user, dashboard):
    widgets = dashboard["config"]["widgets"]
    picks = {w["id"]: {"table": "main.sales_log", "column": "sold_on"} for w in widgets}
    f = client.post(f"/api/reports/{dashboard['id']}/filters/manual", headers=user, json={
        "label": "Sold on", "kind": "date", "widgets": widgets, "columns": picks}).json()
    client.put(f"/api/reports/{dashboard['id']}", headers=user, json={"config": {**dashboard["config"], "filters": [f]}})
    data = client.post(f"/api/reports/{dashboard['id']}/data", headers=user,
                       json={"filters": {f["id"]: {"date_from": "2026-02-01", "date_to": "2026-03-31"}}}).json()
    assert data["widgets"][1]["rows"] == [[75.0]]


def test_text_tiles_sit_between_charts(client, user, dashboard):
    """A text tile (a heading or note) has no query: charts, filters, refresh and Excel skip it."""
    text = {"id": "t1", "kind": "text", "title": "Regional view", "question": "", "sql": "", "text": "Notes for the team",
            "chart": {"type": "table", "x": "", "y": []}}
    config = {**dashboard["config"], "widgets": [text] + dashboard["config"]["widgets"]}
    assert client.put(f"/api/reports/{dashboard['id']}", headers=user, json={"config": config}).status_code == 200

    data = client.post(f"/api/reports/{dashboard['id']}/data", headers=user, json={"filters": {}}).json()
    assert [w["id"] for w in data["widgets"]] == [w["id"] for w in dashboard["config"]["widgets"]]
    assert all(w["ok"] for w in data["widgets"])

    client.put(f"/api/reports/{dashboard['id']}/schedule", headers=user, json={"every": "daily"})
    assert len(client.post(f"/api/reports/{dashboard['id']}/data", headers=user, json={"filters": {}}).json()["widgets"]) == 2

    xlsx = client.post(f"/api/reports/{dashboard['id']}/export", headers=user, json={"filters": {}})
    assert xlsx.status_code == 200 and xlsx.content[:2] == b"PK"
