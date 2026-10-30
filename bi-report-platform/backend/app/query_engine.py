"""
Turns a question into SQL, runs it, and shapes the result for the UI.

PHASE 1 (this file): `interpret_prompt` is a simple keyword stub that only
understands questions about the `sales` table. It lets you build and test the
whole app end to end (login -> ask -> review -> report -> publish).

PHASE 2: replace `interpret_prompt` with the real pipeline:
  pgvector schema search -> LLM (Ollama / Claude) writes SQL ->
  sqlglot validation (SELECT-only) -> EXPLAIN -> auto-fix loop (max 3).
The rest of the app does not need to change: it only relies on the dict
returned by `run_query`.
"""

import re
import time
from datetime import date

from sqlalchemy import text
from sqlalchemy.orm import Session

from .schemas import QueryParams

PERIODS = {
    "q1_2024": {"label": "Q1 2024 (Jan to Mar)", "short": "Q1 2024",
                "start": date(2024, 1, 1), "end": date(2024, 4, 1), "previous": "q4_2023"},
    "q4_2023": {"label": "Q4 2023 (Oct to Dec)", "short": "Q4 2023",
                "start": date(2023, 10, 1), "end": date(2024, 1, 1), "previous": None},
}

MEASURES = {
    "net": {"expr": "SUM(s.revenue - s.discount - s.refund_amount)", "label": "Net revenue",
            "plain": "revenue after discounts and refunds"},
    "gross": {"expr": "SUM(s.revenue)", "label": "Gross revenue",
              "plain": "revenue before discounts and refunds"},
}

# Only these column names can ever be placed into SQL text (never user input).
ALLOWED_DATE_COLUMNS = {"sale_date", "invoice_date"}


class GenerationFailed(Exception):
    def __init__(self, reason: str, attempts: list[dict], last_sql: str):
        super().__init__(reason)
        self.reason = reason
        self.attempts = attempts
        self.last_sql = last_sql


def build_sql(p: QueryParams) -> tuple[str, str]:
    if p.date_col not in ALLOWED_DATE_COLUMNS:
        raise ValueError("Unknown date column")
    m = MEASURES[p.measure]
    col = f"s.{p.date_col}"
    region_filter = "\n  AND s.region = :region" if p.region != "All" else ""
    alias = m["label"].lower().replace(" ", "_")

    by_month = (
        f"SELECT DATE_TRUNC('month', {col}) AS month,\n"
        f"       s.region,\n"
        f"       {m['expr']} AS {alias}\n"
        f"FROM sales s\n"
        f"WHERE {col} >= :start\n"
        f"  AND {col} <  :end{region_filter}\n"
        f"GROUP BY 1, 2\n"
        f"ORDER BY 1, 2"
    )
    top_products = (
        f"SELECT s.product, {m['expr']} AS total\n"
        f"FROM sales s\n"
        f"WHERE {col} >= :start AND {col} < :end{region_filter}\n"
        f"GROUP BY 1\n"
        f"ORDER BY 2 DESC\n"
        f"LIMIT 5"
    )
    return by_month, top_products


def _bind(p: QueryParams) -> dict:
    period = PERIODS[p.period]
    params = {"start": period["start"], "end": period["end"]}
    if p.region != "All":
        params["region"] = p.region
    return params


def _total(db: Session, p: QueryParams) -> float:
    by_month, _ = build_sql(p)
    rows = db.execute(text(by_month), _bind(p)).all()
    return float(sum(r[2] or 0 for r in rows))


def run_query(db: Session, p: QueryParams) -> dict:
    """Runs the saved query with fixed parameters. No AI involved."""
    t0 = time.perf_counter()
    by_month, top_products = build_sql(p)
    bind = _bind(p)

    # Read-only transaction + timeout as a second safety layer.
    if db.bind.dialect.name == "postgresql":
        db.execute(text("SET TRANSACTION READ ONLY"))
        db.execute(text("SET LOCAL statement_timeout = '15s'"))

    rows = db.execute(text(by_month), bind).all()
    products = db.execute(text(top_products), bind).all()

    months: list[str] = []
    series: dict[str, dict[str, float]] = {}
    for month, region, value in rows:
        label = month.strftime("%b")
        if label not in months:
            months.append(label)
        series.setdefault(region, {})[label] = float(value or 0)

    regions = sorted(series.keys())
    matrix = {r: [round(series[r].get(mo, 0.0), 2) for mo in months] for r in regions}
    total = sum(sum(v) for v in matrix.values())

    compare = None
    prev = PERIODS[p.period]["previous"]
    if prev:
        prev_total = _total(db, p.model_copy(update={"period": prev}))
        if prev_total:
            compare = {"pct": round((total - prev_total) / prev_total * 100, 1),
                       "label": f"vs {PERIODS[prev]['short']}"}
    db.rollback()  # end the read-only transaction

    m = MEASURES[p.measure]
    period = PERIODS[p.period]
    display_sql = (by_month + ";\n\n-- Top 5 products\n" + top_products + ";").replace(
        ":start", f"'{period['start']}'").replace(":end", f"'{period['end']}'").replace(
        ":region", f"'{p.region}'")

    return {
        "params": p.model_dump(),
        "title": f"{m['label']} by region, {period['short']}",
        "measure_label": m["label"],
        "period_label": period["label"],
        "period_short": period["short"],
        "months": months,
        "regions": regions,
        "series": matrix,
        "total": round(total, 2),
        "compare": compare,
        "products": [{"name": n, "value": round(float(v or 0), 2)} for n, v in products],
        "sql": display_sql,
        "explanation": (
            f"Adds up {m['plain']} from the sales table for each region and month, placing each "
            f"sale by its {p.date_col.replace('_', ' ')} from {period['start']} up to {period['end']}. "
            f"A second query ranks products by the same measure and keeps the top 5."
        ),
        "row_count": len(rows),
        "elapsed_ms": round((time.perf_counter() - t0) * 1000),
        "source": "bi_db: sales",
    }


def interpret_prompt(prompt: str) -> QueryParams:
    """PHASE 1 stub. Replace with LLM + RAG in phase 2."""
    q = prompt.lower()
    if re.search(r"churn|cohort", q):
        raise GenerationFailed(
            reason=("None of the connected tables record when a customer signed up or cancelled, "
                    "so churn by cohort can't be calculated."),
            attempts=[
                {"ok": False, "message": 'Attempt 1 failed: no table matches "cohort".'},
                {"ok": False, "message": 'Attempt 2 failed: column "signup_date" does not exist.'},
                {"ok": False, "message": 'Attempt 3 failed: column "churned_at" does not exist.'},
            ],
            last_sql=("SELECT DATE_TRUNC('month', c.signup_date) AS cohort,\n"
                      "       COUNT(*) FILTER (WHERE c.churned_at IS NOT NULL) * 1.0 / COUNT(*) AS churn_rate\n"
                      "FROM customers c\nGROUP BY 1;"),
        )
    if not re.search(r"revenue|sales|region|product", q):
        raise GenerationFailed(
            reason=("The starter query engine only understands questions about the sales table "
                    "(revenue, regions, products). Connect the LLM in phase 2 to answer anything else."),
            attempts=[{"ok": False, "message": "No matching tables found for this question."}],
            last_sql="-- no query generated",
        )
    period = "q4_2023" if re.search(r"q4\s*2023|last quarter of 2023", q) else "q1_2024"
    measure = "gross" if "gross" in q else "net"
    return QueryParams(period=period, measure=measure, date_col="sale_date")
