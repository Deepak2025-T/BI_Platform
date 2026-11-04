"""Saved chart colour palettes: making, editing, duplicating, sharing and deleting."""


def make(client, headers, name="Brand", colors=("#FF0000", "#00FF00"), **extra):
    res = client.post("/api/palettes", headers=headers, json={"name": name, "colors": list(colors), **extra})
    assert res.status_code == 201, res.text
    return res.json()


def test_a_palette_is_saved_and_listed(client, user):
    p = make(client, user, name="My blues", colors=["#00B4D8", "#0077B6", "#023E8A"])
    assert p["colors"] == ["#00B4D8", "#0077B6", "#023E8A"]
    assert p["can_edit"] is True and p["is_shared"] is False
    names = [x["name"] for x in client.get("/api/palettes", headers=user).json()]
    assert "My blues" in names


def test_colours_are_stored_as_hex_however_they_were_typed(client, user):
    p = make(client, user, name="Mixed", colors=["#f00", "rgb(0, 180, 216)", "red", "0D3B66"])
    assert p["colors"] == ["#FF0000", "#00B4D8", "#D64545", "#0D3B66"]


def test_a_colour_that_is_not_a_colour_is_refused(client, user):
    res = client.post("/api/palettes", headers=user, json={"name": "Bad", "colors": ["#FF0000", "banana"]})
    assert res.status_code == 422


def test_a_palette_needs_at_least_two_colours(client, user):
    res = client.post("/api/palettes", headers=user, json={"name": "Lonely", "colors": ["#FF0000"]})
    assert res.status_code == 422


def test_duplicating_gives_a_copy_with_its_own_name(client, user):
    first = make(client, user, name="House style")
    copy = client.post(f"/api/palettes/{first['id']}/duplicate", headers=user)
    assert copy.status_code == 201, copy.text
    assert copy.json()["name"] == "House style copy"
    assert copy.json()["colors"] == first["colors"]
    assert copy.json()["id"] != first["id"]
    # Duplicating the copy doesn't collide with it; the name is nudged instead of failing.
    again = client.post(f"/api/palettes/{first['id']}/duplicate", headers=user).json()
    assert again["name"] == "House style copy (2)"


def test_a_name_already_in_use_is_nudged_rather_than_refused(client, user):
    make(client, user, name="Twice")
    second = make(client, user, name="Twice")
    assert second["name"] == "Twice (2)"


def test_editing_changes_the_colours(client, user):
    p = make(client, user, name="Edit me")
    res = client.put(f"/api/palettes/{p['id']}", headers=user, json={"colors": ["#111111", "#222222", "#333333"]})
    assert res.status_code == 200, res.text
    assert res.json()["colors"] == ["#111111", "#222222", "#333333"]
    assert res.json()["name"] == "Edit me"


def test_someone_elses_private_palette_is_not_visible(client, user, manager):
    mine = make(client, user, name="Private to me")
    # A manager sees everything, so check with the other direction: the plain user and a palette
    # the manager keeps private.
    theirs = make(client, manager, name="Manager only")
    listed = [x["id"] for x in client.get("/api/palettes", headers=user).json()]
    assert mine["id"] in listed
    assert theirs["id"] not in listed
    assert client.get("/api/palettes", headers=manager).status_code == 200
    assert client.put(f"/api/palettes/{theirs['id']}", headers=user, json={"name": "Mine now"}).status_code == 404


def test_only_a_manager_can_share_a_palette(client, user, manager):
    refused = client.post("/api/palettes", headers=user,
                          json={"name": "Everyone", "colors": ["#FF0000", "#00FF00"], "is_shared": True})
    assert refused.status_code == 403
    shared = make(client, manager, name="Company colours", is_shared=True)
    assert shared["is_shared"] is True
    # Shared palettes show up for everybody, but not as theirs to change.
    row = next(x for x in client.get("/api/palettes", headers=user).json() if x["id"] == shared["id"])
    assert row["can_edit"] is False
    assert client.put(f"/api/palettes/{shared['id']}", headers=user, json={"name": "No"}).status_code == 403


def test_anyone_can_duplicate_a_shared_palette_and_owns_the_copy(client, user, manager):
    shared = make(client, manager, name="Shared to copy", is_shared=True)
    copy = client.post(f"/api/palettes/{shared['id']}/duplicate", headers=user)
    assert copy.status_code == 201, copy.text
    # The copy is private: sharing is a decision taken about the new palette, not inherited.
    assert copy.json()["is_shared"] is False
    assert copy.json()["can_edit"] is True


def test_deleting_removes_it(client, user):
    p = make(client, user, name="Temporary")
    assert client.delete(f"/api/palettes/{p['id']}", headers=user).status_code == 204
    assert client.put(f"/api/palettes/{p['id']}", headers=user, json={"name": "x"}).status_code == 404


def test_signing_in_is_required(client):
    assert client.get("/api/palettes").status_code == 401
