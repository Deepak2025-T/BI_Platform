"""IBM OpenPages connections: sign-in, object types, OpenPages SQL checks, queries and dashboard filters,
against a small fake OpenPages REST API."""

import base64
import json
import re
import threading
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

import pytest

from app.connections import openpages
from app.datasources import QueryFailed
from app.openpages_templates import count_by, total
from app.routers import templates as templates_router
from app.connections.openpages import (UnsafeOpenPagesSQL, add_conditions, check_sql, has_or,
                                        query_types)

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
        if self.path == "/oauth/token-moved":  # same host: the hop is re-sent as a POST
            self.rfile.read(int(self.headers["Content-Length"]))  # drain, or the socket is reset
            self.send_response(302)
            self.send_header("Location", "/oauth/token")
            self.send_header("Content-Length", "0")
            return self.end_headers()
        if self.path == "/oauth/token-sso":  # a gateway sending the caller off to sign in
            self.rfile.read(int(self.headers["Content-Length"]))
            self.send_response(302)
            self.send_header("Location", "https://sso.example.com/login")
            self.send_header("Content-Length", "0")
            return self.end_headers()
        if self.path in ("/oauth/token", "/oauth/token-basic", "/oauth/token-html"):
            form = parse_qs(self.rfile.read(int(self.headers["Content-Length"])).decode())
            if form.get("grant_type") != ["client_credentials"]:
                return self._send(400, {"error": "unsupported_grant_type"})
            if self.path == "/oauth/token-html":  # a wrong URL: a sign-in page, not a token
                body = b"<html><body>Sign in</body></html>"
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                return self.wfile.write(body)
            if self.path == "/oauth/token-basic":
                # WebSphere Liberty's provider, which OpenPages uses: the client must be a Basic
                # header, and credentials in the body alone are not accepted.
                want = "Basic " + base64.b64encode(b"bi:oauth-secret").decode()
                if self.headers.get("Authorization") != want:
                    return self._send(401, {"error": "invalid_client",
                                            "error_description": "client authentication failed"})
                return self._send(200, {"access_token": "tok-123", "expires_in": 3600})
            if form.get("client_secret") == ["oauth-secret"]:
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
    """No brackets that are not needed. The Query Service's grammar is small, and a predicate in
    brackets it did not ask for comes back as "columnReference cannot be null" - which is what a
    whole report of filtered charts failed with."""
    c = ["[SOXIssue].[OPSS-Iss:Status] = 'O''Neil'"]
    assert add_conditions("SELECT [Name] FROM [SOXIssue]", c) == \
        "SELECT [Name] FROM [SOXIssue] WHERE [SOXIssue].[OPSS-Iss:Status] = 'O''Neil'"
    sql = "SELECT [Name], COUNT([Name]) FROM [SOXIssue] WHERE [Name] = 'a' OR [Name] = 'b' GROUP BY [Name]"
    # The query's own OR keeps its brackets: without them, ANDing a filter onto it would quietly
    # return different rows.
    assert add_conditions(sql, c) == ("SELECT [Name], COUNT([Name]) FROM [SOXIssue] WHERE "
                                      "([Name] = 'a' OR [Name] = 'b') AND [SOXIssue].[OPSS-Iss:Status] = 'O''Neil' "
                                      "GROUP BY [Name]")


def test_a_plain_where_is_left_unbracketed_when_a_filter_is_added():
    sql = "SELECT [Name] FROM [SOXIssue] WHERE [SOXIssue].[OPSS-Iss:Status] = 'Open'"
    assert add_conditions(sql, ["[SOXIssue].[OPSS-Iss:Priority] IN ('High', 'Low')"]) == (
        "SELECT [Name] FROM [SOXIssue] WHERE [SOXIssue].[OPSS-Iss:Status] = 'Open' "
        "AND [SOXIssue].[OPSS-Iss:Priority] IN ('High', 'Low')")


def test_a_condition_of_its_own_with_an_or_is_bracketed():
    sql = "SELECT [Name] FROM [SOXIssue]"
    assert add_conditions(sql, ["[A].[B] = 'a' OR [A].[B] = 'b'", "[A].[C] = 'c'"]) == (
        "SELECT [Name] FROM [SOXIssue] WHERE ([A].[B] = 'a' OR [A].[B] = 'b') AND [A].[C] = 'c'")


def test_an_empty_condition_never_reaches_the_query():
    """An empty WHERE is the one thing the Query Service will not forgive."""
    sql = "SELECT [Name] FROM [SOXIssue]"
    assert add_conditions(sql, ["", "   "]) == sql
    assert add_conditions(sql, ["", "[A].[B] = 'c'"]) == "SELECT [Name] FROM [SOXIssue] WHERE [A].[B] = 'c'"


def test_or_inside_brackets_or_quotes_is_not_a_top_level_or():
    assert not has_or("[A].[B] IN ('a', 'b')")
    assert not has_or("[A].[B] = 'OR'")
    assert not has_or("[A].[Or Something] = 'x'")
    assert has_or("[A].[B] = 'a' OR [A].[B] = 'b'")


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
    # The server's own words, not a guess: "invalid_client" is a wrong id or secret, and the
    # message has to say so, because the same failure used to read "no access_token".
    assert not res["ok"] and "invalid_client" in res["message"]


def test_oauth_against_a_server_that_wants_the_client_in_a_basic_header(client, manager, op_server):
    """WebSphere Liberty, which serves OpenPages' /oauth2/endpoint/<provider>/token, authenticates
    the client with a Basic header and ignores credentials sent only in the body."""
    body = {"db_type": "openpages", "host": op_server + "/grc/api", "password": "oauth-secret",
            "options": {"auth_type": "oauth2", "client_id": "bi",
                        "token_url": op_server + "/oauth/token-basic"}}
    assert client.post("/api/connections/test", headers=manager, json=body).json()["ok"]


def test_a_token_url_that_redirects_on_the_same_server_is_followed(client, manager, op_server):
    """A 302 to another path on the same host is a moved endpoint: re-POST there. Letting a client
    follow it would turn the POST into a GET and drop the form, which is why it is done by hand."""
    body = {"db_type": "openpages", "host": op_server + "/grc/api", "password": "oauth-secret",
            "options": {"auth_type": "oauth2", "client_id": "bi",
                        "token_url": op_server + "/oauth/token-moved"}}
    assert client.post("/api/connections/test", headers=manager, json=body).json()["ok"]


def test_a_token_url_that_redirects_off_the_server_keeps_the_secret(client, manager, op_server):
    """A redirect to a sign-in page must not be followed: the client secret would go to whoever
    answered. The message has to name where it was being sent."""
    body = {"db_type": "openpages", "host": op_server + "/grc/api", "password": "oauth-secret",
            "options": {"auth_type": "oauth2", "client_id": "bi",
                        "token_url": op_server + "/oauth/token-sso"}}
    res = client.post("/api/connections/test", headers=manager, json=body).json()
    assert not res["ok"]
    assert "sso.example.com" in res["message"] and "not sent there" in res["message"]


def test_a_token_url_that_answers_with_a_page_says_the_url_is_wrong(client, manager, op_server):
    body = {"db_type": "openpages", "host": op_server + "/grc/api", "password": "oauth-secret",
            "options": {"auth_type": "oauth2", "client_id": "bi",
                        "token_url": op_server + "/oauth/token-html"}}
    res = client.post("/api/connections/test", headers=manager, json=body).json()
    assert not res["ok"] and "token URL is probably wrong" in res["message"]


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
    # Plainly, with no brackets of its own: see test_filter_conditions_join_the_where.
    assert "WHERE [SOXIssue].[OPSS-Iss:Status] = 'Closed' GROUP BY" in FakeOpenPages.queries[-2]
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


def test_the_grc_reports_ship_as_templates(client, user):
    """The two reports in frontend/Template: Audit Plan Item Overview and the Action Item
    Monitoring Dashboard, filed under GRC in the Internal Audit and Operational Risk folders."""
    plan = _template(client, user, "OpenPages: Audit plan item overview")
    action = _template(client, user, "OpenPages: Action item monitoring dashboard")
    assert (plan["category"], plan["module"]) == ("GRC", "IAM")
    assert (action["category"], action["module"]) == ("GRC", "ORM")

    titles = [w["title"] for w in plan["layout"]["widgets"]]
    for part in ("status", "type", "risk level", "priority", "planned quarter", "auditable unit"):
        assert any(part in t.lower() for t in titles), part
    assert any(w["chart"]["type"] == "table" for w in plan["layout"]["widgets"])
    # Audit Plan Item refuses IS NULL on its own field group, so these counts must not ask.
    for w in plan["layout"]["widgets"]:
        if w["chart"]["type"] != "table":
            assert "IS NOT NULL" not in w["sql"]

    assert [w["chart"]["type"] for w in action["layout"]["widgets"]][:3] == ["kpi"] * 3
    assert any("ageing" in w["title"].lower() for w in action["layout"]["widgets"])


def test_the_orm_overview_is_the_two_pages_it_was_designed_as(client, user):
    """The ORM overview design is two pages: the standing picture, then what happened and what is
    being done about it. They ship as two templates, under GRC in the ORM folder."""
    first = _template(client, user, "ORM: Operational Risk Management — overview")
    second = _template(client, user, "ORM: Events, indicators and remediation")
    for t in (first, second):
        assert (t["category"], t["module"]) == ("GRC", "ORM")
        assert t["layout"]["source_type"] == "openpages"
        # A heading with nothing under it is dropped at build time; every one here has charts.
        assert any(w.get("kind") != "text" for w in t["layout"]["widgets"])

    titles = lambda t: [w["title"] for w in t["layout"]["widgets"]]
    for part in ("Risks by residual rating", "Design effectiveness", "Processes in scope",
                 "Entities in RCSA scope"):
        assert part in titles(first), part
    for part in ("Loss events by outcome", "KRIs by breach status", "Issues by priority",
                 "Action items by status"):
        assert part in titles(second), part
    # Beyond the business-entity band every module dashboard opens with, neither page repeats the
    # other's charts: the point of the split is that each answers its own question.
    band = {w["title"] for w in first["layout"]["widgets"][:5]}
    assert not (set(titles(first)) - band) & (set(titles(second)) - band)


def test_both_orm_overview_pages_write_sql_openpages_accepts(client, user):
    allowed = {f"openpages.{t}" for t in ("soxrisk", "soxcontrol", "soxprocess", "soxbusentity",
                                          "lossevent", "keyriskindicator", "soxissue", "actionitem")}
    for name in ("ORM: Operational Risk Management — overview", "ORM: Events, indicators and remediation"):
        for w in _template(client, user, name)["layout"]["widgets"]:
            if w.get("kind") == "text":
                continue
            assert check_sql(w["sql"], allowed), w["title"]
            assert " AS " not in w["sql"].upper()  # OpenPages SQL has no aliases


# ---------- Field names that differ between installations ----------

class PickyServer:
    """A connection that answers only queries naming the fields it has."""

    is_openpages = True

    def __init__(self, *known: str):
        self.known = set(known)
        self.asked: list[str] = []

    def run(self, sql: str):
        self.asked.append(sql)
        for ref in re.findall(r"\]\.\[([^\]]+)\]", sql):
            if ref not in self.known:
                raise QueryFailed(f"OP-60003: no field [{ref}] on this object type")
        return {"rows": [], "columns": []}


@pytest.fixture
def picky(monkeypatch):
    def make(*known):
        server = PickyServer(*known)
        monkeypatch.setattr(templates_router, "run_sql", lambda source, sql, *a, **k: server.run(sql))
        return server
    return make


def test_a_chart_falls_back_to_the_name_this_installation_uses(picky):
    server = picky("Resource ID", "OPSS-Risk-Qual:Residual Risk Rating")
    template = count_by("SOXRisk", ["OPSS-Risk:Residual Risk Rating", "OPSS-Risk-Qual:Residual Risk Rating"],
                        "Risks by residual rating")
    widget: dict = {"chart": dict(template["chart"])}
    assert templates_router.first_that_runs(None, template, widget) == ""
    assert "OPSS-Risk-Qual:Residual Risk Rating" in widget["sql"]
    # The axis follows the field that was actually used, or the chart would plot a column that
    # isn't in the result.
    assert widget["chart"]["x"] == "OPSS-Risk-Qual:Residual Risk Rating"
    assert len(server.asked) == 2  # the standard name first, then this installation's


def test_the_standard_name_is_used_when_it_works(picky):
    server = picky("Resource ID", "OPSS-Risk:Residual Risk Rating")
    template = count_by("SOXRisk", ["OPSS-Risk:Residual Risk Rating", "OPSS-Risk-Qual:Residual Risk Rating"],
                        "Risks by residual rating")
    widget: dict = {"chart": dict(template["chart"])}
    assert templates_router.first_that_runs(None, template, widget) == ""
    assert "OPSS-Risk:Residual Risk Rating" in widget["sql"]
    assert len(server.asked) == 1  # no second query once the first one answers


def test_a_field_by_none_of_its_names_is_still_left_out_and_says_why(picky):
    picky("Resource ID")
    template = count_by("SOXRisk", ["OPSS-Risk:Risk Domain", "OPSS-Rsk:Domain"], "Risks by domain")
    reason = templates_router.first_that_runs(None, template, {"chart": dict(template["chart"])})
    assert "OPSS-Rsk:Domain" in reason  # the last thing tried, so the message names a real attempt


def test_a_number_tile_tries_each_name_in_its_condition(picky):
    picky("Resource ID", "OPSS-Rsk:Status")
    template = total("SOXRisk", "Open risks",
                     [f"[SOXRisk].[OPSS-Risk:Status] <> 'Closed'", f"[SOXRisk].[OPSS-Rsk:Status] <> 'Closed'"])
    widget: dict = {"chart": dict(template["chart"])}
    assert templates_router.first_that_runs(None, template, widget) == ""
    assert "OPSS-Rsk:Status" in widget["sql"]


def test_a_heat_map_moves_both_of_its_fields_together(picky):
    """A grid names two fields. When the installation files one of them under another group name
    it files the other one there too, so the chart's columns have to follow its rows."""
    from app.openpages_modules import heat
    server = picky("Resource ID", "OPSS-Risk-Qual:Residual Risk Rating", "OPSS-Risk-Qual:Residual Likelihood")
    template = heat("SOXRisk", ["OPSS-Risk:Residual Risk Rating", "OPSS-Risk-Qual:Residual Risk Rating"],
                    ["OPSS-Risk:Residual Likelihood", "OPSS-Risk-Qual:Residual Likelihood"],
                    "Residual rating against residual likelihood")
    widget: dict = {"chart": dict(template["chart"])}
    assert templates_router.first_that_runs(None, template, widget) == ""
    assert widget["chart"]["x"] == "OPSS-Risk-Qual:Residual Risk Rating"
    assert widget["chart"]["legend"] == "OPSS-Risk-Qual:Residual Likelihood"
    assert len(server.asked) == 2


def test_the_alternatives_never_reach_the_saved_report(client, manager, op_connection):
    """alt_sql and alt_x belong to the template. A report keeps one query per chart."""
    t = _template(client, manager, "OpenPages: Issues and remediation")
    res = client.post(f"/api/templates/{t['id']}/build", headers=manager, json={"source_id": op_connection["id"]})
    assert res.status_code == 201, res.text
    for w in res.json()["report"]["config"]["widgets"]:
        assert "alt_sql" not in w and "alt_x" not in w
    client.delete(f"/api/reports/{res.json()['report']['id']}", headers=manager)


def test_a_list_under_the_entity_hierarchy_is_not_an_indirect_join():
    """The Query Service's indirect join may not select the ancestor's fields and needs a Resource
    ID filter on it, so "every X under its entity" cannot be written as one. [Location] is a system
    field holding that path, so one object type answers it."""
    from app.openpages_modules import rooted
    widget = rooted("SOXRisk", "Risks by entity", ["OPSS-Risk:Status"])
    assert "ANCESTOR(" not in widget["sql"] and "JOIN" not in widget["sql"]
    assert "[SOXRisk].[Location]" in widget["sql"]

    # A direct child may still be joined, and may name its parent.
    direct = rooted("SOXProcess", "Processes by entity", ["OPSS-Proc:Status"], direct=True)
    assert "ON PARENT([SOXBusEntity])" in direct["sql"] and "[SOXBusEntity].[Name]" in direct["sql"]


def test_no_shipped_template_selects_a_field_of_an_indirectly_joined_type():
    from app.openpages_modules import module_template_rows
    from app.openpages_templates import template_rows
    offenders = []
    for r in module_template_rows() + template_rows():
        for w in r["layout"]["widgets"]:
            for sql in [w.get("sql", "")] + list(w.get("alt_sql") or []):
                m = re.search(r"ON\s+ANCESTOR\(\[([^\]]+)\]\)", sql or "")
                if m and f"[{m.group(1)}]." in sql.split(" FROM ")[0]:
                    offenders.append((r["name"], w["title"]))
    assert offenders == [], offenders


def test_no_shipped_template_writes_a_python_list_into_its_sql():
    """A field given as several names must be expanded, not interpolated."""
    from app.openpages_modules import module_template_rows
    from app.openpages_templates import template_rows
    for r in module_template_rows() + template_rows():
        for w in r["layout"]["widgets"]:
            for sql in [w.get("sql", "")] + list(w.get("alt_sql") or []):
                assert "['" not in (sql or ""), (r["name"], w["title"])


def test_every_shipped_heat_map_names_the_two_columns_its_query_returns():
    """A grid is drawn by looking its two field names up in the result columns. A field written as
    a list of the names different installations use would leave the renderer looking for a column
    called "['OPSS-Risk:Residual Risk Rating', ...]", find none, and fall back to the rows - which
    is what "the heat map isn't generating" looks like from the outside."""
    from app.openpages_modules import module_template_rows
    from app.openpages_templates import template_rows
    seen = 0
    for r in module_template_rows() + template_rows():
        for w in r["layout"]["widgets"]:
            chart = w.get("chart") or {}
            if chart.get("type") != "heatmap":
                continue
            seen += 1
            where = (r["name"], w["title"])
            x, legend = chart.get("x"), chart.get("legend")
            assert isinstance(x, str) and x, where
            assert isinstance(legend, str) and legend, where
            assert x != legend, where
            # Each query names the pair that goes on the grid when that query is the one kept.
            variants = [w["sql"]] + list(w.get("alt_sql") or [])
            xs, legends = [x] + list(w.get("alt_x") or []), [legend] + list(w.get("alt_legend") or [])
            assert len(xs) == len(legends) == len(variants), where
            for sql, row_name, col_name in zip(variants, xs, legends):
                assert f"[{row_name}]" in sql and f"[{col_name}]" in sql, (where, sql)
    assert seen >= 4


class _Types:
    """An installation that has some of a type's fields and not others."""

    def __init__(self, **by_type):
        self.by_type = by_type
        self.asked: list[str] = []

    def type_fields(self, type_name):
        self.asked.append(type_name)
        return [{"name": n} for n in self.by_type[type_name]]


class _Source:
    is_openpages = True

    def __init__(self, client):
        self.client = client


def test_a_summary_table_is_written_against_the_fields_this_installation_has():
    """Six fields can't be settled one name at a time: a single name the server doesn't have fails
    the whole query. The object type's own field list settles all of them in one read."""
    from app.openpages_templates import summary_table
    from app.routers.templates import with_known_fields
    widget = summary_table("SOXRisk", "Risk summary",
                           ["Name",
                            ["OPSS-Risk:Risk Domain", "OPSS-Rsk:Domain"],
                            ["OPSS-Risk:Residual Risk Rating", "OPSS-Risk-Qual:Residual Risk Rating"],
                            ["OPSS-Risk:Nothing Here"]])
    client = _Types(SOXRisk=["Name", "OPSS-Rsk:Domain", "OPSS-Risk-Qual:Residual Risk Rating"])
    settled = with_known_fields(_Source(client), widget)
    assert settled["sql"] == ("SELECT [SOXRisk].[Name], [SOXRisk].[OPSS-Rsk:Domain], "
                              "[SOXRisk].[OPSS-Risk-Qual:Residual Risk Rating] FROM [SOXRisk]")
    # A field that is here under none of its names is simply not a column, rather than a query
    # that fails and takes the other five columns with it.
    assert "Nothing Here" not in settled["sql"]
    assert settled["alt_sql"] == []
    assert client.asked == ["SOXRisk"]  # one read, not one per name


def test_a_summary_table_falls_back_to_its_queries_when_the_field_list_cant_be_read():
    from app.openpages_templates import summary_table
    from app.routers.templates import with_known_fields

    class Broken:
        def type_fields(self, type_name):
            raise RuntimeError("that type isn't shared")

    widget = summary_table("SOXRisk", "Risk summary", ["Name", ["A", "B"]])
    settled = with_known_fields(_Source(Broken()), widget)
    assert settled["sql"] == widget["sql"] and settled["alt_sql"] == widget["alt_sql"]
    assert len(widget["alt_sql"]) == 1  # one query per name, tried in step


def test_a_multi_value_enum_is_read_rather_than_left_empty():
    """A field a record can hold several of at once keeps its values in multiEnumValue, not in
    "value". Reading only "value" left Domain null on every row, and a chart of it came out as a
    row of nameless bars."""
    from app.connections.openpages import _rows
    payload = {"rows": [{"fields": {"field": [
        {"dataType": "MULTI_VALUE_ENUM", "name": "OPSS-Rsk:Domain", "multiEnumValue": {"enumValue": [
            {"name": "Compliance", "localizedLabel": "Compliance"},
            {"name": "Operational", "localizedLabel": "Operational"},
        ]}},
        {"dataType": "ENUM_TYPE", "name": "OPSS-Risk:Status", "enumValue": {"name": "Open", "localizedLabel": "Open"}},
        {"dataType": "INTEGER_TYPE", "name": "Count_Resource ID", "value": 172},
        {"dataType": "BOOLEAN_TYPE", "name": "Empty"},
    ]}}]}
    assert _rows(payload) == [{"OPSS-Rsk:Domain": "Compliance, Operational", "OPSS-Risk:Status": "Open",
                               "Count_Resource ID": 172, "Empty": None}]

def test_equiti_orm_template(client, user):
    t = _template(client, user, "OpenPages: Equiti ORM dashboard")
    assert (t["category"], t["module"]) == ("GRC", "ORM")
    widgets = t["layout"]["widgets"]
    assert [w["title"] for w in widgets if w.get("kind") == "text"] == [
        "KRI overview and status", "Risk register and control assessment (RCSA)", "Risk incidents overview"]
    assert len(widgets) <= 30 and all(" AS " not in w["sql"].upper() for w in widgets)
    level1 = next(f for f in t["layout"]["filters"] if f["label"] == "Level 1 taxonomy")
    assert level1["types"] == ["KeyRiskIndicator", "SOXRisk", "LossEvent"]


def test_grc_executive_overview_template(client, user):
    t = _template(client, user, "OpenPages: GRC executive overview")
    assert t["category"] == "GRC"
    widgets = t["layout"]["widgets"]
    assert [w["title"] for w in widgets if w.get("kind") == "text"] == ["At a glance", "Where attention is needed", "To follow up"]
    kpis = [w for w in widgets if w.get("chart", {}).get("type") == "kpi"]
    assert len(kpis) == 8 and all(w["style"]["headBg"] == "#0D3B66" for w in kpis)
    assert all(" AS " not in w["sql"].upper() for w in widgets)
    assert all("[OPSS-Iss:" not in w["sql"] for w in widgets)  # issues use the OPSS-Issue fields


def test_builtin_dashboard_templates_stay_one_row_each(client, manager):
    """Starting again keeps one row per built-in dashboard template and brings its layout up to date."""
    from app.database import SessionLocal
    from app.models import ReportTemplate
    from app.openpages_templates import template_rows
    from app.routers.templates import ensure_builtin_templates
    name = "OpenPages: Equiti ORM dashboard"
    current = next(t for t in template_rows() if t["name"] == name)["layout"]
    with SessionLocal() as db:
        row = db.query(ReportTemplate).filter(ReportTemplate.name == name).one()
        row.layout = {"kind": "dashboard", "source_type": "openpages", "widgets": [], "filters": []}
        db.commit()
        ensure_builtin_templates(db)
        ensure_builtin_templates(db)
        rows = db.query(ReportTemplate).filter(ReportTemplate.name == name).all()
        assert len(rows) == 1 and rows[0].layout == current


def test_template_filter_across_object_types(client, manager, op_server):
    from app.database import SessionLocal
    from app.models import ReportTemplate
    c = client.post("/api/connections", headers=manager, json={
        "name": f"OP multi {uuid.uuid4().hex[:6]}", "db_type": "openpages", "host": op_server + "/grc/api",
        "username": "admin", "password": "op-pass", "options": {"auth_type": "basic"}}).json()
    client.put(f"/api/connections/{c['id']}", headers=manager, json={"allowed_tables": ["openpages.SOXIssue", "openpages.Finding"]})
    widgets = [
        {"title": "Issues", "sql": "SELECT COUNT([SOXIssue].[Resource ID]) FROM [SOXIssue]", "chart": {"type": "kpi", "x": "", "y": []}},
        {"title": "Findings", "sql": "SELECT [Finding].[Name] FROM [Finding]", "chart": {"type": "table", "x": "", "y": []}},
    ]
    with SessionLocal() as db:
        t = ReportTemplate(name=f"Multi {uuid.uuid4().hex[:6]}", prompt="test", color="#00AFAB", visibility="shared",
                           is_builtin=False, layout={"kind": "dashboard", "source_type": "openpages", "widgets": widgets,
                                                     "filters": [{"label": "Created", "kind": "date", "type": "SOXIssue",
                                                                  "types": ["SOXIssue", "Finding"], "field": "Creation Date"}]})
        db.add(t)
        db.commit()
        tid = t.id
    res = client.post(f"/api/templates/{tid}/build", headers=manager, json={"source_id": c["id"]})
    assert res.status_code == 201, res.text
    report = res.json()["report"]
    created = report["config"]["filters"][0]
    tables = {v["table"] for v in created["columns"].values()}
    assert len(created["columns"]) == 2 and tables == {"openpages.soxissue", "openpages.finding"}
    client.delete(f"/api/reports/{report['id']}", headers=manager)
    client.delete(f"/api/templates/{tid}", headers=manager)
    client.delete(f"/api/connections/{c['id']}", headers=manager)
