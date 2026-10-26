"""Dashboard filters, the result cache and Excel export, on a small SQLite shop database. The fake
Ollama model from test_assistant maps filters at design time; viewing uses no model."""

import io
import sqlite3
import uuid
import zipfile

import pytest

from app import dashboard_filters
from app.datasources import DataSource, _bind
from tests.test_assistant import model_id  # noqa: F401  (fixture)

TOTAL = "SELECT SUM(amount) AS total FROM orders"
BY_REGION = "SELECT o.region, SUM(o.amount) AS total FROM orders o GROUP BY o.region ORDER BY o.region"
CUSTOMERS = "SELECT COUNT(*) AS customers FROM customers"


@pytest.fixture(scope="module")
def shop(tmp_path_factory) -> str:
    path = (tmp_path_factory.mktemp("shop") / "shop.db").as_posix()
    con = sqlite3.connect(path)
    con.executescript("""
        CREATE TABLE orders (id INTEGER PRIMARY KEY, region TEXT, amount REAL, order_date TEXT);
        CREATE TABLE customers (id INTEGER PRIMARY KEY, name TEXT);
        INSERT INTO orders (region, amount, order_date) VALUES
            ('North', 100, '2024-01-15'), ('North', 200, '2024-02-10'),
            ('South', 50, '2024-02-28 18:30:00'), ('East', 25, '2024-03-05');
        INSERT INTO customers (name) VALUES ('Asha'), ('Ben');
    """)
    con.commit()
    con.close()
    return path


@pytest.fixture(scope="module")
def source(client, manager, shop):
    c = client.post("/api/connections", headers=manager, json={
        "name": f"Shop {uuid.uuid4().hex[:6]}", "db_type": "sqlite", "database": shop}).json()
    client.put(f"/api/connections/{c['id']}", headers=manager, json={"allowed_tables": ["main.orders", "main.customers"]})
    yield c["id"]
    client.delete(f"/api/connections/{c['id']}", headers=manager)


def _widget(wid, title, sql, chart_type="table"):
    return {"id": wid, "title": title, "sql": sql, "chart": {"type": chart_type, "x": "", "y": []}}


@pytest.fixture(scope="module")
def dashboard(client, user, model_id, source):  # noqa: F811
    widgets = [_widget("total", "Total sales", TOTAL, "kpi"), _widget("region", "By region", BY_REGION),
               _widget("cust", "Customers", CUSTOMERS, "kpi")]
    report = client.post("/api/assistant/save", headers=user, json={
        "source_id": source, "title": "Shop: sales/regions", "widgets": widgets}).json()
    filters = []
    for label, kind in (("Order date", "date"), ("Region", "category")):
        res = client.post(f"/api/reports/{report['id']}/filters/map", headers=user, json={
            "model_id": model_id, "label": label, "kind": kind, "widgets": widgets})
        assert res.status_code == 200, res.text
        filters.append(res.json())
    config = {**report["config"], "widgets": widgets, "filters": filters}  # keep the readable ids
    assert client.put(f"/api/reports/{report['id']}", headers=user, json={"config": config}).status_code == 200
    return {"id": report["id"], "date": filters[0], "region": filters[1], "config": config}


def _data(client, headers, report_id, filters=None, refresh=False):
    res = client.post(f"/api/reports/{report_id}/data", headers=headers, json={"filters": filters or {}, "refresh": refresh})
    assert res.status_code == 200, res.text
    return {w["id"]: w for w in res.json()["widgets"]}


def test_filters_are_mapped_to_columns_at_design_time(dashboard):
    date, region = dashboard["date"], dashboard["region"]
    assert date["kind"] == "date" and date["columns"]["total"] == {"table": "main.orders", "column": "order_date"}
    assert region["columns"]["region"] == {"table": "main.orders", "column": "region"}
    assert "cust" not in region["columns"]  # customers has no region
    assert region["options"] == ["East", "North", "South"]


def test_category_filter_applies_to_totals_too(client, user, dashboard):
    data = _data(client, user, dashboard["id"], {dashboard["region"]["id"]: {"values": ["North"]}})
    assert data["total"]["rows"] == [[300.0]]
    assert data["region"]["rows"] == [["North", 300.0]]
    assert data["total"]["filtered"] == [dashboard["region"]["id"]]
    assert data["cust"]["rows"] == [[2]] and data["cust"]["not_filtered"] == [dashboard["region"]["id"]]


def test_date_range_includes_the_whole_last_day(client, user, dashboard):
    f = {dashboard["date"]["id"]: {"date_from": "2024-02-01", "date_to": "2024-02-28"}}
    assert _data(client, user, dashboard["id"], f)["total"]["rows"] == [[250.0]]
    both = {**f, dashboard["region"]["id"]: {"values": ["South", "East"]}}
    assert _data(client, user, dashboard["id"], both)["region"]["rows"] == [["South", 50.0]]


def test_filter_values_are_bound_not_written_into_sql(client, user, dashboard):
    data = _data(client, user, dashboard["id"], {dashboard["region"]["id"]: {"values": ["North' OR '1'='1"]}})
    assert data["total"]["rows"] == [[None]]
    assert "OR '1'='1" not in data["total"]["sql"] and ":bi_p0" in data["total"]["sql"]


def test_mapping_to_a_table_that_is_not_allowed_is_not_used(client, user, dashboard):
    """A filter edited to point at another table can't widen what a chart reads."""
    region = {**dashboard["region"], "columns": {"total": {"table": "main.salaries", "column": "region"}}}
    config = {**dashboard["config"], "filters": [dashboard["date"], region]}
    report = client.post("/api/assistant/save", headers=user, json={
        "source_id": dashboard["config"]["source_id"], "title": "t", "widgets": config["widgets"]}).json()
    client.put(f"/api/reports/{report['id']}", headers=user, json={"config": config})
    data = _data(client, user, report["id"], {region["id"]: {"values": ["North"]}})
    assert data["total"]["rows"] == [[375.0]] and data["total"]["not_filtered"] == [region["id"]]


def test_results_are_cached_until_refresh(client, user, dashboard, shop):
    f = {dashboard["region"]["id"]: {"values": ["East"]}}
    first = _data(client, user, dashboard["id"], f)["total"]
    con = sqlite3.connect(shop)
    con.execute("INSERT INTO orders (region, amount, order_date) VALUES ('East', 1000, '2024-03-06')")
    con.commit()
    con.close()
    again = _data(client, user, dashboard["id"], f)["total"]
    assert again["cached"] is True and again["rows"] == first["rows"] and again["ran_at"] == first["ran_at"]
    fresh = _data(client, user, dashboard["id"], f, refresh=True)["total"]
    assert fresh["cached"] is False and fresh["rows"] == [[1025.0]]
    assert _data(client, user, dashboard["id"], f)["total"]["rows"] == [[1025.0]]  # the refreshed result is kept


def test_excel_export_has_a_sheet_per_chart(client, user, dashboard):
    res = client.post(f"/api/reports/{dashboard['id']}/export", headers=user,
                      json={"filters": {dashboard["region"]["id"]: {"values": ["North"]}}})
    assert res.status_code == 200, res.text
    assert res.headers["content-type"].startswith("application/vnd.openxmlformats")
    assert "Shop%20sales%20regions.xlsx" in res.headers["content-disposition"]
    with zipfile.ZipFile(io.BytesIO(res.content)) as z:
        workbook = z.read("xl/workbook.xml").decode()
        sheets = [n for n in z.namelist() if n.startswith("xl/worksheets/sheet")]
        strings = z.read("xl/sharedStrings.xml").decode()
    assert len(sheets) == 4
    for name in ("About", "Total sales", "By region", "Customers"):
        assert f'name="{name}"' in workbook
    assert "Filter: Region" in strings and "not filtered by Region" in strings


def test_export_needs_access(client, manager, user, source):
    report = client.post("/api/assistant/save", headers=manager, json={
        "source_id": source, "title": "private", "widgets": [_widget("a", "A", TOTAL)]}).json()
    assert client.post(f"/api/reports/{report['id']}/export", headers=user).status_code == 404


def test_others_cannot_map_filters_on_a_private_draft(client, manager, user, model_id, source):  # noqa: F811
    widgets = [_widget("a", "A", TOTAL)]
    report = client.post("/api/assistant/save", headers=manager, json={"source_id": source, "title": "p", "widgets": widgets}).json()
    res = client.post(f"/api/reports/{report['id']}/filters/map", headers=user, json={
        "model_id": model_id, "label": "Region", "kind": "category", "widgets": widgets})
    assert res.status_code == 404


# ---------- Without the API ----------

PG = DataSource(id=1, name="pg", db_type="postgresql", tables=["public.orders"], version="v")
REGION = {"id": "r", "kind": "category", "columns": {"w": {"table": "public.orders", "column": "region"}}}


def test_postgres_placeholders_and_percent_signs():
    sql = "SELECT TO_CHAR(order_date, 'YYYY-MM') AS m, COUNT(*) FROM orders WHERE note LIKE '%x%' GROUP BY 1"
    wrapped, params, applied, _ = dashboard_filters.apply(sql, PG, [REGION], {"r": {"values": ["N", "S"]}}, "w")
    assert applied == ["r"] and params == {"bi_p0": "N", "bi_p1": "S"}
    assert '(SELECT * FROM orders WHERE "region" IN (%(bi_p0)s, %(bi_p1)s)) AS orders' in wrapped
    statement, bound = _bind(wrapped, params, "pyformat")
    assert "'%%x%%'" in statement and bound == params
    statement, bound = _bind(wrapped, params, "qmark")
    assert "IN (?, ?)" in statement and "'%x%'" in statement and bound == ("N", "S")


def test_ctes_and_unmapped_filters():
    sql = "WITH orders AS (SELECT 1 AS region) SELECT * FROM orders"
    _, params, applied, skipped = dashboard_filters.apply(sql, PG, [REGION], {"r": {"values": ["N"]}}, "w")
    assert applied == [] and skipped == ["r"] and params == {}
    # A filter with no value isn't counted either way.
    assert dashboard_filters.apply("SELECT * FROM orders", PG, [REGION], {}, "w")[2:] == ([], [])
