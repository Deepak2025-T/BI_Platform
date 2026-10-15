"""ETL endpoints: extract → map (AI) → transform+validate → load (direct SQL or REST API)."""
from __future__ import annotations

import pathlib

import pandas as pd
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import select

from ..db import EtlRun, SessionLocal
from ..etl.extractors import SUPPORTED, extract_bytes
from ..etl.load import load_direct, load_via_api, validate_rows
from ..etl.transform import ai_mapping, apply_mapping, fields_from_text, pick_table, preview, target_tables
from ..llm.providers import get_llm
from .core import get_conn

router = APIRouter(prefix="/api/etl")
STAGING = pathlib.Path(__file__).resolve().parents[2] / "staging"


def run_dir(run_id: int) -> pathlib.Path:
    return STAGING / str(run_id)


def _save_tables(run_id: int, tables: list[dict], text_: str):
    d = run_dir(run_id)
    d.mkdir(parents=True, exist_ok=True)
    for i, t in enumerate(tables):
        t["df"].to_pickle(d / f"source_{i}.pkl")
    (d / "text.txt").write_text(text_ or "")
    (d / "names.txt").write_text("\n".join(t["name"] for t in tables))


def _source(run_id: int, idx: int) -> pd.DataFrame:
    p = run_dir(run_id) / f"source_{idx}.pkl"
    if not p.exists():
        raise HTTPException(400, "Source table not found for this run")
    return pd.read_pickle(p)


def run_out(r: EtlRun) -> dict:
    return {k: getattr(r, k) for k in ("id", "connection_id", "file_name", "file_type", "target_table", "status", "mapping",
                                        "change_log", "issues", "rows_extracted", "rows_loaded", "created_at")}


@router.get("/supported")
def supported():
    return sorted(SUPPORTED)


@router.get("/targets/{conn_id}")
def targets(conn_id: int):
    return [{"table": t["table"], "columns": [c["name"] for c in t["columns"]]} for t in target_tables(get_conn(conn_id))]


@router.post("/extract")
async def extract(connection_id: int = Form(...), file: UploadFile = File(...)):
    conn = get_conn(connection_id)
    data = await file.read()
    with SessionLocal() as db:
        run = EtlRun(connection_id=conn.id, file_name=file.filename, file_type="?", status="extracting")
        db.add(run)
        db.commit()
        try:
            ex, path = extract_bytes(data, file.filename, run_dir(run.id))
        except Exception as e:  # noqa: BLE001
            run.status, run.issues = "failed", [{"severity": "error", "message": str(e)}]
            db.commit()
            raise HTTPException(400, str(e)) from e
        _save_tables(run.id, ex.tables, ex.text)
        run.file_type, run.staging_path, run.status = ex.file_type, str(path), "extracted"
        run.rows_extracted = int(sum(len(t["df"]) for t in ex.tables))
        run.change_log = ex.log
        db.commit()
        return {**run_out(run), "tables": [{"index": i, "name": t["name"], **preview(t["df"])} for i, t in enumerate(ex.tables)],
                "text_preview": ex.text[:3000]}


class MapIn(BaseModel):
    source_index: int | None = 0         # None → use document text (LLM field extraction)
    table: str | None = None             # None → AI picks the table


@router.post("/{run_id}/map")
def map_columns(run_id: int, body: MapIn):
    with SessionLocal() as db:
        run = db.get(EtlRun, run_id)
        if not run:
            raise HTTPException(404)
        conn = get_conn(run.connection_id)
        tables = target_tables(conn)
        llm = get_llm()
        if body.source_index is None:
            if not body.table:
                raise HTTPException(400, "Choose a target table for text extraction")
            tbl = next(t for t in tables if t["table"] == body.table)
            text_ = (run_dir(run_id) / "text.txt").read_text()
            df = fields_from_text(llm, tbl, text_)
            idx = len(list(run_dir(run_id).glob("source_*.pkl")))
            df.to_pickle(run_dir(run_id) / f"source_{idx}.pkl")
            mapping = {c["name"]: {"source": c["name"] if c["name"] in df.columns else None, "transform": "none", "confidence": 0.9}
                       for c in tbl["columns"]}
            notes = "Fields extracted from document text by the LLM"
        else:
            idx = body.source_index
            df = _source(run_id, idx)
            table_name = body.table or pick_table(llm, tables, df)
            tbl = next((t for t in tables if t["table"] == table_name), None)
            if not tbl:
                raise HTTPException(400, f"Unknown table {table_name}")
            mapping, notes = ai_mapping(llm, tbl, df)
        run.target_table, run.mapping, run.status = tbl["table"], {"source_index": idx, "columns": mapping}, "mapped"
        db.commit()
        return {**run_out(run), "notes": notes, "source_columns": list(df.columns),
                "target_columns": [{"name": c["name"], "type": c["type"], "nullable": c["nullable"],
                                    "pk": c["name"] in tbl["primary_key"]} for c in tbl["columns"]]}


class TransformIn(BaseModel):
    mapping: dict | None = None          # edited mapping from the UI


@router.post("/{run_id}/transform")
def transform(run_id: int, body: TransformIn):
    with SessionLocal() as db:
        run = db.get(EtlRun, run_id)
        if not run or not run.target_table:
            raise HTTPException(400, "Run has no mapping yet")
        conn = get_conn(run.connection_id)
        tbl = next(t for t in target_tables(conn) if t["table"] == run.target_table)
        mapping = body.mapping or run.mapping["columns"]
        df = _source(run_id, run.mapping["source_index"])
        out, log, issues = apply_mapping(conn, tbl, df, mapping)
        issues += validate_rows(conn, tbl, out)
        out.to_pickle(run_dir(run_id) / "transformed.pkl")
        run.mapping = {**run.mapping, "columns": mapping}
        run.change_log = list(run.change_log or []) + log
        run.issues = issues
        run.status = "validated" if not any(i["severity"] == "error" for i in issues) else "needs_review"
        db.commit()
        return {**run_out(run), "preview": preview(out, 50)}


class LoadIn(BaseModel):
    mode: str = "append"                 # append | upsert | replace
    method: str = "direct"               # direct | api
    api_url: str | None = None
    api_headers: dict | None = None
    force: bool = False                  # load despite warnings (errors always block)


@router.post("/{run_id}/load")
def load(run_id: int, body: LoadIn):
    with SessionLocal() as db:
        run = db.get(EtlRun, run_id)
        if not run:
            raise HTTPException(404)
        if any(i["severity"] == "error" for i in (run.issues or [])):
            raise HTTPException(400, "Fix validation errors before loading")
        if not body.force and body.mode == "append" and any(i["severity"] == "warning" for i in (run.issues or [])):
            raise HTTPException(409, "There are warnings — review them, then load with force=true or use upsert")
        p = run_dir(run_id) / "transformed.pkl"
        if not p.exists():
            raise HTTPException(400, "Run transform first")
        df = pd.read_pickle(p)
        conn = get_conn(run.connection_id)
        try:
            if body.method == "api":
                if not body.api_url:
                    raise HTTPException(400, "api_url required for API load")
                n = load_via_api(body.api_url, run.target_table, df, body.api_headers)
            else:
                n = load_direct(conn, run.target_table, df, body.mode)
        except HTTPException:
            raise
        except Exception as e:  # noqa: BLE001
            run.status = "failed"
            run.issues = list(run.issues or []) + [{"severity": "error", "message": "Load failed (rolled back): " + str(getattr(e, 'orig', e)).splitlines()[0]}]
            db.commit()
            raise HTTPException(400, run.issues[-1]["message"]) from e
        run.rows_loaded, run.status = n, "loaded"
        run.change_log = list(run.change_log or []) + [f"loaded {n} row(s) into {run.target_table} via {body.method} ({body.mode})"]
        db.commit()
        return run_out(run)


@router.get("/runs")
def runs(limit: int = 50):
    with SessionLocal() as db:
        return [run_out(r) for r in db.scalars(select(EtlRun).order_by(EtlRun.id.desc()).limit(limit))]


class RecordsIn(BaseModel):
    connection_id: int
    table: str
    records: list[dict]
    mode: str = "append"


@router.post("/load-records")
def load_records(body: RecordsIn):
    """Inbound REST ingestion: other systems push JSON rows; same validation + transactional load."""
    conn = get_conn(body.connection_id)
    tbl = next((t for t in target_tables(conn) if t["table"] == body.table), None)
    if not tbl:
        raise HTTPException(400, "Unknown table")
    df = pd.DataFrame(body.records)
    mapping = {c["name"]: {"source": c["name"] if c["name"] in df.columns else None, "transform": "none"} for c in tbl["columns"]}
    out, log, issues = apply_mapping(conn, tbl, df, mapping)
    issues += validate_rows(conn, tbl, out)
    if any(i["severity"] == "error" for i in issues):
        raise HTTPException(400, {"issues": issues})
    return {"loaded": load_direct(conn, body.table, out, body.mode), "issues": issues}
