"""
Dashboard-wide filters: a date range, or a category such as region.

When a filter is added, an AI model picks the column each chart's query should filter on
(map_filter). The choice is saved in the report config, so viewing never needs the model:

    {"id", "label", "kind": "date" | "category", "options": [...],
     "columns": {widget_id: {"table": "schema.table", "column": "name"}}}

When the dashboard is viewed, apply() replaces each mapped table in a chart's saved SQL with a
subquery that keeps only the matching rows:

    FROM main.orders o   ->   FROM (SELECT * FROM main.orders WHERE "region" IN (:bi_p0)) AS o

so totals and counts are filtered too, not only the rows a chart shows. The values are bound
parameters, never written into the SQL, and run_sql checks the result with sql_guard again. A chart
with no column for a filter isn't filtered by it, and the viewer says so.
"""

import datetime as dt
import uuid

import sqlglot
from sqlglot import exp
from sqlglot.errors import SqlglotError

from .ai.providers import ModelSpec, complete_json
from .connections import openpages
from .datasources import DataSource, column_values, table_columns
from .sql_guard import DIALECTS

KINDS = ("date", "category")
MAX_OPTIONS = 200

_MAP_SCHEMA = {
    "type": "object",
    "properties": {
        "columns": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"widget_id": {"type": "string"}, "table": {"type": "string"}, "column": {"type": "string"}},
                "required": ["widget_id", "table", "column"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["columns"],
    "additionalProperties": False,
}


def _parse(sql: str, source: DataSource) -> exp.Expression | None:
    try:
        return sqlglot.parse_one(sql, read=DIALECTS[source.db_type])
    except (SqlglotError, ValueError):
        return None


def _resolve(table: exp.Table, source: DataSource, cte_names: set[str]) -> str | None:
    """The allowed "schema.table" a table reference reads, or None (a CTE, or not allowed)."""
    name, schema = table.name.lower(), table.db.lower()
    if not name or (not schema and name in cte_names):
        return None
    if schema:
        return f"{schema}.{name}" if f"{schema}.{name}" in source.allowed else None
    return next((t for t in sorted(source.allowed) if t.split(".")[-1] == name), None)


def query_tables(sql: str, source: DataSource) -> list[str]:
    """The allowed tables one query reads, in order of appearance."""
    if source.is_openpages:
        by_name = {t.split(".", 1)[-1].lower(): t.lower() for t in source.tables}
        return [by_name[n.lower()] for n in openpages.query_types(sql) if n.lower() in by_name]
    tree = _parse(sql, source)
    if tree is None:
        return []
    ctes = {c.alias_or_name.lower() for c in tree.find_all(exp.CTE)}
    out = []
    for t in tree.find_all(exp.Table):
        q = _resolve(t, source, ctes)
        if q and q not in out:
            out.append(q)
    return out


# ---------- At view time ----------

def is_active(f: dict, value: dict | None) -> bool:
    if not value:
        return False
    if f.get("kind") == "date":
        return bool(value.get("date_from") or value.get("date_to"))
    return bool(value.get("values"))


def apply(sql: str, source: DataSource, filters: list[dict], values: dict, widget_id: str) -> tuple[str, dict, list[str], list[str]]:
    """Returns (sql, params, applied filter ids, filter ids that don't apply to this chart).

    values: filter id -> {"date_from", "date_to"} (dates) or {"values": [...]}. Only filters with a
    value count; the others are left out of both lists."""
    active = [f for f in filters if is_active(f, values.get(f.get("id")))]
    if not active:
        return sql, {}, [], []
    if source.is_openpages:
        return _apply_openpages(sql, source, active, values, widget_id)
    tree = _parse(sql, source)
    if tree is None:
        return sql, {}, [], [f["id"] for f in active]  # run_sql will report the SQL problem
    ctes = {c.alias_or_name.lower() for c in tree.find_all(exp.CTE)}
    refs = [(t, _resolve(t, source, ctes)) for t in tree.find_all(exp.Table)]
    present = {q for _, q in refs if q}

    params: dict = {}
    conditions: dict[str, list[exp.Expression]] = {}
    applied, skipped = [], []
    for f in active:
        target = (f.get("columns") or {}).get(widget_id) or {}
        table, column = str(target.get("table", "")).lower(), str(target.get("column", ""))
        if not column or table not in present:
            skipped.append(f["id"])
            continue
        conditions.setdefault(table, []).append(_condition(f, values[f["id"]], column, source, params))
        applied.append(f["id"])
    if not conditions:
        return sql, {}, [], skipped

    for t, q in refs:
        if q not in conditions:
            continue
        inner = t.copy()
        inner.set("alias", None)
        alias = t.alias or t.name
        sub = exp.select("*").from_(inner).where(exp.and_(*[c.copy() for c in conditions[q]])).subquery(alias)
        t.replace(sub)
    return tree.sql(dialect=DIALECTS[source.db_type]), params, applied, skipped


def _apply_openpages(sql: str, source: DataSource, active: list[dict], values: dict, widget_id: str):
    """OpenPages has no bound parameters or subqueries: conditions go into the WHERE, with values
    written as quoted literals (quotes doubled), and run_sql checks the SQL again."""
    present = {t.lower() for t in query_tables(sql, source)}
    conditions, applied, skipped = [], [], []
    for f in active:
        target = (f.get("columns") or {}).get(widget_id) or {}
        table, column = str(target.get("table", "")), str(target.get("column", ""))
        if not column or table.lower() not in present:
            skipped.append(f["id"])
            continue
        ref = openpages.field_ref(source.op_type(table), column)
        value = values[f["id"]]
        if f.get("kind") == "date":
            parts = []
            if value.get("date_from"):
                parts.append(f"{ref} >= {openpages.quote(_date(value['date_from']).isoformat())}")
            if value.get("date_to"):
                parts.append(f"{ref} < {openpages.quote((_date(value['date_to']) + dt.timedelta(days=1)).isoformat())}")
            conditions.append(" AND ".join(parts))
        else:
            vals = [str(v) for v in value["values"]]
            conditions.append(" OR ".join(f"{ref} = {openpages.quote(v)}" for v in vals))
        applied.append(f["id"])
    return openpages.add_conditions(sql, conditions), {}, applied, skipped


def _condition(f: dict, value: dict, column: str, source: DataSource, params: dict) -> exp.Expression:
    col = exp.column(column, quoted=True)

    def bind(v) -> exp.Placeholder:
        name = f"bi_p{len(params)}"
        params[name] = v
        return exp.Placeholder(this=name)

    if f.get("kind") == "date":
        # SQLite keeps dates as text, so compare with text; the others get real dates.
        as_param = (lambda d: d.isoformat()) if source.db_type == "sqlite" else (lambda d: d)
        parts = []
        if value.get("date_from"):
            parts.append(col.copy() >= bind(as_param(_date(value["date_from"]))))
        if value.get("date_to"):
            # Before the next day, so timestamps during the last day count.
            parts.append(col.copy() < bind(as_param(_date(value["date_to"]) + dt.timedelta(days=1))))
        return exp.and_(*parts)
    return col.isin(*[bind(str(v)) for v in value["values"]])


def _date(v) -> dt.date:
    return v if isinstance(v, dt.date) else dt.date.fromisoformat(str(v))


# ---------- At design time ----------

def chart_tables(source: DataSource, widgets: list[dict]) -> tuple[dict[str, list[str]], dict[str, list[tuple[str, str]]]]:
    """(chart id -> tables its query reads, table -> its columns as (name, type))."""
    tables: dict[str, list[tuple[str, str]]] = {}
    per_widget: dict[str, list[str]] = {}
    for w in widgets:
        if w.get("kind", "chart") == "text":
            continue  # text tiles have no query, so nothing to filter
        per_widget[w["id"]] = query_tables(w.get("sql", ""), source)
        for t in per_widget[w["id"]]:
            if t not in tables:
                tables[t] = table_columns(source, t)
    return per_widget, tables


def filter_columns(source: DataSource, widgets: list[dict]) -> dict[str, list[dict]]:
    """For choosing filter columns by hand: chart id -> [{"table", "columns": [{"name", "type"}]}]."""
    per_widget, tables = chart_tables(source, widgets)
    return {wid: [{"table": t, "columns": [{"name": n, "type": ty} for n, ty in tables.get(t, [])]} for t in ts]
            for wid, ts in per_widget.items()}


def make_filter(source: DataSource, label: str, kind: str, widgets: list[dict], picks: dict[str, dict],
                filter_id: str | None = None) -> dict:
    """Builds a filter for the report config from chosen columns (chart id -> {"table", "column"}).
    Each choice must be a real column of a table that chart's query reads; others are dropped, so a
    chart is "Not filtered" rather than filtered on the wrong thing. Category filters get the values
    people can pick from the chosen columns."""
    per_widget, tables = chart_tables(source, widgets)
    columns: dict[str, dict] = {}
    for wid, pick in picks.items():
        if not isinstance(pick, dict):
            continue
        table, column = str(pick.get("table", "")).lower(), str(pick.get("column", ""))
        allowed = per_widget.get(str(wid), [])
        table = table if table in allowed else next((t for t in allowed if t.split(".")[-1] == table.split(".")[-1]), "")
        real = next((n for n, _ in tables.get(table, []) if n.lower() == column.lower()), None) if table else None
        if real:
            columns[str(wid)] = {"table": table, "column": real}
    options: list[str] = []
    if kind == "category":
        for target in {(c["table"], c["column"]) for c in columns.values()}:
            options.extend(column_values(source, *target, limit=MAX_OPTIONS))
        options = sorted(set(options))[:MAX_OPTIONS]
    return {"id": filter_id or uuid.uuid4().hex[:8], "label": label.strip()[:60], "kind": kind,
            "options": options, "columns": columns}


def map_filter(spec: ModelSpec, source: DataSource, label: str, kind: str, widgets: list[dict],
               filter_id: str | None = None) -> dict:
    """Asks the model which column each chart should filter on, and checks every answer against the
    tables the chart reads. Returns a filter for the report config."""
    per_widget, tables = chart_tables(source, widgets)

    meaning = ("a date range (choose a date or timestamp column; the main date of each row, such as the order or sale date)"
               if kind == "date" else
               f'a list of values of "{label}" (choose the text column that holds those values)')
    system = f"""You map a dashboard filter to database columns. The filter is "{label}": {meaning}.
For each chart, pick the one table and column in that chart's query the filter should apply to.
Use only tables the chart's query reads and columns those tables have, exactly as listed.
When none fits, give an empty table and column for that chart. Never guess a column that means
something else."""
    blocks = []
    for w in widgets:
        if w["id"] not in per_widget:
            continue  # a text tile
        cols = "\n".join(f"  {t}: " + ", ".join(f"{n} {ty}" for n, ty in tables.get(t, [])) for t in per_widget[w["id"]])
        blocks.append(f"Chart {w['id']}: {w.get('title', '')}\nQuery: {w.get('sql', '')[:1500]}\nTables:\n{cols or '  (none)'}")
    answer = complete_json(spec, system, "\n\n".join(blocks), _MAP_SCHEMA)
    picks = {str(item.get("widget_id", "")): item for item in answer.get("columns") or [] if isinstance(item, dict)}
    return make_filter(source, label, kind, widgets, picks, filter_id)
