"""Context-aware suggestions (app/suggestions.py), with a fake Ollama whose answer each test sets.

Covers: suggestions naming tables or columns the source doesn't share are dropped; a failing or
unusable model falls back to suggestions from the columns; nothing already shown or asked comes
back; quick actions appear only when they apply; and no query is ever run."""

import json
import sqlite3
import tempfile
import threading
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

from app import suggestions

# What the fake model answers next: a list of suggestions, or "fail" for an HTTP 500.
ANSWER: dict = {"value": []}
SEEN: list[dict] = []   # the prompts the fake model was sent


def _s(text, uses=(), category="analytical", kind="question"):
    return {"text": text, "category": category, "kind": kind, "uses": list(uses)}


class FakeOllama(BaseHTTPRequestHandler):
    def do_POST(self):  # noqa: N802
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        SEEN.append({"system": body["messages"][0]["content"], "user": body["messages"][1]["content"]})
        if ANSWER["value"] == "fail":
            self.send_response(500)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        if isinstance(ANSWER["value"], dict):     # a whole answer of another shape (the summary)
            content = ANSWER["value"]
        else:
            content = {"suggestions": ANSWER["value"]}
        data = json.dumps({"message": {"role": "assistant", "content": json.dumps(content)}}).encode()
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
        "name": f"Suggest {uuid.uuid4().hex[:6]}", "provider": "ollama", "model": "fake",
        "base_url": f"http://127.0.0.1:{server.server_port}"})
    yield res.json()["id"]
    client.delete(f"/api/ai-models/{res.json()['id']}", headers=manager)
    server.shutdown()


@pytest.fixture(scope="module")
def source_id(client, manager):
    path = Path(tempfile.mkdtemp(prefix="bi-suggest-")) / "shop.db"
    con = sqlite3.connect(path)
    con.executescript("""
        CREATE TABLE sales_log (id INTEGER PRIMARY KEY, region TEXT, product TEXT, amount REAL, sold_on DATE);
        CREATE TABLE staff (id INTEGER PRIMARY KEY, name TEXT, salary REAL);
        INSERT INTO sales_log (region, product, amount, sold_on) VALUES
            ('North', 'Desk', 1500, '2026-01-10'), ('South', 'Chair', 700, '2026-02-03'),
            ('North', 'Chair', 300, '2026-03-15');
    """)
    con.commit()
    con.close()
    c = client.post("/api/connections", headers=manager, json={
        "name": f"Suggest shop {uuid.uuid4().hex[:6]}", "db_type": "sqlite", "database": path.as_posix()}).json()
    # Only the sales log is shared; staff (and its salaries) is not.
    client.put(f"/api/connections/{c['id']}", headers=manager, json={"allowed_tables": ["main.sales_log"]})
    yield c["id"]
    client.delete(f"/api/connections/{c['id']}", headers=manager)


@pytest.fixture(autouse=True)
def _reset():
    suggestions.forget()
    SEEN.clear()
    ANSWER["value"] = []
    yield


@pytest.fixture
def no_sql(monkeypatch):
    """Fails the test if anything tries to run a query while suggesting."""
    from app import datasources

    def refuse(*args, **kwargs):
        raise AssertionError("suggestions must never run SQL")
    monkeypatch.setattr(datasources, "run_sql", refuse)


FOLLOWUP = {"kind": "followup", "question": "Total amount by region",
            "answer": "North has the highest total.", "title": "Amount by region",
            "sql": "SELECT region, SUM(amount) AS total FROM sales_log GROUP BY region",
            "columns": ["region", "total"], "rows": [["North", 1800.0], ["South", 700.0]], "row_count": 2}


def _post(client, headers, **body):
    res = client.post("/api/assistant/suggestions", headers=headers, json=body)
    assert res.status_code == 200, res.text
    return res.json()


def test_followups_drop_tables_and_columns_that_do_not_exist(client, user, model_id, source_id, no_sql):
    ANSWER["value"] = [
        _s("Which product has the highest amount?", ["sales_log", "product", "amount"]),
        _s("Average salary by region", ["staff", "salary", "region"]),             # not shared
        _s("Profit margin by region", ["profit", "region"]),                       # no such column
        _s("Total of customer_lifetime_value by region", ["region"]),              # invented, in the text
        _s("Show [main.staff] by name", []),                                       # unshared table, in the text
        _s("How has total changed month by month?", ["total", "sold_on"], "advanced"),
        _s("Compare North and South over time", ["region", "sold_on"]),
        _s("Top 3 products by amount in the North", ["product", "amount", "region"], "basic"),
    ]
    body = _post(client, user, source_id=source_id, model_id=model_id, **FOLLOWUP)
    texts = [s["text"] for s in body["suggestions"]]
    assert body["origin"] == "ai"
    assert "Which product has the highest amount?" in texts
    assert "How has total changed month by month?" in texts           # "total" is a result column
    assert not any(w in t.lower() for t in texts for w in ("salary", "profit", "lifetime", "staff"))
    assert 4 <= len(texts) <= 6
    # The model was given the question, the answer, the columns and sample rows, and the schema.
    prompt = SEEN[-1]
    assert "North has the highest total." in prompt["user"] and "region | total" in prompt["user"]
    assert "sales_log" in prompt["system"] and "staff" not in prompt["system"]


def test_followups_never_repeat_what_was_shown_or_asked(client, user, model_id, source_id):
    ANSWER["value"] = [
        _s("Which product has the highest amount?", ["product", "amount"]),
        _s("which product has the highest amount", ["product", "amount"]),       # the same, reworded
        _s("Total amount by region", ["amount", "region"]),                      # already asked
        _s("Monthly amount over the last year", ["amount", "sold_on"]),          # already shown
        _s("Amount by product and region", ["amount", "product", "region"]),
    ]
    body = _post(client, user, source_id=source_id, model_id=model_id, **FOLLOWUP,
                 previous=["Monthly amount over the last year"], asked=["Total amount by region"])
    texts = [s["text"].lower() for s in body["suggestions"]]
    assert texts.count("which product has the highest amount?") == 1
    assert "which product has the highest amount" not in texts
    assert "total amount by region" not in texts
    assert "monthly amount over the last year" not in texts
    keys = [suggestions._key(t) for t in texts]
    assert all(not suggestions._same(a, b) for i, a in enumerate(keys) for b in keys[i + 1:])
    # The model was told what not to repeat.
    assert "Already shown" in SEEN[-1]["user"] and "Already asked" in SEEN[-1]["user"]


def test_falls_back_to_the_columns_when_the_model_fails(client, user, model_id, source_id, no_sql):
    ANSWER["value"] = "fail"
    body = _post(client, user, source_id=source_id, model_id=model_id, **FOLLOWUP)
    assert body["origin"] == "fallback" and body["notice"]
    texts = [s["text"] for s in body["suggestions"]]
    assert 4 <= len(texts) <= 6
    # Grounded: only words from the real columns, and never the unshared table.
    assert any("region" in t for t in texts) and not any("salary" in t for t in texts)
    assert all(s["category"] in ("basic", "analytical", "advanced", "recent") for s in body["suggestions"])


def test_falls_back_when_everything_the_model_wrote_is_invented(client, user, model_id, source_id):
    ANSWER["value"] = [_s("Average salary by region", ["salary"]), _s("Profit by product", ["profit"])]
    body = _post(client, user, source_id=source_id, model_id=model_id, **FOLLOWUP)
    texts = " ".join(s["text"] for s in body["suggestions"]).lower()
    assert len(body["suggestions"]) >= 4 and "salary" not in texts and "profit" not in texts


def test_works_without_a_model_and_with_a_removed_one(client, user, source_id):
    body = _post(client, user, source_id=source_id, **FOLLOWUP)
    assert body["origin"] == "fallback" and len(body["suggestions"]) >= 4
    gone = _post(client, user, source_id=source_id, model_id=999999, **FOLLOWUP)
    assert gone["origin"] == "fallback" and gone["notice"] and len(gone["suggestions"]) >= 4


def test_quick_actions_only_when_they_apply(client, user, source_id):
    body = _post(client, user, source_id=source_id, **FOLLOWUP)
    ids = [a["id"] for a in body["actions"]]
    assert {"change_chart", "view_rows", "view_sql", "export_csv", "add_to_report", "build_report"} <= set(ids)
    # The sales log has a date column, so comparing with the previous period means something.
    assert "compare_period" in ids

    # One number from a table with no date: no chart to change and no period to compare.
    no_date = _post(client, user, source_id=None, kind="followup", question="How many rows?",
                    sql="SELECT COUNT(*) AS n FROM customers_nowhere", columns=["n"], rows=[[3]], row_count=1)
    no_ids = [a["id"] for a in no_date["actions"]]
    assert "change_chart" not in no_ids and "compare_period" not in no_ids


def test_starters_mix_levels_and_use_past_questions(client, user, model_id, source_id, no_sql):
    chat = client.post("/api/chats", headers=user, json={"source_id": source_id, "model_id": model_id}).json()
    # A past question, saved straight into the history (the chat endpoint would need a real answer).
    from app.database import SessionLocal
    from app.models import ChatMessage
    with SessionLocal() as db:
        db.add(ChatMessage(conversation_id=chat["id"], question="Which products sold best in March?",
                           status="ok", result={}, error="", model_name="fake"))
        db.commit()
    body = _post(client, user, kind="starter", source_id=source_id)
    cats = {s["category"] for s in body["suggestions"]}
    texts = [s["text"] for s in body["suggestions"]]
    assert "Which products sold best in March?" in texts                    # their own question, back
    assert {"basic", "analytical", "advanced"} <= cats
    assert 6 <= len(texts) <= 10 and not any("salary" in t for t in texts)
    client.delete(f"/api/chats/{chat['id']}", headers=user)


def test_starters_are_cached_so_the_model_is_asked_once(client, user, model_id, source_id):
    ANSWER["value"] = [_s(f"Amount by region, take {i}", ["amount", "region"]) for i in range(1)] + [
        _s("Count of sales by product", ["product"], "basic"),
        _s("Monthly amount trend", ["amount", "sold_on"]),
        _s("Regions above the average amount", ["region", "amount"], "advanced"),
        _s("Products by region", ["product", "region"], "advanced"),
        _s("Total amount", ["amount"], "basic"),
    ]
    first = _post(client, user, kind="starter", source_id=source_id, model_id=model_id)
    second = _post(client, user, kind="starter", source_id=source_id, model_id=model_id)
    assert first == second and len(SEEN) == 1
    _post(client, user, kind="starter", source_id=source_id, model_id=model_id, refresh=True)
    assert len(SEEN) == 2


@pytest.fixture
def report(client, user, source_id):
    res = client.post("/api/assistant/save", headers=user, json={
        "source_id": source_id, "title": "Sales overview", "prompt": "Sales overview", "widgets": [
            {"id": "w1", "title": "Amount by region", "question": "Amount by region",
             "sql": "SELECT region, SUM(amount) AS total FROM sales_log GROUP BY region ORDER BY total DESC",
             "chart": {"type": "bar", "x": "region", "y": ["total"]}},
        ]})
    assert res.status_code == 201, res.text
    yield res.json()
    client.delete(f"/api/reports/{res.json()['id']}", headers=user)


def test_report_insights_are_grounded_and_mark_charts(client, user, model_id, report, no_sql):
    ANSWER["value"] = [
        _s("Amount by product", ["amount", "product"], kind="chart"),
        _s("Why does North lead the amount by region?", ["region", "amount"]),
        _s("Headcount by region", ["headcount", "region"], kind="chart"),        # no such column
        _s("Monthly amount over the last year", ["amount", "sold_on"], kind="chart"),
        _s("Which product sells best in the South?", ["product", "region"]),
    ]
    body = _post(client, user, kind="report", report_id=report["id"], model_id=model_id)
    texts = [s["text"] for s in body["suggestions"]]
    assert "Headcount by region" not in texts and "Amount by product" in texts
    assert next(s for s in body["suggestions"] if s["text"] == "Amount by product")["kind"] == "chart"
    # The model read the report's charts, their SQL and the numbers the report last showed.
    assert "Amount by region (bar)" in SEEN[-1]["user"] and "North" in SEEN[-1]["user"]
    ids = [a["id"] for a in body["actions"]]
    assert ids[0] == "ask_about" and {"add_chart", "compare_periods", "executive_summary",
                                      "export_excel", "export_ppt", "build_another"} <= set(ids)


def test_report_insights_fall_back_and_hide_what_does_not_apply(client, user, model_id, report):
    ANSWER["value"] = "fail"
    body = _post(client, user, kind="report", report_id=report["id"], model_id=model_id)
    assert body["origin"] == "fallback" and len(body["suggestions"]) >= 4
    # Without a model, there is no executive summary to offer.
    plain = _post(client, user, kind="report", report_id=report["id"])
    assert "executive_summary" not in [a["id"] for a in plain["actions"]]
    # Someone who can't edit the report isn't offered to add charts to it.
    ctx = {"widgets": [{"title": "x"}]}
    assert "add_chart" not in [a["id"] for a in suggestions.report_actions(ctx, False, can_edit=False, ai=True)]
    assert "compare_periods" not in [a["id"] for a in suggestions.report_actions(ctx, False, can_edit=True, ai=True)]


def test_report_kind_needs_a_report(client, user):
    res = client.post("/api/assistant/suggestions", headers=user, json={"kind": "report"})
    assert res.status_code == 400


def test_executive_summary_reads_saved_numbers(client, user, model_id, report, no_sql):
    ANSWER["value"] = {"summary": "North leads with 1,800 of 2,500.", "highlights": ["North: 1,800", "South: 700"]}
    res = client.post(f"/api/reports/{report['id']}/summary", headers=user, json={"model_id": model_id})
    assert res.status_code == 200, res.text
    assert res.json()["summary"].startswith("North leads") and len(res.json()["highlights"]) == 2
    assert "North | 1800" in SEEN[-1]["user"]


def test_grounding_helper():
    schema = suggestions.Schema(tables={"main.orders": [("region", "TEXT"), ("amount", "REAL")]},
                                known={"main.orders", "orders", "region", "amount"})
    assert suggestions.grounded("Total amount by region", ["orders", "amount"], schema)
    assert not suggestions.grounded("Total amount by sales_rep", [], schema)
    assert not suggestions.grounded("Rows of main.salaries", [], schema)
    assert suggestions.grounded('Orders where region is "North"', [], schema)   # a quoted value, not a name
    assert not suggestions.grounded("Orders by `rep_name`", [], schema)


def test_openpages_starters_mix_levels_without_reading_the_schema(monkeypatch):
    """An OpenPages connection's starters come in every level, and need no field reads."""
    from app.datasources import DataSource
    src = DataSource(id=9100, name="GRC", db_type="openpages", version="v1",
                     tables=["openpages.SOXRisk", "openpages.SOXControl", "openpages.SOXIssue"])
    picker = suggestions.Picker([], 8)
    suggestions.fallback_starters(src, suggestions.Schema(tables={}, known=set()), [], picker)
    assert {"basic", "analytical", "advanced"} <= {s.category for s in picker.out}


def test_past_report_requests_are_not_offered_as_questions():
    assert suggestions._NOT_A_QUESTION.search("genrate one business entity risk, and control report")
    assert suggestions._NOT_A_QUESTION.search("make me a sales dashboard")
    assert not suggestions._NOT_A_QUESTION.search("Average order value by channel")
    # Follow-ups that only made sense after the answer before them.
    assert suggestions._NEEDS_CONTEXT.search("crate pie chart for this")
    assert suggestions._NEEDS_CONTEXT.search("give me list of these risk with name")
    assert not suggestions._NEEDS_CONTEXT.search("Which products sold best this quarter?")
