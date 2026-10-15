"""Templates, prompt→report generation, save / publish / refresh."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from ..connectors import run_readonly
from ..db import Report, SessionLocal
from ..nl2sql.charts import infer_chart, kpis, to_records
from ..nl2sql.pipeline import _normalise
from ..nl2sql.validator import validate
from ..rag import add_example
from ..reports.builder import build_report
from ..reports.templates import TEMPLATE_BY_ID, TEMPLATES
from .core import get_conn

router = APIRouter(prefix="/api")


@router.get("/templates")
def templates():
    return TEMPLATES


class GenerateIn(BaseModel):
    connection_id: int
    prompt: str
    template_id: str = "executive"
    insights: bool = True


@router.post("/reports/generate")
def generate(body: GenerateIn):
    if body.template_id not in TEMPLATE_BY_ID:
        raise HTTPException(400, "Unknown template")
    try:
        spec = build_report(get_conn(body.connection_id), body.prompt, body.template_id, with_insights=body.insights)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"Report generation failed: {e}") from e
    spec["connection_id"] = body.connection_id
    return spec


class ReportIn(BaseModel):
    title: str
    prompt: str | None = None
    connection_id: int | None = None
    template_id: str | None = None
    spec: dict


def out(r: Report, full=True) -> dict:
    d = {"id": r.id, "title": r.title, "prompt": r.prompt, "connection_id": r.connection_id, "template_id": r.template_id,
         "published": r.published, "created_at": r.created_at, "updated_at": r.updated_at}
    if full:
        d["spec"] = r.spec
    return d


def _strip_data(spec: dict) -> dict:
    """Persist layout/SQL/style only; data is re-queried on open so reports stay live."""
    s = dict(spec)
    s["widgets"] = [{k: v for k, v in w.items() if k not in ("rows",)} for w in spec.get("widgets", [])]
    return s


@router.get("/reports")
def list_reports():
    with SessionLocal() as db:
        return [out(r, full=False) for r in db.scalars(select(Report).order_by(Report.updated_at.desc()))]


@router.post("/reports")
def create_report(body: ReportIn):
    with SessionLocal() as db:
        r = Report(title=body.title, prompt=body.prompt, connection_id=body.connection_id, template_id=body.template_id,
                   spec=_strip_data(body.spec))
        db.add(r)
        db.commit()
        return out(r)


@router.put("/reports/{rid}")
def update_report(rid: int, body: ReportIn):
    with SessionLocal() as db:
        r = db.get(Report, rid)
        if not r:
            raise HTTPException(404)
        r.title, r.prompt, r.spec = body.title, body.prompt, _strip_data(body.spec)
        r.connection_id, r.template_id = body.connection_id, body.template_id
        db.commit()
        return out(r)


@router.delete("/reports/{rid}")
def delete_report(rid: int):
    with SessionLocal() as db:
        r = db.get(Report, rid)
        if r:
            db.delete(r)
            db.commit()
    return {"ok": True}


@router.get("/reports/{rid}")
def get_report(rid: int, refresh: bool = True):
    with SessionLocal() as db:
        r = db.get(Report, rid)
        if not r:
            raise HTTPException(404)
        d = out(r)
    if refresh and d["connection_id"]:
        d["spec"] = refresh_spec(d["connection_id"], d["spec"])
    return d


@router.post("/reports/{rid}/publish")
def publish(rid: int):
    with SessionLocal() as db:
        r = db.get(Report, rid)
        if not r:
            raise HTTPException(404)
        r.published = True
        db.commit()
        spec, conn_id = r.spec, r.connection_id
    # learning loop: verified question→SQL pairs become few-shot examples for future prompts
    n = 0
    if conn_id:
        for w in spec.get("widgets", []):
            if w.get("sql") and w.get("question") and not w.get("error"):
                add_example(conn_id, w["question"], w["sql"])
                n += 1
    return {"ok": True, "examples_saved": n}


def refresh_spec(conn_id: int, spec: dict) -> dict:
    conn = get_conn(conn_id)
    widgets = []
    for w in spec.get("widgets", []):
        w = dict(w)
        if w.get("sql"):
            try:
                safe = validate(conn, w["sql"], 5000)
                df = _normalise(run_readonly(conn, safe, 5000))
                chart = infer_chart(df, w.get("chart"), (w.get("chart") or {}).get("type"))
                w.update(rows=to_records(df), columns=list(df.columns), kpis=kpis(df, chart), roles=chart["roles"], error=None)
            except Exception as e:  # noqa: BLE001
                w.update(rows=[], error=str(e)[:300])
        widgets.append(w)
    return {**spec, "widgets": widgets}
