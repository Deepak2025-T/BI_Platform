"""
Uses an AI model to understand a question about the sales data.

The model only chooses from a fixed set of options (period, measure, date column). It never
writes SQL: the query is still built by query_engine.build_sql, so a model can't change or
read anything else. Week 2 of the build plan replaces this with schema search + SQL writing.
"""

import time

from ..query_engine import MEASURES, PERIODS, GenerationFailed
from ..schemas import QueryParams
from .providers import AIError, ModelSpec, complete_json

SYSTEM = f"""You turn business questions into settings for a fixed sales report.

The data is one table, sales: one row per sale, with sale_date, invoice_date, region (East, North,
South, West), product, revenue, discount and refund_amount. The report shows revenue by region and
month, the total, and the top products.

Choose:
- period: {", ".join(f'"{k}" ({v["short"]})' for k, v in PERIODS.items())}. These are the only periods with data.
- measure: "net" (revenue after discounts and refunds; the default) or "gross" (before discounts and refunds).
- date_col: "sale_date" (when the sale happened; the default) or "invoice_date" (when the customer was billed).

Set answerable to false when the question needs data this table doesn't have (for example costs,
budgets, customers, churn or profit), or asks only for a period that has no data. Then explain why in
reason, in one short sentence written to the person who asked. When answerable is true, reason
says in a few words how you read the question."""

SCHEMA = {
    "type": "object",
    "properties": {
        "answerable": {"type": "boolean"},
        "reason": {"type": "string"},
        "period": {"type": "string", "enum": list(PERIODS)},
        "measure": {"type": "string", "enum": list(MEASURES)},
        "date_col": {"type": "string", "enum": ["sale_date", "invoice_date"]},
    },
    "required": ["answerable", "reason", "period", "measure", "date_col"],
    "additionalProperties": False,
}


def interpret_with_model(spec: ModelSpec, model_name: str, prompt: str) -> tuple[QueryParams, dict]:
    """Returns the report settings and a note for the review screen. Raises AIError or GenerationFailed."""
    t0 = time.perf_counter()
    answer = complete_json(spec, SYSTEM, prompt, SCHEMA)
    ms = round((time.perf_counter() - t0) * 1000)
    reason = str(answer.get("reason", "")).strip()[:300]
    if not answer.get("answerable"):
        raise GenerationFailed(
            reason=reason or "This question needs data that isn't connected yet.",
            attempts=[{"ok": False, "message": f"{model_name} read the question in {ms} ms and found it can't be "
                                               f"answered from the sales table."}],
            last_sql="-- no query generated")
    try:
        params = QueryParams(period=answer["period"], measure=answer["measure"], date_col=answer["date_col"])
    except (KeyError, ValueError):
        raise AIError("The model chose settings that don't exist.")
    note = f"{model_name} understood the question in {ms} ms" + (f": {reason}" if reason else ".")
    return params, {"ok": True, "message": note}
