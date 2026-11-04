"""
Chat with a database, and build dashboards from a prompt.

The model writes SQL and a small chart spec; it never runs anything itself. Every query goes
through sql_guard and runs read-only (datasources.run_sql). When a query fails, the error goes back
to the model, which gets up to MAX_ATTEMPTS tries in total.

What the model sees: the question, recent conversation turns, the chosen tables' columns (with the
values of low-cardinality text columns), and, to explain an answer, at most 20 result rows.
"""

import datetime as dt
import json
import time
import uuid

from ..datasources import DataSource, QueryFailed, describe, run_sql
from ..sql_guard import UnsafeSQL
from .providers import ModelSpec, complete_json

MAX_ATTEMPTS = 3
ROWS_SHOWN_TO_MODEL = 20
CHART_TYPES = ["kpi", "bar", "line", "area", "pie", "table"]

_DIALECT_TIPS = {
    "postgresql": "PostgreSQL: DATE_TRUNC('month', d), EXTRACT(YEAR FROM d), d >= DATE '2024-01-01', LIMIT n.",
    "mysql": "MySQL: DATE_FORMAT(d, '%Y-%m-01'), YEAR(d), MONTH(d), d >= '2024-01-01', LIMIT n. Quote names with backticks.",
    "mssql": "SQL Server: DATEFROMPARTS(YEAR(d), MONTH(d), 1), YEAR(d), d >= '2024-01-01', TOP n (never LIMIT). Quote names with [brackets].",
    "sqlite": "SQLite: strftime('%Y-%m', d), CAST(strftime('%Y', d) AS INTEGER), d >= '2024-01-01', LIMIT n.",
    "openpages": "IBM OpenPages Query Service SQL, as described above: [brackets] around every type and field, "
                 "hierarchy joins (PARENT/CHILD/ANCESTOR/DESCENDANT), no LIMIT or TOP, no subqueries or CASE.",
}

_CHART_SCHEMA = {
    "type": "object",
    "properties": {
        "type": {"type": "string", "enum": CHART_TYPES},
        "x": {"type": "string"},
        "y": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["type", "x", "y"],
    "additionalProperties": False,
}

_ANSWER_SCHEMA = {
    "type": "object",
    "properties": {
        "action": {"type": "string", "enum": ["query", "reply"]},
        "reply": {"type": "string"},
        "title": {"type": "string"},
        "sql": {"type": "string"},
        "chart": _CHART_SCHEMA,
    },
    "required": ["action", "reply", "title", "sql", "chart"],
    "additionalProperties": False,
}

_EXPLAIN_SCHEMA = {
    "type": "object",
    "properties": {"answer": {"type": "string"}},
    "required": ["answer"],
    "additionalProperties": False,
}

_PLAN_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "widgets": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"title": {"type": "string"}, "question": {"type": "string"},
                               "sql": {"type": "string"}, "chart": _CHART_SCHEMA},
                "required": ["title", "question", "sql", "chart"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["title", "widgets"],
    "additionalProperties": False,
}

_CHART_RULES = """Chart types: "kpi" for one number; "line" or "area" for a value over time; "bar" to compare
categories; "pie" for shares of a whole with at most 8 parts; "table" for detailed rows. "x" is the
column holding categories or dates (empty for kpi), "y" lists the numeric columns to plot."""


def _sql_rules(source: DataSource) -> str:
    today = dt.date.today()
    return f"""Database: {source.name} ({source.type_label}). Write {source.type_label} SQL.
Tables you may use, and nothing else (write table names exactly as listed). Text after "--" describes
a column; follow it exactly, for example whether an amount is money or a percentage:

{describe(source)}

Today is {today.isoformat()} ({today:%A}). Use this date for words like "this year", "last month" or "today".

SQL rules: one SELECT query only. Never change data. Use only the tables above. {_alias_rule(source)}
Aggregate where it helps; return at most 500 rows.
Date and limit syntax for this database: {_DIALECT_TIPS[source.db_type]}"""


def _alias_rule(source: DataSource) -> str:
    if source.db_type == "openpages":
        return "Never use AS: OpenPages columns keep their field names (counts are \"Count_Resource ID\")."
    return "Give every computed column a short readable alias."


class AssistantError(Exception):
    """The question couldn't be answered. The message is safe to show."""


# ---------- Chat ----------

def chat(spec: ModelSpec, source: DataSource, question: str, history: list[dict]) -> dict:
    """Answers one chat message. history: earlier turns, oldest first: {"question", "reply", "sql"}."""
    t0 = time.perf_counter()
    system = f"""You are a data analyst inside a BI tool. People ask questions about their database in plain
language, and you answer them.

{_sql_rules(source)}

Decide the action:
- "query" when the question needs data: write sql, a short title for the result, and a chart.
- "reply" when no query is needed (what data exists, what a column means, how to phrase a question)
  or the tables can't answer it: write the full answer in reply, and leave sql empty.

{_CHART_RULES}"""
    context = _history_text(history)
    prompt = f"{context}Question: {question}"
    answer, data, attempts = _query_with_retries(spec, source, system, prompt)
    if answer["action"] == "reply":
        return {"kind": "reply", "reply": answer["reply"].strip() or "I couldn't find an answer to that.",
                "attempts": attempts, "elapsed_ms": _ms(t0)}
    reply = _explain(spec, question, data)
    return {"kind": "result", "reply": reply, "title": answer["title"].strip() or question[:80],
            "chart": fit_chart(answer.get("chart"), data["columns"], data["rows"]),
            "attempts": attempts, "elapsed_ms": _ms(t0), **data}


def write_widget(spec: ModelSpec, source: DataSource, question: str) -> dict:
    """One dashboard widget for a question ("add a widget by asking"). Raises AssistantError."""
    system = f"""You write one SQL query for one chart on a BI dashboard.

{_sql_rules(source)}

Always use action "query". {_CHART_RULES}"""
    answer, data, attempts = _query_with_retries(spec, source, system, f"Chart request: {question}")
    if answer["action"] != "query":
        raise AssistantError(answer["reply"] or "The model couldn't write a query for that.")
    widget = new_widget(answer["title"] or question, question, data["sql"],
                        fit_chart(answer.get("chart"), data["columns"], data["rows"]))
    return {"widget": widget, "data": data, "attempts": attempts}


def revise_widget(spec: ModelSpec, source: DataSource, widget: dict, instruction: str) -> dict:
    """Changes one chart as asked ("only completed orders", "by week", "top 5 instead"). Keeps the
    chart's id and size; the new query is checked and run like any other. Raises AssistantError."""
    system = f"""You change one chart on a BI dashboard. You get the chart's current title, the question it
answers, and its SQL. Rewrite them so the chart does what the change asks, keeping everything the
change doesn't mention. Give a short new title.

{_sql_rules(source)}

Always use action "query". {_CHART_RULES}"""
    prompt = (f"Current title: {widget.get('title', '')}\nCurrent question: {widget.get('question', '')}\n"
              f"Current SQL: {widget.get('sql', '')}\nCurrent chart: {json.dumps(widget.get('chart') or {})}\n\n"
              f"Change requested: {instruction}")
    answer, data, attempts = _query_with_retries(spec, source, system, prompt)
    if answer["action"] != "query":
        raise AssistantError(answer["reply"] or "The model couldn't change the chart that way.")
    revised = {**widget, "title": (answer["title"] or widget.get("title", ""))[:120],
               "question": f"{widget.get('question', '')} ({instruction})".strip()[:500], "sql": data["sql"],
               "chart": fit_chart(answer.get("chart"), data["columns"], data["rows"])}
    return {"widget": revised, "data": data, "attempts": attempts}


def _query_with_retries(spec: ModelSpec, source: DataSource, system: str, prompt: str):
    attempts: list[dict] = []
    feedback = ""
    for n in range(1, MAX_ATTEMPTS + 1):
        answer = _normalize(complete_json(spec, system, prompt + feedback, _ANSWER_SCHEMA))
        if answer.get("action") != "query":
            return answer, None, attempts
        sql = str(answer.get("sql", "")).strip()
        try:
            data = run_sql(source, sql)
            attempts.append({"ok": True, "message": f"Attempt {n}: the query is read-only and ran in "
                                                    f"{data['elapsed_ms']} ms ({data['row_count']} rows)."})
            return answer, data, attempts
        except (UnsafeSQL, QueryFailed) as err:
            attempts.append({"ok": False, "message": f"Attempt {n} failed: {err}", "sql": sql})
            feedback = (f"\n\nYour previous query failed.\nQuery: {sql}\nError: {err}\n"
                        "Write a corrected query that follows the rules.")
    last_error = attempts[-1]["message"].split(": ", 1)[-1]
    raise AssistantError(f"The model couldn't write a working query in {MAX_ATTEMPTS} tries. Last error: {last_error}")


def _normalize(answer: dict) -> dict:
    """Accepts answers close to the schema. Models that don't enforce it sometimes give the chart as
    a word ("bar") with x and y alongside it, leave fields out, or skip the action."""
    answer = dict(answer)
    chart = answer.get("chart")
    if not isinstance(chart, dict):
        y = answer.get("y")
        chart = {"type": chart or "", "x": answer.get("x") or "", "y": y if isinstance(y, list) else [y] if y else []}
    y = chart.get("y") or []
    answer["chart"] = {"type": str(chart.get("type") or "").lower(), "x": str(chart.get("x") or ""),
                       "y": [str(c) for c in (y if isinstance(y, list) else [y]) if c]}
    for key in ("reply", "title", "sql", "question"):
        answer[key] = str(answer.get(key) or "")
    if answer.get("action") not in ("query", "reply"):
        answer["action"] = "query" if answer["sql"].strip() else "reply"
    return answer


def _explain(spec: ModelSpec, question: str, data: dict) -> str:
    if not data["rows"]:
        return "The query ran, but no rows match."
    sample = [dict(zip(data["columns"], row)) for row in data["rows"][:ROWS_SHOWN_TO_MODEL]]
    more = f" (showing the first {ROWS_SHOWN_TO_MODEL} of {data['row_count']})" if data["row_count"] > ROWS_SHOWN_TO_MODEL else ""
    try:
        answer = complete_json(
            spec,
            "You explain query results to business people in plain language: 2 to 4 sentences, the key "
            "numbers, no SQL or technical words. Use only the numbers given; don't invent any.",
            f"Question: {question}\nResult rows{more}:\n{json.dumps(sample, default=str)[:6000]}",
            _EXPLAIN_SCHEMA)
        return str(answer.get("answer", "")).strip() or "Here are the results."
    except Exception:
        return "Here are the results."  # the data is still shown; the summary is a nice-to-have


def _history_text(history: list[dict]) -> str:
    turns = history[-6:]
    if not turns:
        return ""
    lines = ["Earlier in this conversation:"]
    for t in turns:
        lines.append(f"- Asked: {str(t.get('question', ''))[:300]}")
        if t.get("sql"):
            lines.append(f"  Query used: {str(t['sql'])[:600]}")
        if t.get("reply"):
            lines.append(f"  Answer: {str(t['reply'])[:300]}")
    return "\n".join(lines) + "\n\n"


# ---------- Dashboards ----------

def plan_dashboard(spec: ModelSpec, source: DataSource, prompt: str, parameters: dict) -> dict:
    """Plans and runs a dashboard. Returns {"title", "widgets": [...], "failed": [...]}."""
    params_text = _parameters_text(parameters)
    system = f"""You design BI dashboards. Turn the request into 4 to 6 charts that answer it well.
Start with 1 to 3 "kpi" charts for the headline numbers, then charts that break them down
(over time, by category, top items).

{_sql_rules(source)}

Each chart needs a title, a one-line question it answers, one SQL query, and a chart.
{params_text}
{_CHART_RULES}"""
    plan = complete_json(spec, system, f"Dashboard request: {prompt}", _PLAN_SCHEMA)
    plan["widgets"] = [_normalize(w) for w in plan.get("widgets") or [] if isinstance(w, dict)]
    widgets, failed = [], []
    for item in (plan.get("widgets") or [])[:8]:
        title, question = str(item.get("title", "")).strip(), str(item.get("question", "")).strip()
        try:
            data = run_sql(source, str(item.get("sql", "")))
            widgets.append(new_widget(title or question, question, data["sql"],
                                      fit_chart(item.get("chart"), data["columns"], data["rows"])))
        except (UnsafeSQL, QueryFailed) as err:
            # One more try with the error, using the single-widget writer.
            try:
                fixed = write_widget(spec, source, f"{question or title}{' ' + params_text if params_text else ''}"
                                                   f"\n(An earlier query for this failed: {err})")
                fixed["widget"]["title"] = title or fixed["widget"]["title"]
                widgets.append(fixed["widget"])
            except Exception as err2:
                failed.append({"title": title or question, "error": str(err2)[:300]})
    if not widgets:
        raise AssistantError("The model couldn't build any working charts for that request. "
                             "Try naming the tables or measures you want.")
    return {"title": str(plan.get("title", "")).strip() or prompt[:80], "widgets": widgets, "failed": failed}


def _parameters_text(parameters: dict) -> str:
    parts = []
    if parameters.get("date_from") or parameters.get("date_to"):
        parts.append(f"dates from {parameters.get('date_from') or 'the start'} to {parameters.get('date_to') or 'today'} "
                     "(use the main date column of each table)")
    if parameters.get("filters"):
        parts.append(f"only rows where {parameters['filters']}")
    if not parts:
        return ""
    return "Apply these parameters to every chart where the table allows it: " + "; ".join(parts) + "."


def new_widget(title: str, question: str, sql: str, chart: dict) -> dict:
    return {"id": uuid.uuid4().hex[:8], "title": title.strip()[:120], "question": question.strip()[:500],
            "sql": sql, "chart": chart}


# ---------- Charts ----------

def fit_chart(suggested: dict | None, columns: list[str], rows: list[list]) -> dict:
    """Keeps the model's chart when it fits the result; otherwise picks one from the result's shape:
    one number -> kpi, a date column -> line, a few parts of a whole -> pie, categories -> bar."""
    numeric = [c for i, c in enumerate(columns) if _is_numeric_column(rows, i)]
    others = [c for c in columns if c not in numeric]
    s = suggested or {}
    kind, x = s.get("type"), s.get("x") or ""
    y = [c for c in (s.get("y") or []) if c in numeric]
    if kind == "table":
        return {"type": "table", "x": "", "y": []}
    if kind == "kpi" and numeric and len(rows) == 1:
        return {"type": "kpi", "x": "", "y": y or numeric[:1]}
    if kind in ("bar", "line", "area", "pie") and x in others and y:
        return {"type": kind, "x": x, "y": y if kind != "pie" else y[:1]}
    # The suggestion doesn't fit: choose from the shape of the result.
    if len(rows) == 1 and numeric:
        return {"type": "kpi", "x": "", "y": numeric[:1]}
    if not numeric or not others:
        return {"type": "table", "x": "", "y": []}
    x = others[0]
    if _looks_like_dates(rows, columns.index(x)):
        return {"type": "line", "x": x, "y": numeric[:3]}
    if len(rows) <= 6 and len(numeric) == 1:
        return {"type": "pie", "x": x, "y": numeric[:1]}
    return {"type": "bar", "x": x, "y": numeric[:3]}


def _is_numeric_column(rows: list[list], i: int) -> bool:
    values = [r[i] for r in rows if r[i] is not None]
    return bool(values) and all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in values)


def _looks_like_dates(rows: list[list], i: int) -> bool:
    values = [str(r[i]) for r in rows[:20] if r[i] is not None]
    return bool(values) and all(len(v) >= 7 and v[:4].isdigit() and v[4] == "-" for v in values)


def _ms(t0: float) -> int:
    return round((time.perf_counter() - t0) * 1000)
