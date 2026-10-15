"""Prompt → intent → RAG → SQL → validate (auto-fix) → execute → chart spec + KPIs."""
from __future__ import annotations

import decimal
import json
import time
from dataclasses import dataclass, field

import pandas as pd

from ..config import get_settings
from ..connectors import DIALECTS, run_readonly
from ..db import DbConnection, QueryLog, SessionLocal
from ..llm.providers import LLM, get_llm
from ..rag import retrieve
from . import prompts
from .charts import infer_chart, kpis, to_records
from .validator import SQLValidationError, validate


@dataclass
class QueryResult:
    question: str
    sql: str | None = None
    explanation: str | None = None
    intent: dict = field(default_factory=dict)
    chart: dict = field(default_factory=dict)
    kpis: list = field(default_factory=list)
    columns: list = field(default_factory=list)
    rows: list = field(default_factory=list)
    attempts: int = 0
    tables_used: list = field(default_factory=list)
    error: str | None = None
    trace: list = field(default_factory=list)
    elapsed_ms: int = 0

    def dict(self) -> dict:
        return self.__dict__.copy()


def _normalise(df: pd.DataFrame) -> pd.DataFrame:
    for c in df.columns:
        nonnull = df[c].dropna()
        if len(nonnull) and isinstance(nonnull.iloc[0], decimal.Decimal):
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def detect_intent(llm: LLM, question: str) -> dict:
    try:
        return llm.complete_json(prompts.INTENT_SYSTEM, question, tier="fast")
    except Exception as e:  # noqa: BLE001 — intent is an optimisation, never fatal
        return {"intent": None, "search_query": question, "error": str(e)[:200]}


def generate_sql(llm: LLM, conn: DbConnection, question: str, ctx: dict) -> dict:
    system = prompts.SQL_SYSTEM.format(
        dialect=DIALECTS[conn.dialect].label, schema=ctx["schema_text"] or "(no schema indexed)",
        glossary=ctx["glossary_text"] or "(none)", examples=ctx["examples_text"] or "(none)")
    return llm.complete_json(system, f"QUESTION: {question}", tier="strong"), system


def run_question(conn: DbConnection, question: str, *, max_rows: int | None = None,
                 preferred_chart: str | None = None, llm: LLM | None = None) -> QueryResult:
    s = get_settings()
    max_rows = max_rows or s.max_rows_default
    llm = llm or get_llm()
    t0 = time.time()
    res = QueryResult(question=question)

    res.intent = detect_intent(llm, question)
    res.trace.append({"step": "intent", "data": res.intent})

    search = " ".join(filter(None, [question, res.intent.get("search_query"),
                                    " ".join(res.intent.get("measures") or []),
                                    " ".join(res.intent.get("dimensions") or [])]))
    ctx = retrieve(conn.id, search)
    res.tables_used = ctx["tables"]
    res.trace.append({"step": "retrieve", "data": {"tables": ctx["tables"]}})

    out, system = generate_sql(llm, conn, question, ctx)
    sql = out.get("sql", "")
    safe_sql = None
    for attempt in range(1, s.sql_max_fix_attempts + 2):
        res.attempts = attempt
        try:
            safe_sql = validate(conn, sql, max_rows)
            res.trace.append({"step": "validate", "attempt": attempt, "ok": True})
            break
        except SQLValidationError as e:
            res.trace.append({"step": "validate", "attempt": attempt, "ok": False, "error": str(e), "sql": sql})
            if attempt > s.sql_max_fix_attempts:
                res.error = str(e)
                break
            out = llm.complete_json(system, prompts.FIX_USER.format(question=question, sql=sql, error=str(e)), tier="strong")
            sql = out.get("sql", "")

    res.sql = safe_sql or sql
    res.explanation = out.get("explanation")
    if safe_sql:
        try:
            df = _normalise(run_readonly(conn, safe_sql, max_rows))
            res.columns = list(df.columns)
            res.chart = infer_chart(df, out.get("chart"), preferred_chart)
            res.kpis = kpis(df, res.chart)
            res.rows = to_records(df)
        except Exception as e:  # noqa: BLE001
            res.error = "Execution failed: " + str(getattr(e, "orig", e)).splitlines()[0]
    res.elapsed_ms = int((time.time() - t0) * 1000)
    _log(conn, question, res, llm.name)
    return res


def insights(llm: LLM, question: str, res: QueryResult) -> list[str]:
    if not res.rows:
        return []
    sample = json.dumps(res.rows[:25], default=str)
    try:
        out = llm.complete_json(prompts.INSIGHT_SYSTEM, f"QUESTION: {question}\nKPIS: {json.dumps(res.kpis)}\nDATA: {sample}", tier="fast")
        return [str(x) for x in out.get("insights", [])][:3]
    except Exception:  # noqa: BLE001
        return []


def _log(conn, question, res: QueryResult, provider: str) -> None:
    with SessionLocal() as db:
        db.add(QueryLog(connection_id=conn.id, prompt=question, sql=res.sql, provider=provider,
                        status="error" if res.error else "ok", error=res.error, attempts=res.attempts,
                        row_count=len(res.rows)))
        db.commit()
