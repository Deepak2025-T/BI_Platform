"""Five report templates. Layout uses a 12-column grid (x, y, w, h) consumed by react-grid-layout."""

# Validated categorical palette (CVD-safe adjacent pairs, fixed order — never cycled)
PALETTE = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]


def _s(slot, type_, hint, x, y, w, h):
    return {"slot": slot, "type": type_, "hint": hint, "layout": {"x": x, "y": y, "w": w, "h": h}}


TEMPLATES = [
    {
        "id": "executive",
        "name": "Executive Overview",
        "description": "Four headline KPIs, a trend line, a mix donut, a comparison column chart and a detail table.",
        "theme": {"palette": PALETTE},
        "slots": [
            _s("kpi1", "kpi", "primary headline total for the period", 0, 0, 3, 2),
            _s("kpi2", "kpi", "second headline measure", 3, 0, 3, 2),
            _s("kpi3", "kpi", "a count (e.g. number of transactions/customers)", 6, 0, 3, 2),
            _s("kpi4", "kpi", "a ratio or average", 9, 0, 3, 2),
            _s("trend", "line", "main measure over time by month", 0, 2, 8, 4),
            _s("mix", "donut", "share of the main measure by a category (<=6 slices)", 8, 2, 4, 4),
            _s("compare", "column", "main measure by a second category", 0, 6, 6, 4),
            _s("detail", "table", "top 10 records/entities by main measure", 6, 6, 6, 4),
        ],
    },
    {
        "id": "finance_pnl",
        "name": "Finance P&L",
        "description": "Revenue, expense, net profit and margin; stacked revenue vs expense by month; expense mix; cash trend.",
        "theme": {"palette": PALETTE},
        "slots": [
            _s("revenue", "kpi", "total revenue", 0, 0, 3, 2),
            _s("expense", "kpi", "total expense", 3, 0, 3, 2),
            _s("profit", "kpi", "net profit (revenue minus expense)", 6, 0, 3, 2),
            _s("margin", "kpi", "net profit margin percent", 9, 0, 3, 2),
            _s("rev_vs_exp", "stacked_column", "revenue and expense by month (account type as series)", 0, 2, 8, 4),
            _s("exp_mix", "pie", "expense by account / category", 8, 2, 4, 4),
            _s("cash", "area", "net cash movement or balance by month", 0, 6, 6, 4),
            _s("top_accounts", "table", "top accounts by amount with type", 6, 6, 6, 4),
        ],
    },
    {
        "id": "sales",
        "name": "Sales Performance",
        "description": "Sales KPIs, monthly trend, breakdown by region/segment, product mix and top-customer ranking.",
        "theme": {"palette": PALETTE},
        "slots": [
            _s("sales", "kpi", "total sales / invoiced amount", 0, 0, 4, 2),
            _s("orders", "kpi", "number of invoices or orders", 4, 0, 4, 2),
            _s("avg", "kpi", "average invoice value", 8, 0, 4, 2),
            _s("trend", "line", "sales by month", 0, 2, 7, 4),
            _s("segment", "column", "sales by region / segment / customer group", 7, 2, 5, 4),
            _s("product_mix", "donut", "sales share by product or category", 0, 6, 4, 4),
            _s("top_customers", "bar", "top 10 customers by sales", 4, 6, 8, 4),
        ],
    },
    {
        "id": "receivables",
        "name": "Receivables & Payables",
        "description": "Outstanding AR/AP, aging buckets stacked by party type, overdue ranking and open-item detail.",
        "theme": {"palette": PALETTE},
        "slots": [
            _s("ar", "kpi", "total outstanding receivables", 0, 0, 4, 2),
            _s("ap", "kpi", "total outstanding payables", 4, 0, 4, 2),
            _s("overdue", "kpi", "amount overdue (past due date)", 8, 0, 4, 2),
            _s("aging", "stacked_column", "outstanding amount by aging bucket (0-30, 31-60, 61-90, 90+) split by invoice type", 0, 2, 7, 4),
            _s("status_mix", "pie", "invoice amount by status", 7, 2, 5, 4),
            _s("top_overdue", "bar", "top 10 parties by overdue amount", 0, 6, 6, 4),
            _s("open_items", "table", "open invoices with party, due date, amount", 6, 6, 6, 4),
        ],
    },
    {
        "id": "analyst",
        "name": "Analyst Workbench",
        "description": "One headline KPI, a stacked comparison, a column chart and a large detail table for ad-hoc analysis.",
        "theme": {"palette": PALETTE},
        "slots": [
            _s("headline", "kpi", "the single number that answers the question", 0, 0, 4, 2),
            _s("stacked", "stacked_column", "the main measure by two dimensions", 4, 0, 8, 4),
            _s("column", "column", "the main measure by one dimension", 0, 2, 4, 4),
            _s("table", "table", "detailed rows supporting the answer", 0, 6, 12, 5),
        ],
    },
]

TEMPLATE_BY_ID = {t["id"]: t for t in TEMPLATES}
