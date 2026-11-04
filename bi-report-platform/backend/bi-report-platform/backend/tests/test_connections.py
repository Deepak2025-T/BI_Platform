import uuid

import pytest

from app.config import settings


@pytest.fixture
def sqlite_connection(client, manager, business_db):
    res = client.post("/api/connections", headers=manager, json={
        "name": f"Business {uuid.uuid4().hex[:8]}", "db_type": "sqlite", "database": business_db})
    assert res.status_code == 201, res.text
    yield res.json()
    client.delete(f"/api/connections/{res.json()['id']}", headers=manager)


def test_users_cannot_manage_connections(client, user):
    assert client.get("/api/connections", headers=user).status_code == 403
    assert client.post("/api/connections", headers=user, json={
        "name": "x", "db_type": "sqlite", "database": "x.db"}).status_code == 403
    assert client.post("/api/connections/test", headers=user, json={"db_type": "sqlite", "database": "x.db"}).status_code == 403


def test_users_see_names_only(client, user, sqlite_connection):
    rows = client.get("/api/connections/available", headers=user).json()
    row = next(r for r in rows if r["id"] == sqlite_connection["id"])
    assert set(row) == {"id", "name", "db_type", "type_label", "status"}


def test_password_is_encrypted_and_never_returned(client, manager):
    res = client.post("/api/connections", headers=manager, json={
        "name": "Sales MySQL", "db_type": "mysql", "host": "db.local", "database": "sales",
        "username": "report_reader", "password": "s3cret!"})
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["has_password"] is True
    assert "s3cret!" not in res.text and "password" not in body
    listing = client.get("/api/connections", headers=manager).text
    assert "s3cret!" not in listing

    from app.database import SessionLocal
    from app.models import DataConnection
    with SessionLocal() as db:
        stored = db.get(DataConnection, body["id"]).password_encrypted
    assert stored and "s3cret!" not in stored

    # Leaving the password out keeps it; the old test result is cleared because details changed.
    updated = client.put(f"/api/connections/{body['id']}", headers=manager, json={"host": "db2.local"}).json()
    assert updated["has_password"] is True and updated["status"] == "untested"
    client.delete(f"/api/connections/{body['id']}", headers=manager)


def test_server_types_need_a_host(client, manager):
    res = client.post("/api/connections", headers=manager, json={"name": "No host", "db_type": "postgresql", "database": "x"})
    assert res.status_code == 422


def test_duplicate_names_are_rejected(client, manager, sqlite_connection):
    res = client.post("/api/connections", headers=manager, json={
        "name": sqlite_connection["name"].upper(), "db_type": "sqlite", "database": "other.db"})
    assert res.status_code == 409


def test_saved_connection_tests_green_and_lists_tables(client, manager, sqlite_connection):
    res = client.post(f"/api/connections/{sqlite_connection['id']}/test", headers=manager).json()
    assert res["ok"] is True, res["message"]
    names = {t["name"] for s in res["schemas"] for t in s["tables"]}
    assert {"orders", "customers", "big_orders"} <= names

    saved = next(c for c in client.get("/api/connections", headers=manager).json() if c["id"] == sqlite_connection["id"])
    assert saved["status"] == "ok" and saved["last_tested_at"]

    tables = client.get(f"/api/connections/{sqlite_connection['id']}/tables", headers=manager).json()
    assert tables[0]["schema"] == "main"


def test_choosing_allowed_tables(client, manager, sqlite_connection):
    res = client.put(f"/api/connections/{sqlite_connection['id']}", headers=manager,
                     json={"allowed_tables": ["main.orders", "main.orders", " main.customers "]}).json()
    assert res["allowed_tables"] == ["main.customers", "main.orders"]


def test_unreachable_server_fails_cleanly(client, manager):
    res = client.post("/api/connections/test", headers=manager, json={
        "db_type": "postgresql", "host": "127.0.0.1", "port": 1, "database": "nothing", "username": "u", "password": "p"})
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is False and body["message"]


def test_missing_connections_key_is_explained(client, manager, monkeypatch):
    monkeypatch.setattr(settings, "connections_key", "")
    res = client.post("/api/connections", headers=manager, json={
        "name": "Needs key", "db_type": "postgresql", "host": "h", "database": "d", "password": "pw"})
    assert res.status_code == 400
    assert "CONNECTIONS_KEY" in res.json()["detail"]
