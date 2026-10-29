"""
The visual builder: building SQL from dragged fields, on a small SQLite shop database.

These check two things above all: that a spec only ever reaches tables and columns a manager
shared, and that what people type lands in bound parameters instead of in the SQL.
"""

import sqlite3
import uuid

import pytest

from app.datasources import get_source
from app.database import SessionLocal
from app.visual_query import SpecError, compile_spec, describe_table


@pytest.fixture(scope="module")
def shop(tmp_path_factory) -> str:
    path = (tmp_path_factory.mktemp("visuals") / "shop.db").as_posix()
    con = sqlite3.connect(path)
    con.executescript("""
        CREATE TABLE orders (id INTEGER PRIMARY KEY, region TEXT, status TEXT, amount REAL, order_date DATE);
        CREATE TABLE secrets (id INTEGER PRIMARY KEY, token TEXT);
        INSERT INTO orders (region, status, amount, order_date) VALUES
            ('North', 'open',   100, '2024-01-15'),
            ('North', 'closed', 200, '2024-02-10'),
            ('South', 'open',    50, '2024-02-28'),
            ('East',  'open',    25, '2024-03-05');
        INSERT INTO secrets (token) VALUES ('shhh');
    """)
    con.commit()
    con.close()
    return path


@pytest.fixture(scope="module")
def source_id(client, manager, shop) -> int:
    """A connection sharing only `orders`, so `secrets` must stay out of reach."""
    c = client.post("/api/connections", headers=manager, json={
        "name": f"Visuals {uuid.uuid4().hex[:6]}", "db_type": "sqlite", "database": shop}).json()
    client.put(f"/api/connections/{c['id']}", headers=manager, json={"allowed_tables": ["main.orders"]})
    yield c["id"]
    client.delete(f"/api/connections/{c['id']}", headers=manager)


@pytest.fixture(scope="module")
def source(source_id):
    db = SessionLocal()
    try:
        yield get_source(db, source_id)
    finally:
        db.close()


def run(source, spec) -> dict:
    """Compile a spec and run it, the way /api/visuals/run does."""
    from app.datasources import run_sql
    sql, params = compile_spec(source, spec)
    return run_sql(source, sql, params, refresh=True)


# ---------- Building the query ----------

def test_groups_and_aggregates(source):
    data = run(source, {"table": "main.orders",
                        "dimensions": [{"column": "region"}],
                        "measures": [{"column": "amount", "agg": "sum", "alias": "Revenue"}],
                        "order": [{"ref": "Revenue", "dir": "desc"}]})
    assert data["columns"] == ["region", "Revenue"]
    assert data["rows"] == [["North", 300.0], ["South", 50.0], ["East", 25.0]]


def test_count_without_a_column_counts_rows(source):
    data = run(source, {"table": "main.orders", "measures": [{"column": "", "agg": "count"}]})
    assert data["columns"] == ["Count"]
    assert data["rows"] == [[4]]


def test_count_distinct(source):
    data = run(source, {"table": "main.orders", "measures": [{"column": "region", "agg": "count_distinct"}]})
    assert data["rows"] == [[3]]


def test_dimension_only_returns_distinct_values(source):
    data = run(source, {"table": "main.orders", "dimensions": [{"column": "status"}],
                        "order": [{"ref": "status", "dir": "asc"}]})
    assert data["rows"] == [["closed"], ["open"]]


def test_date_bucket_gives_sortable_labels(source):
    data = run(source, {"table": "main.orders",
                        "dimensions": [{"column": "order_date", "bucket": "month"}],
                        "measures": [{"column": "amount", "agg": "sum", "alias": "Revenue"}],
                        "order": [{"ref": "order_date (month)", "dir": "asc"}]})
    assert [r[0] for r in data["rows"]] == ["2024-01", "2024-02", "2024-03"]


def test_two_measures_get_separate_names(source):
    data = run(source, {"table": "main.orders",
                        "measures": [{"column": "amount", "agg": "sum"}, {"column": "amount", "agg": "avg"}]})
    assert data["columns"] == ["Sum of amount", "Average of amount"]


def test_same_alias_twice_does_not_collide(source):
    sql, _ = compile_spec(source, {"table": "main.orders",
                                   "measures": [{"column": "amount", "agg": "sum", "alias": "Total"},
                                                {"column": "id", "agg": "sum", "alias": "Total"}]})
    assert '"Total"' in sql and '"Total 2"' in sql


# ---------- Filters ----------

def test_filter_values_are_bound_not_written_into_the_sql(source):
    sql, params = compile_spec(source, {"table": "main.orders",
                                        "measures": [{"column": "amount", "agg": "sum"}],
                                        "filters": [{"column": "region", "op": "=", "values": ["North"]}]})
    assert "North" not in sql
    assert list(params.values()) == ["North"]


def test_in_filter(source):
    data = run(source, {"table": "main.orders", "measures": [{"column": "amount", "agg": "sum", "alias": "t"}],
                        "filters": [{"column": "region", "op": "in", "values": ["North", "South"]}]})
    assert data["rows"] == [[350.0]]


def test_between_filter_on_dates(source):
    data = run(source, {"table": "main.orders", "measures": [{"column": "amount", "agg": "sum", "alias": "t"}],
                        "filters": [{"column": "order_date", "op": "between",
                                     "values": ["2024-02-01", "2024-02-29"]}]})
    assert data["rows"] == [[250.0]]


def test_contains_filter_escapes_wildcards(source):
    # The % is matched as a character, so nothing matches rather than everything.
    sql, params = compile_spec(source, {"table": "main.orders",
                                        "measures": [{"column": "amount", "agg": "sum"}],
                                        "filters": [{"column": "region", "op": "contains", "values": ["100%"]}]})
    assert params == {"bi_p0": "%100\\%%"}


def test_is_null_takes_no_values(source):
    data = run(source, {"table": "main.orders", "measures": [{"column": "amount", "agg": "sum", "alias": "t"}],
                        "filters": [{"column": "status", "op": "is_null"}]})
    assert data["rows"] == [[None]]


def test_between_needs_two_values(source):
    with pytest.raises(SpecError, match="needs 2 values"):
        compile_spec(source, {"table": "main.orders", "measures": [{"column": "amount", "agg": "sum"}],
                              "filters": [{"column": "amount", "op": "between", "values": [1]}]})


def test_a_number_filter_rejects_text(source):
    with pytest.raises(SpecError, match="isn't a number"):
        compile_spec(source, {"table": "main.orders", "measures": [{"column": "amount", "agg": "sum"}],
                              "filters": [{"column": "amount", "op": ">", "values": ["abc"]}]})


# ---------- Saving a chart: SQL that stands on its own ----------

def test_inline_writes_the_values_into_the_sql(source):
    sql, params = compile_spec(source, {"table": "main.orders",
                                        "measures": [{"column": "amount", "agg": "sum", "alias": "t"}],
                                        "filters": [{"column": "region", "op": "=", "values": ["North"]}]},
                               inline=True)
    assert params == {}
    assert "'North'" in sql


def test_inlined_sql_runs_on_its_own(source):
    """What a saved chart does: the dashboard runs the SQL later with nothing alongside it."""
    from app.datasources import run_sql
    sql, params = compile_spec(source, {"table": "main.orders",
                                        "dimensions": [{"column": "region", "alias": "region"}],
                                        "measures": [{"column": "amount", "agg": "sum", "alias": "Revenue"}],
                                        "filters": [{"column": "region", "op": "in", "values": ["North", "South"]}],
                                        "order": [{"ref": "Revenue", "dir": "desc"}]},
                               inline=True)
    assert params == {}
    data = run_sql(source, sql, {}, refresh=True)  # no parameters, as the dashboard would run it
    assert data["rows"] == [["North", 300.0], ["South", 50.0]]


def test_inlined_dates_run(source):
    from app.datasources import run_sql
    sql, params = compile_spec(source, {"table": "main.orders",
                                        "measures": [{"column": "amount", "agg": "sum", "alias": "t"}],
                                        "filters": [{"column": "order_date", "op": "between",
                                                     "values": ["2024-02-01", "2024-02-29"]}]},
                               inline=True)
    assert params == {}
    assert run_sql(source, sql, {}, refresh=True)["rows"] == [[250.0]]


def test_a_quote_in_an_inlined_value_is_escaped(source):
    """A value with a quote must not be able to end the string and change the query."""
    from app.datasources import run_sql
    sql, _ = compile_spec(source, {"table": "main.orders",
                                   "measures": [{"column": "amount", "agg": "sum", "alias": "t"}],
                                   "filters": [{"column": "region", "op": "=",
                                                "values": ["North' OR 1=1 --"]}]},
                          inline=True)
    # It is one ordinary value that matches nothing, not a condition.
    assert run_sql(source, sql, {}, refresh=True)["rows"] == [[None]]


def test_inlined_sql_still_has_to_pass_the_guard(source):
    """check_query runs over the saved SQL, so an inlined chart is checked like any other."""
    from app.datasources import check_query
    sql, _ = compile_spec(source, {"table": "main.orders", "measures": [{"column": "amount", "agg": "sum"}],
                                   "filters": [{"column": "region", "op": "=", "values": ["North"]}]},
                          inline=True)
    assert check_query(source, sql)


def test_compile_endpoint_can_inline(client, user, source_id):
    res = client.post("/api/visuals/compile", headers=user, json={
        "source_id": source_id, "inline": True,
        "spec": {"table": "main.orders", "measures": [{"column": "amount", "agg": "sum"}],
                 "filters": [{"column": "region", "op": "=", "values": ["North"]}]}})
    assert res.status_code == 200, res.text
    assert res.json()["parameters"] == 0 and "'North'" in res.json()["sql"]


def test_a_saved_builder_chart_keeps_its_spec_and_look(client, user, source_id):
    """Saving must not drop the fields the chart was built from, or how it looks."""
    sql = client.post("/api/visuals/compile", headers=user, json={
        "source_id": source_id, "inline": True,
        "spec": {"table": "main.orders", "dimensions": [{"column": "region", "alias": "region"}],
                 "measures": [{"column": "amount", "agg": "sum", "alias": "Revenue"}]}}).json()["sql"]
    spec = {"table": "main.orders", "dimensions": [{"column": "region"}],
            "measures": [{"column": "amount", "agg": "sum"}], "filters": [], "order": []}
    res = client.post("/api/assistant/save", headers=user, json={
        "source_id": source_id, "title": "Built by hand",
        "widgets": [{"id": "v1", "title": "By region", "sql": sql,
                     "chart": {"type": "bar", "x": "region", "y": ["Revenue"]},
                     "style": {"stackMode": "none"}, "size": "full", "visual": spec}]})
    assert res.status_code == 201, res.text
    saved = res.json()["config"]["widgets"][0]
    assert saved["visual"] == spec
    assert saved["style"] == {"stackMode": "none"} and saved["size"] == "full"

    # And it runs through the ordinary dashboard path, with no parameters to carry.
    data = client.post(f"/api/reports/{res.json()['id']}/data", headers=user, json={"filters": {}})
    assert data.status_code == 200, data.text
    widget = data.json()["widgets"][0]
    assert widget["ok"] is True, widget
    assert widget["rows"] == [["North", 300.0], ["South", 50.0], ["East", 25.0]] or widget["row_count"] == 3


# ---------- What a spec may not reach ----------

def test_a_table_that_was_not_shared_is_refused(source):
    with pytest.raises(SpecError, match="isn't one of the tables shared"):
        compile_spec(source, {"table": "main.secrets", "measures": [{"column": "id", "agg": "count"}]})


def test_a_column_that_does_not_exist_is_refused(source):
    with pytest.raises(SpecError, match='no column called "nope"'):
        compile_spec(source, {"table": "main.orders", "dimensions": [{"column": "nope"}]})


def test_sql_in_a_column_name_is_refused_not_quoted(source):
    with pytest.raises(SpecError, match="no column called"):
        compile_spec(source, {"table": "main.orders",
                              "dimensions": [{"column": 'region" FROM secrets --'}]})


def test_sql_in_a_filter_column_is_refused(source):
    with pytest.raises(SpecError, match="no column called"):
        compile_spec(source, {"table": "main.orders", "measures": [{"column": "amount", "agg": "sum"}],
                              "filters": [{"column": "1=1 OR x", "op": "=", "values": ["a"]}]})


def test_an_unknown_aggregate_is_refused(source):
    with pytest.raises(SpecError, match="isn't a way to summarise"):
        compile_spec(source, {"table": "main.orders", "measures": [{"column": "amount", "agg": "median"}]})


def test_summing_text_is_refused(source):
    with pytest.raises(SpecError, match="can't be added up"):
        compile_spec(source, {"table": "main.orders", "measures": [{"column": "region", "agg": "sum"}]})


def test_bucketing_a_non_date_is_refused(source):
    with pytest.raises(SpecError, match="isn't a date column"):
        compile_spec(source, {"table": "main.orders", "dimensions": [{"column": "region", "bucket": "month"}]})


def test_sorting_by_something_the_chart_does_not_show_is_refused(source):
    with pytest.raises(SpecError, match="doesn't show it"):
        compile_spec(source, {"table": "main.orders", "measures": [{"column": "amount", "agg": "sum"}],
                              "order": [{"ref": "region", "dir": "asc"}]})


def test_an_empty_chart_is_refused(source):
    with pytest.raises(SpecError, match="at least one field"):
        compile_spec(source, {"table": "main.orders"})


def test_the_row_limit_is_capped(source):
    sql, _ = compile_spec(source, {"table": "main.orders", "dimensions": [{"column": "region"}], "limit": 99999})
    assert "LIMIT 5000" in sql


# ---------- The fields pane ----------

def test_describe_table_marks_numbers_and_dates(source):
    described = describe_table(source, "main.orders")
    by_name = {f["name"]: f for f in described["fields"]}
    assert described["table"] == "main.orders"
    assert by_name["amount"]["role"] == "measure" and by_name["amount"]["is_number"]
    assert by_name["region"]["role"] == "dimension" and not by_name["region"]["is_number"]
    assert by_name["order_date"]["is_date"]


def test_describe_table_refuses_a_table_that_was_not_shared(source):
    with pytest.raises(SpecError, match="isn't one of the tables shared"):
        describe_table(source, "main.secrets")


def test_a_table_can_be_named_without_its_schema(source):
    sql, _ = compile_spec(source, {"table": "orders", "measures": [{"column": "amount", "agg": "sum"}]})
    assert "orders" in sql


# ---------- The endpoints ----------

def test_fields_endpoint(client, user, source_id):
    res = client.get("/api/visuals/fields", headers=user, params={"source_id": source_id, "table": "main.orders"})
    assert res.status_code == 200, res.text
    assert {f["name"] for f in res.json()["fields"]} == {"id", "region", "status", "amount", "order_date"}


def test_tables_endpoint_lists_only_shared_tables(client, user, source_id):
    res = client.get("/api/visuals/tables", headers=user, params={"source_id": source_id})
    assert res.status_code == 200, res.text
    assert [t["table"] for t in res.json()] == ["main.orders"]


def test_run_endpoint(client, user, source_id):
    res = client.post("/api/visuals/run", headers=user, json={
        "source_id": source_id,
        "spec": {"table": "main.orders", "dimensions": [{"column": "region"}],
                 "measures": [{"column": "amount", "agg": "sum", "alias": "Revenue"}],
                 "order": [{"ref": "Revenue", "dir": "desc"}]}})
    assert res.status_code == 200, res.text
    assert res.json()["rows"][0] == ["North", 300.0]


def test_compile_endpoint_returns_sql_without_running_it(client, user, source_id):
    res = client.post("/api/visuals/compile", headers=user, json={
        "source_id": source_id,
        "spec": {"table": "main.orders", "measures": [{"column": "amount", "agg": "sum"}],
                 "filters": [{"column": "region", "op": "=", "values": ["North"]}]}})
    assert res.status_code == 200, res.text
    assert "SUM" in res.json()["sql"].upper() and "North" not in res.json()["sql"]
    assert res.json()["parameters"] == 1


def test_values_endpoint_lists_a_columns_values(client, user, source_id):
    res = client.get("/api/visuals/values", headers=user,
                     params={"source_id": source_id, "table": "main.orders", "column": "region"})
    assert res.status_code == 200, res.text
    assert res.json()["values"] == ["East", "North", "South"]


def test_values_endpoint_refuses_a_table_that_was_not_shared(client, user, source_id):
    res = client.get("/api/visuals/values", headers=user,
                     params={"source_id": source_id, "table": "main.secrets", "column": "token"})
    assert res.status_code == 400


def test_a_bad_spec_is_a_400_not_a_crash(client, user, source_id):
    res = client.post("/api/visuals/run", headers=user, json={
        "source_id": source_id, "spec": {"table": "main.orders", "dimensions": [{"column": "nope"}]}})
    assert res.status_code == 400
    assert "nope" in res.json()["detail"]


def test_signing_in_is_required(client, source_id):
    assert client.get("/api/visuals/tables", params={"source_id": source_id}).status_code == 401


def test_a_plain_user_may_build_charts(client, user, source_id):
    """The builder reads only tables a manager already shared, so it is not manager-only."""
    assert client.get("/api/visuals/fields", headers=user,
                      params={"source_id": source_id, "table": "main.orders"}).status_code == 200
