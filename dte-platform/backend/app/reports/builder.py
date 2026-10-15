"""Build a full multi-widget report from one prompt + a template."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from sqlalchemy import select

from ..db import DbConnection, RagChunk, SessionLocal
from ..llm.providers import get_llm
from ..nl2sql import prompts
from ..nl2sql.pipeline import insights, run_question
from .templates import TEMPLATE_BY_ID


def schema_summary(conn_id: int) -> str:
    with SessionLocal() as db:
        rows = db.scalars(select(RagChunk).where(RagChunk.connection_id == conn_id, RagChunk.kind == "table")).all()
    return "\n".join(f"- {r.ref}({', '.join((r.meta or {}).get('columns', [])[:20])})" for r in rows)


def default_style(template: dict) -> dict:
    return {"palette": template["theme"]["palette"], "numberFormat": {"style": "number", "decimals": 0, "prefix": "", "suffix": ""},
            "showLegend": True, "showLabels": False}


def build_report(conn: DbConnection, prompt: str, template_id: str, *, with_insights: bool = True, max_rows: int = 5000) -> dict:
    template = TEMPLATE_BY_ID[template_id]
    llm = get_llm()
    slots_txt = "\n".join(f"- slot {s['slot']}: {s['type']} — {s['hint']}" for s in template["slots"])
    plan = llm.complete_json(
        prompts.PLANNER_SYSTEM.format(schema=schema_summary(conn.id)),
        f"USER REQUEST: {prompt}\nTEMPLATE: {template['name']}\nSLOTS:\n{slots_txt}", tier="fast")
    planned = {w.get("slot"): w for w in plan.get("widgets", [])}

    def work(slot):
        p = planned.get(slot["slot"]) or {"title": slot["hint"].capitalize(), "question": f"{prompt} — {slot['hint']}"}
        res = run_question(conn, p["question"], preferred_chart=slot["type"], llm=llm, max_rows=max_rows)
        widget = {
            "id": slot["slot"], "title": p.get("title") or slot["hint"], "question": p["question"],
            "layout": slot["layout"], "sql": res.sql, "chart": {k: v for k, v in res.chart.items() if k != "roles"} or {"type": slot["type"]},
            "roles": res.chart.get("roles"), "kpis": res.kpis, "columns": res.columns, "rows": res.rows,
            "error": res.error, "attempts": res.attempts, "style": default_style(template),
        }
        if with_insights and not res.error:
            widget["insights"] = insights(llm, p["question"], res)
        return widget

    with ThreadPoolExecutor(max_workers=4) as pool:
        widgets = list(pool.map(work, template["slots"]))
    return {"title": plan.get("title") or prompt[:80], "template_id": template_id, "prompt": prompt,
            "theme": template["theme"], "widgets": widgets}
