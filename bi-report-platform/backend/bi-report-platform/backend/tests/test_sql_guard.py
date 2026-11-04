import pytest

from app.sql_guard import UnsafeSQL, check_sql

ALLOWED = {"public.sales", "public.customers"}


def ok(sql, db="postgresql", allowed=ALLOWED, max_rows=500):
    return check_sql(sql, db, allowed, max_rows)


def refused(sql, db="postgresql", allowed=ALLOWED):
    with pytest.raises(UnsafeSQL) as err:
        check_sql(sql, db, allowed, 500)
    return str(err.value)


def test_simple_select_gets_a_limit():
    assert ok("SELECT region, SUM(revenue) FROM sales GROUP BY region").endswith("LIMIT 500")


def test_schema_qualified_and_cte_are_fine():
    ok("SELECT * FROM public.sales")
    ok("WITH t AS (SELECT region FROM sales) SELECT * FROM t")


def test_smaller_limit_is_kept_larger_is_capped():
    assert ok("SELECT * FROM sales LIMIT 10").endswith("LIMIT 10")
    assert ok("SELECT * FROM sales LIMIT 100000").endswith("LIMIT 500")


def test_sql_server_uses_top():
    sql = ok("SELECT region, SUM(revenue) AS s FROM dbo.sales GROUP BY region ORDER BY s DESC",
             db="mssql", allowed={"dbo.sales"})
    assert sql.startswith("SELECT TOP 500")


@pytest.mark.parametrize("sql", [
    "DELETE FROM sales",
    "UPDATE sales SET revenue = 0",
    "INSERT INTO sales (id) VALUES (1)",
    "DROP TABLE sales",
    "TRUNCATE sales",
    "SELECT * INTO copy_of_sales FROM sales",
    "WITH d AS (DELETE FROM sales RETURNING *) SELECT * FROM d",
    "SELECT 1; DROP TABLE sales",
    "SELECT * FROM sales FOR UPDATE",
    "GRANT ALL ON sales TO public",
])
def test_writes_are_refused(sql):
    refused(sql)


@pytest.mark.parametrize("sql", [
    "SELECT * FROM app_users",
    "SELECT * FROM information_schema.tables",
    "SELECT * FROM pg_catalog.pg_user",
    "SELECT * FROM other.sales",
    "SELECT s.* FROM sales s JOIN app_users u ON u.id = s.id",
    "SELECT * FROM (SELECT * FROM app_users) x",
    "SELECT * FROM bi_db.public.sales",
])
def test_only_allowed_tables(sql):
    refused(sql)


@pytest.mark.parametrize("sql", [
    "SELECT pg_read_file('/etc/passwd')",
    "SELECT pg_sleep(100)",
    "SELECT * FROM sales WHERE 1 = (SELECT 1 FROM dblink('host=x', 'select 1') AS t(a int))",
    "SELECT set_config('statement_timeout', '0', false)",
    "SELECT * FROM generate_series(1, 10)",
])
def test_dangerous_functions_are_refused(sql):
    refused(sql)


def test_mysql_and_sqlite_functions():
    refused("SELECT LOAD_FILE('/etc/passwd')", db="mysql", allowed={"shop.orders"})
    refused("SELECT load_extension('x')", db="sqlite", allowed={"main.orders"})


def test_garbage_is_refused():
    assert "couldn't be read" in refused("SELEC region FROM")
    assert refused("") == "No SQL was written."
