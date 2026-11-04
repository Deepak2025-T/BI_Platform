"""AI models: managing them, the picker, and asking a question with a chosen model.

A tiny fake server stands in for Ollama and for an OpenAI-compatible server, so these tests
exercise the real HTTP code without needing a model installed.
"""

import json
import threading
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from app.routers import query as query_router


def _answer(system: str, user: str) -> dict:
    if "connectivity check" in system:
        return {"reply": "OK"}
    if "churn" in user.lower():
        return {"answerable": False, "reason": "There is no customer or churn data.",
                "period": "q1_2024", "measure": "net", "date_col": "sale_date"}
    return {"answerable": True, "reason": "gross revenue for Q4 2023", "period": "q4_2023",
            "measure": "gross", "date_col": "sale_date"}


class FakeModelServer(BaseHTTPRequestHandler):
    def _send(self, body: dict, code: int = 200):
        data = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):  # noqa: N802
        if self.path == "/api/tags":
            self._send({"models": [{"name": "qwen2.5-coder:14b"}, {"name": "llama3.1:8b"}]})
        elif self.path == "/v1/models":
            self._send({"data": [{"id": "local-model"}]})
        else:
            self._send({}, 404)

    def do_POST(self):  # noqa: N802
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        system, user = body["messages"][0]["content"], body["messages"][1]["content"]
        if self.path == "/api/chat":
            if body["model"] == "missing-model":
                self._send({"error": "model not found"}, 404)
                return
            self._send({"message": {"role": "assistant", "content": json.dumps(_answer(system, user))}})
        elif self.path == "/v1/chat/completions":
            # Wrapped in a code fence, as some local models do.
            text = "Sure:\n```json\n" + json.dumps(_answer(system, user)) + "\n```"
            self._send({"choices": [{"message": {"role": "assistant", "content": text}}]})
        else:
            self._send({}, 404)

    def log_message(self, *args):
        pass


@pytest.fixture(scope="module")
def fake_server():
    server = HTTPServer(("127.0.0.1", 0), FakeModelServer)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()


@pytest.fixture
def ollama_model(client, manager, fake_server):
    res = client.post("/api/ai-models", headers=manager, json={
        "name": f"Local {uuid.uuid4().hex[:6]}", "provider": "ollama", "model": "qwen2.5-coder:14b",
        "base_url": fake_server})
    assert res.status_code == 201, res.text
    yield res.json()
    client.delete(f"/api/ai-models/{res.json()['id']}", headers=manager)


@pytest.fixture
def fake_run_query(monkeypatch):
    """run_query needs PostgreSQL; echo the chosen settings instead."""
    monkeypatch.setattr(query_router, "run_query", lambda db, params: {"params": params.model_dump()})


def test_users_cannot_manage_models(client, user):
    assert client.get("/api/ai-models", headers=user).status_code == 403
    assert client.post("/api/ai-models", headers=user, json={
        "name": "x", "provider": "ollama", "model": "m", "base_url": "http://x"}).status_code == 403


def test_picker_shows_active_models_only_without_details(client, user, manager, ollama_model):
    rows = client.get("/api/ai-models/available", headers=user).json()
    row = next(r for r in rows if r["id"] == ollama_model["id"])
    assert set(row) == {"id", "name", "provider", "provider_label", "is_default"}
    client.put(f"/api/ai-models/{ollama_model['id']}", headers=manager, json={"is_active": False})
    assert all(r["id"] != ollama_model["id"] for r in client.get("/api/ai-models/available", headers=user).json())


def test_api_key_is_required_encrypted_and_never_returned(client, manager):
    no_key = {"name": "Claude", "provider": "anthropic", "model": "claude-opus-5-5"}
    assert client.post("/api/ai-models", headers=manager, json=no_key).status_code == 422
    res = client.post("/api/ai-models", headers=manager, json={**no_key, "api_key": "sk-ant-secret-123"})
    assert res.status_code == 201
    assert res.json()["has_api_key"] is True and "sk-ant-secret-123" not in res.text
    assert "sk-ant-secret-123" not in client.get("/api/ai-models", headers=manager).text
    client.delete(f"/api/ai-models/{res.json()['id']}", headers=manager)


def test_only_one_default(client, manager, ollama_model, fake_server):
    other = client.post("/api/ai-models", headers=manager, json={
        "name": f"Other {uuid.uuid4().hex[:6]}", "provider": "ollama", "model": "llama3.1:8b",
        "base_url": fake_server, "is_default": True}).json()
    models = {m["id"]: m for m in client.get("/api/ai-models", headers=manager).json()}
    assert models[other["id"]]["is_default"] and sum(m["is_default"] for m in models.values()) == 1
    off = client.put(f"/api/ai-models/{other['id']}", headers=manager, json={"is_active": False}).json()
    assert off["is_default"] is False
    assert client.put(f"/api/ai-models/{other['id']}", headers=manager, json={"is_default": True}).status_code == 400
    client.delete(f"/api/ai-models/{other['id']}", headers=manager)


def test_test_and_discover(client, manager, ollama_model, fake_server):
    res = client.post(f"/api/ai-models/{ollama_model['id']}/test", headers=manager).json()
    assert res["ok"] is True, res["message"]
    saved = next(m for m in client.get("/api/ai-models", headers=manager).json() if m["id"] == ollama_model["id"])
    assert saved["status"] == "ok"
    names = client.post("/api/ai-models/discover", headers=manager, json={"provider": "ollama", "base_url": fake_server}).json()
    assert "qwen2.5-coder:14b" in names


def test_missing_ollama_model_is_explained(client, manager, fake_server):
    res = client.post("/api/ai-models/test", headers=manager, json={
        "provider": "ollama", "model": "missing-model", "base_url": fake_server}).json()
    assert res["ok"] is False and "ollama pull missing-model" in res["message"]


def test_unreachable_server_fails_cleanly(client, manager):
    res = client.post("/api/ai-models/test", headers=manager, json={
        "provider": "ollama", "model": "m", "base_url": "http://127.0.0.1:1"}).json()
    assert res["ok"] is False and "connect" in res["message"].lower()


def test_question_uses_the_chosen_model(client, user, ollama_model, fake_run_query):
    res = client.post("/api/query/generate", headers=user, json={
        "prompt": "How did gross sales do over the holidays?", "model_id": ollama_model["id"]})
    assert res.status_code == 200, res.text
    body = res.json()
    # The keyword engine would have chosen q1_2024 and net; the model read the question.
    assert body["params"]["period"] == "q4_2023" and body["params"]["measure"] == "gross"
    assert body["model"] == ollama_model["name"]
    assert body["attempts"][0]["ok"] and ollama_model["name"] in body["attempts"][0]["message"]


def test_model_can_decline_a_question(client, user, ollama_model):
    res = client.post("/api/query/generate", headers=user, json={
        "prompt": "Show customer churn by signup cohort", "model_id": ollama_model["id"]})
    assert res.status_code == 422
    assert res.json()["detail"]["reason"] == "There is no customer or churn data."


def test_unreachable_model_falls_back_to_builtin_engine(client, manager, user, fake_run_query):
    m = client.post("/api/ai-models", headers=manager, json={
        "name": f"Down {uuid.uuid4().hex[:6]}", "provider": "ollama", "model": "m", "base_url": "http://127.0.0.1:1"}).json()
    body = client.post("/api/query/generate", headers=user, json={"prompt": "revenue by region", "model_id": m["id"]}).json()
    assert body["attempts"][0]["ok"] is False and "built-in" in body["attempts"][0]["message"]
    assert body["model"] is None
    client.delete(f"/api/ai-models/{m['id']}", headers=manager)


def test_turned_off_model_is_refused(client, manager, user, ollama_model):
    client.put(f"/api/ai-models/{ollama_model['id']}", headers=manager, json={"is_active": False})
    res = client.post("/api/query/generate", headers=user, json={"prompt": "revenue by region", "model_id": ollama_model["id"]})
    assert res.status_code == 400


def test_openai_compatible_server(client, manager, user, fake_server, fake_run_query):
    m = client.post("/api/ai-models", headers=manager, json={
        "name": f"LM Studio {uuid.uuid4().hex[:6]}", "provider": "openai_compatible", "model": "local-model",
        "base_url": f"{fake_server}/v1"}).json()
    assert client.post(f"/api/ai-models/{m['id']}/test", headers=manager).json()["ok"] is True
    body = client.post("/api/query/generate", headers=user, json={"prompt": "gross sales Q4", "model_id": m["id"]}).json()
    assert body["params"]["measure"] == "gross"
    client.delete(f"/api/ai-models/{m['id']}", headers=manager)


def test_no_model_uses_builtin_engine(client, user, fake_run_query):
    body = client.post("/api/query/generate", headers=user, json={"prompt": "revenue by region"}).json()
    assert body["model"] is None and "built-in" in body["attempts"][0]["message"]


class _FakeClaude:
    """Stands in for anthropic.Anthropic and records the request it would send."""
    calls: list = []

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.messages = self._Messages(plain=True)
        self.beta = type("Beta", (), {"messages": self._Messages(plain=False)})()

    class _Messages:
        def __init__(self, plain: bool):
            self.plain = plain

        def create(self, **request):
            _FakeClaude.calls.append({"plain": self.plain, **request})
            block = type("Block", (), {"type": "text", "text": json.dumps({"reply": "OK"})})()
            return type("Response", (), {"stop_reason": "end_turn", "content": [block]})()


@pytest.mark.parametrize("model,uses_fallback", [("claude-opus-5-5", True), ("claude-haiku-5-5", False)])
def test_claude_request_shape(monkeypatch, model, uses_fallback):
    from app.ai import providers
    monkeypatch.setattr(providers.anthropic, "Anthropic", _FakeClaude)
    _FakeClaude.calls.clear()
    ms, reply = providers.ping(providers.ModelSpec(provider="anthropic", model=model, api_key="k"))
    assert reply == "OK"
    call = _FakeClaude.calls[0]
    assert call["model"] == model and call["output_config"]["format"]["type"] == "json_schema"
    assert call["output_config"]["effort"] == "low"
    assert call["plain"] is (not uses_fallback)
    if uses_fallback:
        assert call["fallbacks"] == "default" and call["betas"] == ["server-side-fallback-2026-07-01"]
