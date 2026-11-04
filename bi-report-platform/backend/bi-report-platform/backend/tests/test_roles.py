"""Role rules that existed before connections: users, reports, templates and categories."""

import uuid


def unique(prefix: str) -> str:
    return f"{prefix} {uuid.uuid4().hex[:8]}"


# ---------- Users ----------

def test_only_managers_manage_users(client, user, manager):
    assert client.get("/api/users", headers=user).status_code == 403
    assert client.get("/api/users", headers=manager).status_code == 200


def test_manager_cannot_remove_own_access(client, manager):
    me = client.get("/api/auth/me", headers=manager).json()
    assert client.patch(f"/api/users/{me['id']}", headers=manager, json={"role": "user"}).status_code == 400


# ---------- Reports ----------

def test_drafts_are_private_until_published(client, user, manager, make_report):
    draft = make_report(manager, unique("Manager draft"))
    assert client.get(f"/api/reports/{draft['id']}", headers=user).status_code == 404
    client.post(f"/api/reports/{draft['id']}/publish", headers=manager)
    assert client.get(f"/api/reports/{draft['id']}", headers=user).status_code == 200


def test_users_cannot_change_other_peoples_reports(client, user, manager, make_report):
    report = make_report(manager, unique("Manager report"))
    client.post(f"/api/reports/{report['id']}/publish", headers=manager)
    assert client.put(f"/api/reports/{report['id']}", headers=user, json={"title": "x"}).status_code == 403
    assert client.delete(f"/api/reports/{report['id']}", headers=user).status_code == 403


def test_publish_with_category(client, user, make_report):
    cat = client.post("/api/categories", headers=user, json={"name": unique("Cat")}).json()
    report = make_report(user)
    published = client.post(f"/api/reports/{report['id']}/publish", headers=user, json={"category_id": cat["id"]}).json()
    assert published["status"] == "published" and published["category"]["id"] == cat["id"]
    assert client.post(f"/api/reports/{report['id']}/publish", headers=user, json={"category_id": 999999}).status_code == 400


# ---------- Templates ----------

def test_only_managers_share_templates(client, user, manager):
    body = {"name": unique("Tpl"), "prompt": "sales by region", "visibility": "shared"}
    assert client.post("/api/templates", headers=user, json=body).status_code == 403
    assert client.post("/api/templates", headers=manager, json=body).status_code == 201


def test_private_templates_stay_private(client, user, manager):
    t = client.post("/api/templates", headers=user, json={"name": unique("Mine"), "prompt": "sales by region"}).json()
    assert all(x["id"] != t["id"] for x in client.get("/api/templates", headers=manager).json())


def test_users_cannot_edit_builtin_templates(client, user):
    builtin = next(t for t in client.get("/api/templates", headers=user).json() if t["is_builtin"])
    assert builtin["can_edit"] is False
    assert client.put(f"/api/templates/{builtin['id']}", headers=user, json={"name": "x"}).status_code == 403


# ---------- Categories ----------

def test_category_names_are_unique(client, user, manager):
    name = unique("Finance")
    assert client.post("/api/categories", headers=user, json={"name": name}).status_code == 201
    assert client.post("/api/categories", headers=manager, json={"name": name.upper()}).status_code == 409


def test_only_creator_or_manager_edits_a_category(client, user, manager):
    cat = client.post("/api/categories", headers=manager, json={"name": unique("Ops")}).json()
    assert client.put(f"/api/categories/{cat['id']}", headers=user, json={"name": "x"}).status_code == 403
    assert client.delete(f"/api/categories/{cat['id']}", headers=user).status_code == 403


def test_deleting_a_category_keeps_its_reports(client, user, make_report):
    cat = client.post("/api/categories", headers=user, json={"name": unique("Temp")}).json()
    report = make_report(user)
    client.post(f"/api/reports/{report['id']}/publish", headers=user, json={"category_id": cat["id"]})
    assert client.delete(f"/api/categories/{cat['id']}", headers=user).status_code == 204
    assert client.get(f"/api/reports/{report['id']}", headers=user).json()["category"] is None


# ---------- Settings ----------

def test_setup_warnings_are_manager_only(client, user, manager):
    assert client.get("/api/admin/usage", headers=user).status_code == 403
    usage = client.get("/api/admin/usage", headers=manager).json()
    assert usage["warnings"] == []  # the test settings use a strong JWT secret and a connections key


def test_default_jwt_secret_is_flagged(client, manager, monkeypatch):
    from app.config import DEFAULT_JWT_SECRET, settings
    monkeypatch.setattr(settings, "jwt_secret", DEFAULT_JWT_SECRET)
    monkeypatch.setattr(settings, "connections_key", "")
    warnings = settings.setup_warnings()
    assert any("JWT_SECRET" in w for w in warnings) and any("CONNECTIONS_KEY" in w for w in warnings)
