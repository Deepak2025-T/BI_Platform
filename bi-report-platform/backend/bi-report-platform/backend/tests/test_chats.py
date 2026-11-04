"""Saved chat history: every turn is stored, follow-ups use the saved turns, and chats are private."""

import json
import threading
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

SQL = "SELECT region, SUM(revenue) AS total FROM sales GROUP BY region ORDER BY total DESC"


class FakeModel(BaseHTTPRequestHandler):
    """Answers with SQL on the sample sales table; says whether it was given earlier turns."""

    def do_POST(self):  # noqa: N802
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        system, user = body["messages"][0]["content"], body["messages"][1]["content"]
        if "explain query results" in system:
            answer = {"answer": "remembered" if "Earlier in this conversation" in FakeModel.last_prompt else "first"}
        else:
            FakeModel.last_prompt = user
            answer = {"action": "query", "reply": "", "title": "Revenue by region", "sql": SQL,
                      "chart": {"type": "bar", "x": "region", "y": ["total"]}}
        data = json.dumps({"message": {"role": "assistant", "content": json.dumps(answer)}}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass


FakeModel.last_prompt = ""


@pytest.fixture(scope="module")
def model_id(client, manager):
    server = HTTPServer(("127.0.0.1", 0), FakeModel)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    m = client.post("/api/ai-models", headers=manager, json={
        "name": f"Chat model {uuid.uuid4().hex[:6]}", "provider": "ollama", "model": "fake",
        "base_url": f"http://127.0.0.1:{server.server_port}"}).json()
    yield m["id"]
    client.delete(f"/api/ai-models/{m['id']}", headers=manager)
    server.shutdown()


def start(client, headers, model_id, source_id=None):
    res = client.post("/api/chats", headers=headers, json={"source_id": source_id, "model_id": model_id})
    assert res.status_code == 201, res.text
    return res.json()


def test_turns_are_saved_and_reopened(client, user, model_id):
    chat = start(client, user, model_id)
    assert chat["title"] == "New chat" and chat["source_name"] == "Sample sales data"
    msg = client.post(f"/api/chats/{chat['id']}/messages", headers=user, json={"question": "Revenue by region?"}).json()
    assert msg["status"] == "ok" and msg["result"]["kind"] == "result" and msg["result"]["rows"]

    saved = client.get(f"/api/chats/{chat['id']}", headers=user).json()
    assert saved["title"] == "Revenue by region?"  # named after the first question
    assert [m["question"] for m in saved["messages"]] == ["Revenue by region?"]
    assert saved["messages"][0]["result"]["sql"].startswith("SELECT region")
    assert saved["messages"][0]["model_name"]

    listed = client.get("/api/chats", headers=user).json()
    assert listed[0]["id"] == chat["id"] and listed[0]["message_count"] == 1


def test_follow_ups_use_saved_turns(client, user, model_id):
    chat = start(client, user, model_id)
    first = client.post(f"/api/chats/{chat['id']}/messages", headers=user, json={"question": "Revenue by region?"}).json()
    assert first["result"]["reply"] == "first"
    second = client.post(f"/api/chats/{chat['id']}/messages", headers=user, json={"question": "And the top one?"}).json()
    assert second["result"]["reply"] == "remembered"
    assert "Revenue by region?" in FakeModel.last_prompt


def test_failures_are_saved_too(client, user, manager, model_id):
    chat = start(client, user, model_id)
    client.put(f"/api/ai-models/{model_id}", headers=manager, json={"is_active": False})
    try:
        msg = client.post(f"/api/chats/{chat['id']}/messages", headers=user, json={"question": "Revenue?"})
        assert msg.status_code == 201
        assert msg.json()["status"] == "error" and "turned off" in msg.json()["error"]
        assert client.get(f"/api/chats/{chat['id']}", headers=user).json()["messages"][0]["status"] == "error"
    finally:
        client.put(f"/api/ai-models/{model_id}", headers=manager, json={"is_active": True})


def test_chats_are_private(client, user, manager, model_id):
    chat = start(client, user, model_id)
    assert client.get(f"/api/chats/{chat['id']}", headers=manager).status_code == 404
    assert client.post(f"/api/chats/{chat['id']}/messages", headers=manager, json={"question": "hi there"}).status_code == 404
    assert client.delete(f"/api/chats/{chat['id']}", headers=manager).status_code == 404
    assert all(c["id"] != chat["id"] for c in client.get("/api/chats", headers=manager).json())


def test_rename_and_delete(client, user, model_id):
    chat = start(client, user, model_id)
    assert client.patch(f"/api/chats/{chat['id']}", headers=user, json={"title": "Q1 review"}).json()["title"] == "Q1 review"
    assert client.delete(f"/api/chats/{chat['id']}", headers=user).status_code == 204
    assert client.get(f"/api/chats/{chat['id']}", headers=user).status_code == 404


def test_deleted_connection_is_not_swapped_for_sample_data(client, user, manager, model_id, business_db):
    conn = client.post("/api/connections", headers=manager, json={
        "name": f"Gone {uuid.uuid4().hex[:6]}", "db_type": "sqlite", "database": business_db}).json()
    client.put(f"/api/connections/{conn['id']}", headers=manager, json={"allowed_tables": ["main.orders"]})
    chat = start(client, user, model_id, source_id=conn["id"])
    client.delete(f"/api/connections/{conn['id']}", headers=manager)
    msg = client.post(f"/api/chats/{chat['id']}/messages", headers=user, json={"question": "Revenue by region?"}).json()
    assert msg["status"] == "error" and "no longer exists" in msg["error"]
    assert client.get(f"/api/chats/{chat['id']}", headers=user).json()["source_name"] == conn["name"]
