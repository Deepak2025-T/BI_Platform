"""
The questions the Ask page suggests for a database.

These are worked out from the columns, not from a model, so they can be checked exactly: the
point of each test is that a suggestion names something the table really holds.
"""

import sqlite3
import uuid

import pytest

from app.database import SessionLocal
from app.datasources import get_source
from app.prompt_ideas import MAX_IDEAS, ideas_for


@pytest.fixture(scope="module")
def shop(tmp_path_factory) -> str:
    path = (tmp_path_factory.mktemp("ideas") / "shop.db").as_posix()
    con = sqlite3.connect(path)
    con.executescript("""
        CREATE TABLE orders (id INTEGER PRIMARY KEY, region TEXT, customer_name TEXT,
                             revenue REAL, order_date DATE);
        CREATE TABLE people (id INTEGER PRIMARY KEY, full_name TEXT, department TEXT);
        INSERT INTO orders (region, customer_name, revenue, order_date)
            VALUES ('North', 'Asha', 100, '2024-01-15');
        INSERT INTO people (full_name, department) VALUES ('Asha', 'Sales');
    """)
    con.commit()
    con.close()
    return path


@pytest.fixture(scope="module")
def source(client, manager, shop):
    c = client.post("/api/connections", headers=manager, json={
        "name": f"Ideas {uuid.uuid4().hex[:6]}", "db_type": "sqlite", "database": shop}).json()
    client.put(f"/api/connections/{c['id']}", headers=manager,
               json={"allowed_tables": ["main.orders", "main.people"]})
    db = SessionLocal()
    try:
        yield get_source(db, c["id"]), c["id"]
    finally:
        db.close()
        client.delete(f"/api/connections/{c['id']}", headers=manager)


def test_the_ideas_name_real_columns(source):
    src, _ = source
    ideas = ideas_for(src)
    assert ideas, "a table with a number, a date and something to group by should suggest something"
    assert any("revenue" in i and "region" in i for i in ideas)
    assert any("monthly" in i.lower() for i in ideas)


def test_a_key_is_never_suggested_as_the_thing_to_add_up(source):
    src, _ = source
    assert not any(" id " in i or i.endswith(" id") for i in ideas_for(src))


def test_free_text_is_a_last_resort_for_grouping(source):
    """Grouping by a name draws one bar per row, so region wins while region exists."""
    src, _ = source
    orders = [i for i in ideas_for(src) if "orders" in i]
    assert orders and not any("customer name" in i for i in orders)


def test_every_table_gets_a_turn_before_any_gets_a_second(source):
    src, _ = source
    ideas = ideas_for(src)
    assert "people" in ideas[1], f"the second idea should be about the other table: {ideas}"


def test_there_are_never_more_than_a_handful(source):
    src, _ = source
    assert len(ideas_for(src)) <= MAX_IDEAS


def test_a_table_that_cannot_be_read_is_skipped(client, manager, source):
    """A shared table that has since been dropped shouldn't stop the others suggesting anything."""
    src, source_id = source
    client.put(f"/api/connections/{source_id}", headers=manager,
               json={"allowed_tables": ["main.orders", "main.gone"]})
    db = SessionLocal()
    try:
        assert any("revenue" in i for i in ideas_for(get_source(db, source_id)))
    finally:
        db.close()
        client.put(f"/api/connections/{source_id}", headers=manager,
                   json={"allowed_tables": ["main.orders", "main.people"]})


def test_the_endpoint_answers_without_a_model(client, user, source):
    _, source_id = source
    res = client.get("/api/assistant/prompt-ideas", headers=user, params={"source_id": source_id})
    assert res.status_code == 200, res.text
    assert len(res.json()["ideas"]) >= 2


def test_signing_in_is_required(client, source):
    _, source_id = source
    assert client.get("/api/assistant/prompt-ideas", params={"source_id": source_id}).status_code == 401
