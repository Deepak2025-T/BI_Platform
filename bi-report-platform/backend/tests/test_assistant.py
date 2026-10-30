"""Chat with a database and AI-built dashboards, using a fake Ollama that writes SQL for a small
SQLite business database. Exercises the real checking, retry, running and saving code."""

import json
import sqlite3
import threading
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

GOOD_SQL = "SELECT region, SUM(amount) AS total FROM orders GROUP BY region ORDER BY total DESC"


def _map_filter(system: str, user: str) -> dict:
    """Maps a date filter to order_date and any other filter to region, where the chart's tables have them."""
    wanted = "order_date" if "a date range" in system else "region"
    out = []
    for block in user.split("\n\nChart "):
        widget_id = block.removeprefix("Chart ").split(":", 1)[0]
        table = next((line.split(":")[0].strip() for line in block.splitlines()
                      if line.startswith("  ") and f" {wanted} " in line.split(":", 1)[-1] + " "), "")
        out.append({"widget_id": widget_id, "table": table, "column": wanted if table else ""})
    return {"columns": out}


def _reply(system: str, user: str) -> dict:
    if "map a dashboard filter" in system:
        return _map_filter(system, user)
    if "explain query results" in system:
        return {"answer": "North leads with the highest total."}
    if "design BI dashboards" in system:
        return {"title": "Orders overview", "widgets": [
            {"title": "Total orders", "question": "How much in total?", "sql": "SELECT SUM(amount) AS total FROM orders",
             "chart": {"type": "kpi", "x": "", "y": ["total"]}},
            {"title": "By region", "question": "Total by region", "sql": GOOD_SQL,
             "chart": {"type": "bar", "x": "region", "y": ["total"]}},
            {"title": "Secret", "question": "Salaries", "sql": "SELECT * FROM salaries",
             "chart": {"type": "table", "x": "", "y": []}},
        ]}
    query = lambda sql, chart=None: {"action": "query", "reply": "", "title": "Orders by region", "sql": sql,  # noqa: E731
                                     "chart": chart or {"type": "bar", "x": "region", "y": ["total"]}}
    if "Chart request" in user:
        if "salar" in user.lower():
            return query("SELECT * FROM salaries")
        return query(GOOD_SQL)
    question = user.rsplit("Question:", 1)[-1].lower()
    if "which tables" in question:
        return {"action": "reply", "reply": "You can ask about orders and customers.", "title": "", "sql": "",
                "chart": {"type": "table", "x": "", "y": []}}
    if "delete" in question:
        return query("DELETE FROM orders")
    if "try twice" in question and "previous query failed" not in user:
        return query("SELECT region, SUM(amount) AS total FROM missing_table GROUP BY region")
    return query(GOOD_SQL)


class FakeOllama(BaseHTTPRequestHandler):
    def do_POST(self):  # noqa: N802
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        answer = _reply(body["messages"][0]["content"], body["messages"][1]["content"])
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
    server = HTTPServer(("127.0.0.1", 0), FakeOllama)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    res = client.post("/api/ai-models", headers=manager, json={
        "name": f"Fake {uuid.uuid4().hex[:6]}", "provider": "ollama", "model": "fake",
        "base_url": f"http://127.0.0.1:{server.server_port}"})
    yield res.json()["id"]
    client.delete(f"/api/ai-models/{res.json()['id']}", headers=manager)
    server.shutdown()


@pytest.fixture(scope="module")
def source_id(client, manager, business_db):
    con = sqlite3.connect(business_db)
    con.executescript("""
        CREATE TABLE IF NOT EXISTS salaries (id INTEGER PRIMARY KEY, name TEXT, salary REAL);
        DELETE FROM orders;
        INSERT INTO orders (region, amount) VALUES ('North', 1500), ('North', 700), ('South', 900), ('East', 300);
    """)
    con.commit()
    con.close()
    c = client.post("/api/connections", headers=manager, json={
        "name": f"Shop {uuid.uuid4().hex[:6]}", "db_type": "sqlite", "database": business_db}).json()
    # Users may query orders and customers, but not salaries.
    client.put(f"/api/connections/{c['id']}", headers=manager, json={"allowed_tables": ["main.orders", "main.customers"]})
    yield c["id"]
    client.delete(f"/api/connections/{c['id']}", headers=manager)


def test_sources_list_names_only(client, user, source_id):
    rows = client.get("/api/sources", headers=user).json()
    assert rows[0]["builtin"] is True
    row = next(r for r in rows if r["id"] == source_id)
    assert set(row) == {"id", "name", "db_type", "type_label", "table_count", "builtin"} and row["table_count"] == 2


def test_chat_answers_with_data(client, user, model_id, source_id):
    res = client.post("/api/assistant/chat", headers=user, json={
        "source_id": source_id, "model_id": model_id, "question": "What are total orders by region?"})
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["kind"] == "result" and body["columns"] == ["region", "total"]
    assert body["rows"][0] == ["North", 2200.0]
    assert body["reply"] == "North leads with the highest total."
    assert body["chart"] == {"type": "bar", "x": "region", "y": ["total"]}
    assert body["sql"].endswith("LIMIT 500")


def test_chat_can_reply_without_a_query(client, user, model_id, source_id):
    body = client.post("/api/assistant/chat", headers=user, json={
        "source_id": source_id, "model_id": model_id, "question": "Which tables can I ask about?"}).json()
    assert body["kind"] == "reply" and "orders" in body["reply"]


def test_failed_query_is_sent_back_and_fixed(client, user, model_id, source_id):
    body = client.post("/api/assistant/chat", headers=user, json={
        "source_id": source_id, "model_id": model_id, "question": "Orders by region, try twice"}).json()
    assert body["kind"] == "result"
    assert [a["ok"] for a in body["attempts"]] == [False, True]
    assert "missing_table" in body["attempts"][0]["message"]


def test_writes_never_run(client, user, model_id, source_id, business_db):
    res = client.post("/api/assistant/chat", headers=user, json={
        "source_id": source_id, "model_id": model_id, "question": "delete everything"})
    assert res.status_code == 422 and "Only SELECT queries can run" in res.json()["detail"]
    assert sqlite3.connect(business_db).execute("SELECT COUNT(*) FROM orders").fetchone()[0] == 4


def test_tables_not_shared_stay_hidden(client, user, model_id, source_id):
    res = client.post("/api/assistant/widget", headers=user, json={
        "source_id": source_id, "model_id": model_id, "question": "Show salaries"})
    assert res.status_code == 422 and "salaries" in res.json()["detail"]


def test_chat_on_builtin_sample(client, user, model_id):
    # The fake model's SQL names "orders", which the built-in source doesn't have: refused, not run.
    res = client.post("/api/assistant/chat", headers=user, json={"model_id": model_id, "question": "orders by region"})
    assert res.status_code == 422 and "isn't one of the tables" in res.json()["detail"]


def test_build_dashboard_skips_failing_charts(client, user, model_id, source_id):
    res = client.post("/api/assistant/dashboard", headers=user, json={
        "source_id": source_id, "model_id": model_id, "prompt": "Orders dashboard",
        "parameters": {"date_from": "2024-01-01", "filters": "region = 'North'"}})
    assert res.status_code == 201, res.text
    body = res.json()
    config = body["report"]["config"]
    assert config["kind"] == "dashboard" and [w["title"] for w in config["widgets"]] == ["Total orders", "By region"]
    assert config["parameters"]["date_from"] == "2024-01-01"
    assert body["failed"][0]["title"] == "Secret"

    data = client.post(f"/api/reports/{body['report']['id']}/data", headers=user).json()
    assert [w["ok"] for w in data["widgets"]] == [True, True]
    assert data["widgets"][0]["rows"] == [[3400.0]]


def test_saving_chat_answers_checks_sql(client, user, source_id):
    good = {"id": "a1", "title": "By region", "sql": GOOD_SQL, "chart": {"type": "bar", "x": "region", "y": ["total"]}}
    res = client.post("/api/assistant/save", headers=user, json={"source_id": source_id, "title": "From chat", "widgets": [good]})
    assert res.status_code == 201 and res.json()["config"]["widgets"][0]["title"] == "By region"
    bad = {**good, "sql": "SELECT * FROM salaries"}
    assert client.post("/api/assistant/save", headers=user, json={
        "source_id": source_id, "title": "x", "widgets": [bad]}).status_code == 400


def test_edited_report_sql_is_checked_when_it_runs(client, user, source_id):
    """A dashboard's SQL can be changed with PUT /api/reports; it's still checked before it runs."""
    good = {"id": "a1", "title": "By region", "sql": GOOD_SQL, "chart": {"type": "table", "x": "", "y": []}}
    report = client.post("/api/assistant/save", headers=user, json={"source_id": source_id, "title": "t", "widgets": [good]}).json()
    config = {**report["config"], "widgets": [{**good, "sql": "DELETE FROM orders"}]}
    client.put(f"/api/reports/{report['id']}", headers=user, json={"config": config})
    data = client.post(f"/api/reports/{report['id']}/data", headers=user).json()
    assert data["widgets"][0]["ok"] is False


def test_other_users_drafts_stay_private(client, manager, user, source_id):
    good = {"id": "a1", "title": "By region", "sql": GOOD_SQL, "chart": {"type": "table", "x": "", "y": []}}
    report = client.post("/api/assistant/save", headers=manager, json={"source_id": source_id, "title": "t", "widgets": [good]}).json()
    assert client.post(f"/api/reports/{report['id']}/data", headers=user).status_code == 404
