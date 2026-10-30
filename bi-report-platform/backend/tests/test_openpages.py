"""IBM OpenPages connections: sign-in, object types, OpenPages SQL checks, queries and dashboard filters,
against a small fake OpenPages REST API."""

import base64
import json
import threading
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

import pytest

from app.connections import openpages
from app.connections.openpages import UnsafeOpenPagesSQL, add_conditions, check_sql, query_types

BASIC = "Basic " + base64.b64encode(b"admin:op-pass").decode()
ISSUES = [("Server patching late", "Open"), ("Vendor review missing", "Open"), ("Badge access", "Closed")]


class FakeOpenPages(BaseHTTPRequestHandler):
    queries: list[str] = []

    def log_message(self, *args):
        pass

    def _send(self, code: int, body):
        data = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        if self.path == "/oauth/token":
            form = parse_qs(self.rfile.read(int(self.headers["Content-Length"])).decode())
            if form.get("client_secret") == ["oauth-secret"] and form.get("grant_type") == ["client_credentials"]:
                return self._send(200, {"access_token": "tok-123", "expires_in": 3600})
            return self._send(401, {"error": "invalid_client"})
        self._send(404, {})

    def do_GET(self):
        if self.headers.get("Authorization") not in (BASIC, "Bearer tok-123"):
            return self._send(401, {"message": "Unauthorized"})
        url = urlparse(self.path)
        if url.path == "/grc/api/types":
            return self._send(200, [{"name": "SOXIssue"}, {"name": "Finding"}, {"name": "SOXBusEntity"}])
        if url.path == "/grc/api/types/SOXIssue":
            return self._send(200, {"name": "SOXIssue", "fieldDefinitions": {"fieldDefinition": [
                {"name": "OPSS-Iss:Status", "dataType": "ENUM_TYPE",
                 "enumValues": {"enumValue": [{"name": "Open"}, {"name": "Closed"}]}}]}})
        if url.path == "/grc/api/query":
            q = parse_qs(url.query)["q"][0]
            FakeOpenPages.queries.append(q)
            rows = [(n, s) for n, s in ISSUES if "'Closed'" not in q or s == "Closed"]
            if "COUNT(" in q:
                counts = {}
                for _, s in rows:
                    counts[s] = counts.get(s, 0) + 1
                return self._send(200, {"rows": [{"fields": {"field": [
                    {"name": "OPSS-Iss:Status", "value": s}, {"name": "Count_Resource ID", "value": str(n)}]}}
                    for s, n in counts.items()]})
            return self._send(200, {"rows": [{"fields": {"field": [
                {"name": "Name", "value": n}, {"name": "OPSS-Iss:Status", "value": {"name": s}}]}} for n, s in rows]})
        self._send(404, {"message": "Not found"})


@pytest.fixture(scope="module")
def op_server():
    server = HTTPServer(("127.0.0.1", 0), FakeOpenPages)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()


@pytest.fixture
def op_connection(client, manager, op_server):
    res = client.post("/api/connections", headers=manager, json={
        "name": f"OpenPages {uuid.uuid4().hex[:6]}", "db_type": "openpages", "host": op_server + "/grc/api/query",
        "username": "admin", "password": "op-pass", "options": {"auth_type": "basic", "audit_name": "Equiti FA 2024"}})
    assert res.status_code == 201, res.text
    c = res.json()
    res = client.put(f"/api/connections/{c['id']}", headers=manager, json={"allowed_tables": ["openpages.SOXIssue"]})
    assert res.status_code == 200, res.text
    yield res.json()
    client.delete(f"/api/connections/{c['id']}", headers=manager)


# ---------- The SQL check ----------

ALLOWED = {"openpages.soxissue", "openpages.soxbusentity"}


def test_plain_openpages_selects_pass():
    sql = ("SELECT [SOXIssue].[Name], [SOXBusEntity].[Name] FROM [SOXIssue] JOIN [SOXBusEntity] ON CHILD([SOXIssue]) "
           "WHERE [SOXBusEntity].[Name] LIKE '%DELETE me; -- not code%'")
    assert check_sql(sql + ";", ALLOWED) == sql
    assert query_types(sql) == ["SOXIssue", "SOXBusEntity"]


@pytest.mark.parametrize("sql, reason", [
    ("UPDATE [SOXIssue] SET [Name] = 'x'", "SELECT"),
    ("SELECT [Name] FROM [SOXIssue]; SELECT [Name] FROM [SOXIssue]", "one statement"),
    ("SELECT [Name] FROM [SOXIssue] -- hi", "comments"),
    ("SELECT [Name] FROM [SOXIssue] WHERE [Resource ID] IN (SELECT [Resource ID] FROM [SOXIssue])", "Subqueries"),
    ("SELECT [Name] FROM [SOXIssue] UNION SELECT [Name] FROM [SOXIssue]", "UNION"),
    ("SELECT [Name] FROM [SOXIssue] LIMIT 5", "LIMIT"),
    ("SELECT [Name] FROM [Finding]", "isn't one of the types"),
    ("SELECT Name FROM SOXIssue", "brackets"),
    ("SELECT [Name] FROM [SOXIssue] WHERE [Name] = 'open", "unclosed"),
    ("SELECT COUNT([SOXIssue].[Resource ID]) AS [n] FROM [SOXIssue]", "AS"),
    ("SELECT DISTINCT [SOXIssue].[Name] FROM [SOXIssue]", "DISTINCT"),
    ("SELECT MAX([SOXIssue].[Creation Date]) FROM [SOXIssue]", "no MAX function"),
    ("SELECT [SOXBusEntity].[Name], COUNT([SOXIssue].[Resource ID]) FROM [SOXBusEntity] "
     "JOIN [SOXIssue] ON PARENT([SOXBusEntity]) GROUP BY [SOXBusEntity].[Name]", "one object type"),
])


def test_unsafe_openpages_sql_is_refused(sql, reason):
    with pytest.raises(UnsafeOpenPagesSQL, match=reason):
        check_sql(sql, ALLOWED)


def test_joined_fields_with_the_same_name_get_their_type():
    sql = "SELECT [AuditProgram].[Name], [Finding].[Name], [Finding].[OPSS-Finding:Status] FROM [AuditProgram] JOIN [Finding] ON PARENT([AuditProgram])"
    assert openpages.select_labels(sql) == ["AuditProgram Name", "Finding Name", ""]
    payload = {"rows": [{"fields": {"field": [{"name": "Name", "value": "Audit A"}, {"name": "Name", "value": "Finding 1"},
                                              {"name": "OPSS-Finding:Status", "enumValue": {"name": "Open"}}]}}]}
    assert openpages._rows(payload, openpages.select_labels(sql)) == [
        {"AuditProgram Name": "Audit A", "Finding Name": "Finding 1", "OPSS-Finding:Status": "Open"}]


def test_filter_conditions_join_the_where():
    c = ["[SOXIssue].[OPSS-Iss:Status] = 'O''Neil'"]
    assert add_conditions("SELECT [Name] FROM [SOXIssue]", c) == \
        "SELECT [Name] FROM [SOXIssue] WHERE ([SOXIssue].[OPSS-Iss:Status] = 'O''Neil')"
    sql = "SELECT [Name], COUNT([Name]) FROM [SOXIssue] WHERE [Name] = 'a' OR [Name] = 'b' GROUP BY [Name]"
    assert add_conditions(sql, c) == ("SELECT [Name], COUNT([Name]) FROM [SOXIssue] WHERE "
                                      "([SOXIssue].[OPSS-Iss:Status] = 'O''Neil') AND ([Name] = 'a' OR [Name] = 'b') GROUP BY [Name]")


def test_api_url_is_normalized():
    assert openpages.normalize_base("https://op.example.com/grc/api/query/") == "https://op.example.com/grc/api"
    assert openpages.normalize_base("https://op.example.com") == "https://op.example.com/grc/api"
    with pytest.raises(ValueError):
        openpages.normalize_base("http://op.example.com/grc/api")


# ---------- Through the API ----------

def test_connection_signs_in_and_lists_object_types(client, manager, op_connection):
    assert op_connection["host"].endswith("/grc/api")
    assert op_connection["type_label"] == "IBM OpenPages"
    assert "op-pass" not in json.dumps(op_connection)
    res = client.post(f"/api/connections/{op_connection['id']}/test", headers=manager).json()
    assert res["ok"], res
    assert "3 object types" in res["message"]
    assert [t["name"] for t in res["schemas"][0]["tables"]] == ["Finding", "SOXBusEntity", "SOXIssue"]


def test_wrong_password_fails_the_test(client, manager, op_server):
    res = client.post("/api/connections/test", headers=manager, json={
        "db_type": "openpages", "host": op_server + "/grc/api", "username": "admin", "password": "wrong",
        "options": {"auth_type": "basic"}}).json()
    assert not res["ok"] and "HTTP 401" in res["message"]


def test_oauth_client_credentials(client, manager, op_server):
    body = {"db_type": "openpages", "host": op_server + "/grc/api", "password": "oauth-secret",
            "options": {"auth_type": "oauth2", "client_id": "bi", "token_url": op_server + "/oauth/token"}}
    assert client.post("/api/connections/test", headers=manager, json=body).json()["ok"]
    body["password"] = "nope"
    res = client.post("/api/connections/test", headers=manager, json=body).json()
    assert not res["ok"] and "token server refused" in res["message"]


def test_mtls_private_key_is_never_returned(client, manager, op_server):
    res = client.post("/api/connections", headers=manager, json={
        "name": f"OP mTLS {uuid.uuid4().hex[:6]}", "db_type": "openpages", "host": op_server,
        "client_key": "-----BEGIN PRIVATE KEY-----secret-key-----END PRIVATE KEY-----",
        "options": {"auth_type": "mtls", "client_cert": "-----BEGIN CERTIFICATE-----x-----END CERTIFICATE-----"}})
    assert res.status_code == 201, res.text
    assert res.json()["options"]["has_client_key"] is True
    listing = client.get("/api/connections", headers=manager).text
    assert "secret-key" not in listing and "client_key_encrypted" not in listing
    client.delete(f"/api/connections/{res.json()['id']}", headers=manager)


def test_dashboard_runs_openpages_sql_with_filters(client, manager, op_connection):
    FakeOpenPages.queries.clear()
    widgets = [
        {"id": "w1", "title": "Issues by status", "sql":
         "SELECT [SOXIssue].[OPSS-Iss:Status], COUNT([SOXIssue].[Resource ID]) FROM [SOXIssue] "
         "GROUP BY [SOXIssue].[OPSS-Iss:Status]", "chart": {"type": "bar", "x": "OPSS-Iss:Status", "y": ["Count_Resource ID"]}},
        {"id": "w2", "title": "Issues", "sql": "SELECT [SOXIssue].[Name], [SOXIssue].[OPSS-Iss:Status] FROM [SOXIssue]",
         "chart": {"type": "table", "x": "", "y": []}},
    ]
    res = client.post("/api/assistant/save", headers=manager, json={
        "source_id": op_connection["id"], "title": "OpenPages issues", "widgets": widgets})
    assert res.status_code == 201, res.text
    report = res.json()
    saved = report["config"]["widgets"]  # saving gives each chart a new id
    w1, w2 = saved[0]["id"], saved[1]["id"]
    widgets = [{**w, "id": s["id"]} for w, s in zip(widgets, saved)]

    data = client.post(f"/api/reports/{report['id']}/data", headers=manager, json={"refresh": True}).json()
    by_id = {w["id"]: w for w in data["widgets"]}
    assert by_id[w1]["ok"], by_id[w1]
    assert sorted(by_id[w1]["rows"]) == [["Closed", 1], ["Open", 2]]  # counts come back as numbers
    assert by_id[w2]["rows"][0] == ["Server patching late", "Open"]

    # A category filter, with columns picked by hand; its choices come from the field definition.
    cols = client.post(f"/api/reports/{report['id']}/filters/columns", headers=manager, json={"widgets": widgets}).json()
    assert "OPSS-Iss:Status" in [c["name"] for c in cols[w1][0]["columns"]]
    f = client.post(f"/api/reports/{report['id']}/filters/manual", headers=manager, json={
        "label": "Status", "kind": "category", "widgets": widgets,
        "columns": {w1: {"table": "openpages.SOXIssue", "column": "OPSS-Iss:Status"},
                    w2: {"table": "openpages.SOXIssue", "column": "OPSS-Iss:Status"}}}).json()
    assert f["options"] == ["Closed", "Open"] and set(f["columns"]) == {w1, w2}
    config = {**report["config"], "filters": [f]}
    assert client.put(f"/api/reports/{report['id']}", headers=manager, json={"config": config}).status_code == 200

    data = client.post(f"/api/reports/{report['id']}/data", headers=manager,
                       json={"filters": {f["id"]: {"values": ["Closed"]}}, "refresh": True}).json()
    by_id = {w["id"]: w for w in data["widgets"]}
    assert by_id[w1]["rows"] == [["Closed", 1]] and by_id[w1]["filtered"] == [f["id"]]
    assert "WHERE ([SOXIssue].[OPSS-Iss:Status] = 'Closed') GROUP BY" in FakeOpenPages.queries[-2]
    client.delete(f"/api/reports/{report['id']}", headers=manager)


def test_unsafe_sql_cannot_be_saved(client, manager, op_connection):
    res = client.post("/api/assistant/save", headers=manager, json={
        "source_id": op_connection["id"], "title": "Bad", "widgets": [
            {"id": "w1", "title": "x", "sql": "DELETE FROM [SOXIssue]", "chart": {"type": "table", "x": "", "y": []}}]})
    assert res.status_code == 400 and "SELECT" in res.json()["detail"]


def test_model_gets_openpages_guide_and_fields(client, manager, op_connection):
    from app.database import SessionLocal
    from app.datasources import describe, get_source
    with SessionLocal() as db:
        text = describe(get_source(db, op_connection["id"]))
    assert "Wrap EVERY object type and field in square brackets" in text
    assert "[OPSS-Iss:Status] enum  -- values: 'Open', 'Closed'" in text
    assert "Default audit" in text and "'Equiti FA 2024'" in text


# ---------- Dashboard templates ----------

def _template(client, headers, name):
    return next(t for t in client.get("/api/templates", headers=headers).json() if t["name"] == name)


def test_openpages_templates_are_built_in(client, user):
    names = [t["name"] for t in client.get("/api/templates", headers=user).json()]
    assert "OpenPages: Audit findings" in names and "OpenPages: Controls effectiveness" in names
    t = _template(client, user, "OpenPages: Issues and remediation")
    assert t["is_builtin"] and t["layout"]["kind"] == "dashboard" and t["layout"]["source_type"] == "openpages"
    for w in t["layout"]["widgets"]:
        assert " AS " not in w["sql"].upper()  # OpenPages SQL has no aliases


def test_build_dashboard_from_template(client, manager, op_connection):
    t = _template(client, manager, "OpenPages: Issues and remediation")
    res = client.post(f"/api/templates/{t['id']}/build", headers=manager, json={"source_id": op_connection["id"]})
    assert res.status_code == 201, res.text
    body = res.json()
    report = body["report"]
    assert report["title"] == "Issues and remediation" and report["status"] == "draft"
    config = report["config"]
    assert config["kind"] == "dashboard" and config["source_id"] == op_connection["id"]
    assert len(config["widgets"]) == len([w for w in t["layout"]["widgets"] if w.get("kind") != "text"]) - len(body["skipped"])
    # The date filter maps to the system field every chart's type has.
    created = next(f for f in config["filters"] if f["label"] == "Created")
    assert set(created["columns"]) == {w["id"] for w in config["widgets"]}
    client.delete(f"/api/reports/{report['id']}", headers=manager)


def test_template_needs_its_object_types_and_connection_type(client, manager, op_connection):
    controls = _template(client, manager, "OpenPages: Controls effectiveness")
    res = client.post(f"/api/templates/{controls['id']}/build", headers=manager, json={"source_id": op_connection["id"]})
    assert res.status_code == 400 and "[SOXControl] isn't one of the types" in res.json()["detail"]
    res = client.post(f"/api/templates/{controls['id']}/build", headers=manager, json={"source_id": None})
    assert res.status_code == 400 and "IBM OpenPages" in res.json()["detail"]
