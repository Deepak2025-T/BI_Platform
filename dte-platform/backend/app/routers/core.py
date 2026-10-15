"""Connections, model settings, NL→SQL query and forecasting endpoints."""
from __future__ import annotations

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from ..connectors import DIALECTS, drop_engine, introspect, run_readonly, test_connection
from ..db import DbConnection, QueryLog, SessionLocal, encrypt
from ..forecast import METRICS, run_forecast
from ..llm.providers import load_config, save_config, test_provider
from ..nl2sql.charts import infer_chart, kpis, to_records
from ..nl2sql.pipeline import _normalise, run_question
from ..nl2sql.validator import SQLValidationError, validate
from ..rag import add_glossary, index_connection

router = APIRouter(prefix="/api")


# ---------------- dialects & connections ----------------
@router.get("/dialects")
def dialects():
    return [{"key": d.key, "label": d.label, "default_port": d.default_port, "status": d.status, "driver": d.pip}
            for d in DIALECTS.values()]


class ConnIn(BaseModel):
    name: str
    dialect: str = "postgres"
    host: str | None = "localhost"
    port: int | None = None
    database: str
    username: str | None = None
    password: str | None = None
    schema_name: str | None = None
    options: dict = {}


def conn_out(c: DbConnection) -> dict:
    return {"id": c.id, "name": c.name, "dialect": c.dialect, "host": c.host, "port": c.port, "database": c.database,
            "username": c.username, "schema_name": c.schema_name, "indexed_at": c.indexed_at, "options": c.options,
            "status": DIALECTS[c.dialect].status}


def get_conn(conn_id: int) -> DbConnection:
    with SessionLocal() as db:
        c = db.get(DbConnection, conn_id)
        if not c:
            raise HTTPException(404, "Connection not found")
        return c


def _apply(c: DbConnection, body: ConnIn):
    if body.dialect not in DIALECTS:
        raise HTTPException(400, f"Unknown dialect {body.dialect}")
    for f in ("name", "dialect", "host", "port", "database", "username", "schema_name", "options"):
        setattr(c, f, getattr(body, f))
    if body.password:
        c.password_enc = encrypt(body.password)


@router.get("/connections")
def list_connections():
    with SessionLocal() as db:
        return [conn_out(c) for c in db.scalars(select(DbConnection).order_by(DbConnection.id))]


@router.post("/connections/test")
def test_unsaved(body: ConnIn):
    c = DbConnection()
    _apply(c, body)
    return test_connection(c)


@router.post("/connections")
def create_connection(body: ConnIn):
    with SessionLocal() as db:
        c = DbConnection()
        _apply(c, body)
        db.add(c)
        db.commit()
        return conn_out(c)


@router.put("/connections/{conn_id}")
def update_connection(conn_id: int, body: ConnIn):
    with SessionLocal() as db:
        c = db.get(DbConnection, conn_id)
        if not c:
            raise HTTPException(404)
        _apply(c, body)
        db.commit()
        drop_engine(conn_id)
        return conn_out(c)


@router.delete("/connections/{conn_id}")
def delete_connection(conn_id: int):
    with SessionLocal() as db:
        c = db.get(DbConnection, conn_id)
        if c:
            db.delete(c)
            db.commit()
    drop_engine(conn_id)
    return {"ok": True}


@router.post("/connections/{conn_id}/test")
def test_saved(conn_id: int):
    return test_connection(get_conn(conn_id))


class IndexIn(BaseModel):
    glossary: dict[str, str] = {}


@router.post("/connections/{conn_id}/index")
def index(conn_id: int, body: IndexIn | None = None):
    try:
        n = index_connection(get_conn(conn_id), (body.glossary if body else None))
    except Exception as e:  # noqa: BLE001
        raise HTTPException(400, f"Indexing failed: {e}") from e
    return {"ok": True, "tables_indexed": n}


@router.get("/connections/{conn_id}/schema")
def schema(conn_id: int):
    return introspect(get_conn(conn_id))


class GlossaryIn(BaseModel):
    term: str
    definition: str


@router.post("/connections/{conn_id}/glossary")
def glossary(conn_id: int, body: GlossaryIn):
    add_glossary(conn_id, body.term, body.definition)
    return {"ok": True}


# ---------------- model configuration ----------------
@router.get("/settings/llm")
def get_llm_settings():
    return load_config().public()


@router.put("/settings/llm")
def put_llm_settings(body: dict):
    return save_config(body).public()


@router.post("/settings/llm/test")
def test_llm(body: dict | None = None):
    cfg = load_config()
    for k, v in (body or {}).items():
        if hasattr(cfg, k) and v not in (None, "") and not (k == "anthropic_api_key" and str(v).startswith("••••")):
            setattr(cfg, k, v)
    return test_provider(cfg)


@router.get("/settings/ollama/models")
def ollama_models():
    cfg = load_config()
    try:
        r = httpx.get(f"{cfg.ollama_url.rstrip('/')}/api/tags", timeout=5)
        return {"ok": True, "models": [m["name"] for m in r.json().get("models", [])]}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "models": [], "error": str(e)[:200]}


# ---------------- querying ----------------
class AskIn(BaseModel):
    connection_id: int
    question: str
    chart: str | None = None
    max_rows: int | None = None


@router.post("/query")
def ask(body: AskIn):
    try:
        res = run_question(get_conn(body.connection_id), body.question, preferred_chart=body.chart, max_rows=body.max_rows)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"LLM/pipeline error: {e}") from e
    d = res.dict()
    d["roles"] = d["chart"].pop("roles", None) if d["chart"] else None
    return d


class SqlIn(BaseModel):
    connection_id: int
    sql: str
    chart: dict | None = None
    max_rows: int = 5000


@router.post("/query/sql")
def run_sql(body: SqlIn):
    """Run user-edited SQL from the designer (same safety checks as generated SQL)."""
    conn = get_conn(body.connection_id)
    try:
        safe = validate(conn, body.sql, body.max_rows)
    except SQLValidationError as e:
        raise HTTPException(400, str(e)) from e
    df = _normalise(run_readonly(conn, safe, body.max_rows))
    chart = infer_chart(df, body.chart, (body.chart or {}).get("type"))
    return {"sql": safe, "columns": list(df.columns), "rows": to_records(df), "kpis": kpis(df, chart),
            "chart": {k: v for k, v in chart.items() if k != "roles"}, "roles": chart["roles"]}


@router.get("/query/history")
def history(limit: int = 50):
    with SessionLocal() as db:
        rows = db.scalars(select(QueryLog).order_by(QueryLog.id.desc()).limit(limit)).all()
        return [{"id": r.id, "prompt": r.prompt, "sql": r.sql, "status": r.status, "error": r.error, "provider": r.provider,
                 "attempts": r.attempts, "row_count": r.row_count, "created_at": r.created_at} for r in rows]


# ---------------- forecasting ----------------
@router.get("/forecast/metrics")
def forecast_metrics():
    return [{"key": k, "label": v[0]} for k, v in METRICS.items()]


class ForecastIn(BaseModel):
    connection_id: int
    metric: str = "revenue"
    horizon: int = 6
    sql: str | None = None


@router.post("/forecast")
def forecast(body: ForecastIn):
    try:
        return run_forecast(get_conn(body.connection_id), body.metric, body.horizon, body.sql)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(400, str(e)) from e
