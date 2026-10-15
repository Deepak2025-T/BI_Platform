"""Relational database connectors. All dialects go through SQLAlchemy; PostgreSQL is the active target,
the others are wired up and become usable once their driver is installed (see requirements-extra.txt)."""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine, URL

from .config import get_settings
from .db import DbConnection, decrypt


@dataclass(frozen=True)
class Dialect:
    key: str
    label: str
    sa_driver: str           # SQLAlchemy drivername
    sqlglot: str             # sqlglot dialect name for parsing/transpiling
    default_port: int | None
    status: str              # active | beta
    pip: str                 # driver package


DIALECTS: dict[str, Dialect] = {
    "postgres": Dialect("postgres", "PostgreSQL", "postgresql+psycopg", "postgres", 5432, "active", "psycopg[binary]"),
    "mysql": Dialect("mysql", "MySQL / MariaDB", "mysql+pymysql", "mysql", 3306, "beta", "pymysql"),
    "mssql": Dialect("mssql", "SQL Server", "mssql+pyodbc", "tsql", 1433, "beta", "pyodbc (+ ODBC Driver 18)"),
    "oracle": Dialect("oracle", "Oracle", "oracle+oracledb", "oracle", 1521, "beta", "oracledb"),
    "db2": Dialect("db2", "IBM Db2", "db2+ibm_db", "postgres", 50000, "beta", "ibm_db_sa"),
    "sqlite": Dialect("sqlite", "SQLite", "sqlite", "sqlite", None, "beta", "built-in"),
}


def build_url(conn: DbConnection) -> URL | str:
    d = DIALECTS[conn.dialect]
    if conn.dialect == "sqlite":
        return f"sqlite:///{conn.database}"
    query = dict(conn.options or {}).get("query", {})
    if conn.dialect == "mssql" and "driver" not in query:
        query = {**query, "driver": "ODBC Driver 18 for SQL Server", "TrustServerCertificate": "yes"}
    if conn.dialect == "oracle":
        query = {**query, "service_name": conn.database}
    return URL.create(
        d.sa_driver,
        username=conn.username,
        password=decrypt(conn.password_enc),
        host=conn.host,
        port=conn.port or d.default_port,
        database=None if conn.dialect == "oracle" else conn.database,
        query=query,
    )


_engines: dict[int, Engine] = {}


def get_engine(conn: DbConnection) -> Engine:
    key = conn.id
    if key not in _engines:
        _engines[key] = create_engine(build_url(conn), pool_pre_ping=True, future=True)
    return _engines[key]


def drop_engine(conn_id: int) -> None:
    eng = _engines.pop(conn_id, None)
    if eng:
        eng.dispose()


def test_connection(conn: DbConnection) -> dict:
    eng = create_engine(build_url(conn), future=True)
    try:
        with eng.connect() as c:
            c.execute(text("SELECT 1" if conn.dialect not in ("oracle",) else "SELECT 1 FROM dual"))
        return {"ok": True}
    except ModuleNotFoundError as e:
        return {"ok": False, "error": f"Driver not installed: {e.name}. Install: {DIALECTS[conn.dialect].pip}"}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e).splitlines()[0]}
    finally:
        eng.dispose()


def introspect(conn: DbConnection) -> list[dict]:
    """Return tables with columns, PK, FKs and a few sample values — the raw material for RAG."""
    eng = get_engine(conn)
    insp = inspect(eng)
    schema = conn.schema_name or (None if conn.dialect != "postgres" else "public")
    out = []
    for t in insp.get_table_names(schema=schema):
        cols = insp.get_columns(t, schema=schema)
        pk = insp.get_pk_constraint(t, schema=schema).get("constrained_columns", [])
        fks = [
            {"columns": fk["constrained_columns"], "ref_table": fk["referred_table"], "ref_columns": fk["referred_columns"]}
            for fk in insp.get_foreign_keys(t, schema=schema)
        ]
        comment = (insp.get_table_comment(t, schema=schema) or {}).get("text")
        samples = {}
        try:
            q = f'SELECT * FROM {qualify(conn, t)}'
            with eng.connect() as c:
                df = pd.read_sql(text(_limit(conn, q, 5)), c)
            for col in df.columns:
                vals = [str(v) for v in df[col].dropna().unique()[:3]]
                if vals:
                    samples[col] = vals
        except Exception:  # noqa: BLE001
            pass
        out.append({
            "table": t,
            "schema": schema,
            "comment": comment,
            "primary_key": pk,
            "foreign_keys": fks,
            "columns": [
                {"name": c["name"], "type": str(c["type"]), "nullable": c.get("nullable", True),
                 "comment": c.get("comment"), "samples": samples.get(c["name"], [])}
                for c in cols
            ],
        })
    return out


def qualify(conn: DbConnection, table: str) -> str:
    schema = conn.schema_name or ("public" if conn.dialect == "postgres" else None)
    q = '"' if conn.dialect in ("postgres", "oracle", "db2", "sqlite") else ("`" if conn.dialect == "mysql" else '"')
    return f"{q}{schema}{q}.{q}{table}{q}" if schema else f"{q}{table}{q}"


def _limit(conn: DbConnection, sql: str, n: int) -> str:
    if conn.dialect == "mssql":
        return sql.replace("SELECT", f"SELECT TOP {n}", 1)
    if conn.dialect in ("oracle", "db2"):
        return f"{sql} FETCH FIRST {n} ROWS ONLY"
    return f"{sql} LIMIT {n}"


def run_readonly(conn: DbConnection, sql: str, max_rows: int) -> pd.DataFrame:
    """Execute a validated SELECT inside a read-only transaction with a statement timeout."""
    s = get_settings()
    eng = get_engine(conn)
    with eng.connect() as c:
        if conn.dialect == "postgres":
            c.execute(text("SET TRANSACTION READ ONLY"))
            c.execute(text(f"SET LOCAL statement_timeout = {int(s.statement_timeout_ms)}"))
        elif conn.dialect == "mysql":
            c.execute(text("SET SESSION TRANSACTION READ ONLY"))
        result = c.execute(text(sql))
        rows = result.fetchmany(max_rows)
        df = pd.DataFrame(rows, columns=list(result.keys()))
        c.rollback()
    return df


def explain(conn: DbConnection, sql: str) -> None:
    """Dry-run: raises if the query cannot be planned (bad column, bad join, etc.)."""
    eng = get_engine(conn)
    prefix = {"postgres": "EXPLAIN ", "mysql": "EXPLAIN ", "sqlite": "EXPLAIN QUERY PLAN ",
              "oracle": "EXPLAIN PLAN FOR ", "db2": "EXPLAIN PLAN FOR "}.get(conn.dialect)
    with eng.connect() as c:
        if prefix:
            c.execute(text(prefix + sql))
        elif conn.dialect == "mssql":
            c.execute(text("SET SHOWPLAN_XML ON"))
            try:
                c.execute(text(sql))
            finally:
                c.execute(text("SET SHOWPLAN_XML OFF"))
        c.rollback()
