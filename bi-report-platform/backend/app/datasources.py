"""
The databases people can chat with and build dashboards from.

- The built-in sample: the sales table in the app database, so chat works before any connection exists.
- Each saved connection, limited to the tables a manager chose on the Connections page.

Queries are checked by sql_guard first, then run read-only with a timeout, and at most MAX_ROWS rows
come back. Results are kept for RESULT_CACHE_SECONDS, so opening a dashboard again doesn't query
every database again.
"""

import datetime as dt
import re
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass, field, replace
from decimal import Decimal

from sqlalchemy import Engine, MetaData, Table, distinct, func, inspect, select
from sqlalchemy.orm import Session

from . import openpages_model
from .config import settings
from .connections import connection_spec, openpages, openpages_spec
from .connections.engines import DB_TYPES, friendly_error, get_engine
from .database import engine as app_engine
from .models import DataConnection
from .sql_guard import UnsafeSQL, check_sql

MAX_ROWS = 500
TIMEOUT_SECONDS = 15
SCHEMA_CACHE_SECONDS = 600
RESULT_CACHE_SECONDS = 15 * 60
RESULT_CACHE_SIZE = 300  # results, each at most MAX_ROWS rows
BUILTIN_NAME = "Sample sales data"


@dataclass
class DataSource:
    id: int | None  # None is the built-in sample
    name: str
    db_type: str
    tables: list[str]  # "schema.table", as chosen on the Connections page
    version: str  # changes when the connection changes, so cached schema descriptions refresh
    engine: Engine | None = field(default=None, repr=False)
    client: openpages.OpenPagesClient | None = field(default=None, repr=False)  # IBM OpenPages: its REST API
    options: dict = field(default_factory=dict, repr=False)

    @property
    def is_openpages(self) -> bool:
        return self.db_type == "openpages"

    def op_type(self, qualified: str) -> str:
        """An OpenPages object type name as OpenPages writes it, from "openpages.soxissue" or "SOXIssue"."""
        bare = qualified.split(".", 1)[-1]
        return next((t.split(".", 1)[-1] for t in self.tables if t.split(".", 1)[-1].lower() == bare.lower()), bare)

    @property
    def type_label(self) -> str:
        return DB_TYPES[self.db_type]["label"]

    @property
    def allowed(self) -> set[str]:
        return {t.lower() for t in self.tables}


class SourceError(Exception):
    """The source can't be used right now. The message is safe to show."""


def _builtin(with_engine: bool) -> DataSource:
    db_type = app_engine.dialect.name if app_engine.dialect.name in DB_TYPES else "postgresql"
    schema = "main" if db_type == "sqlite" else "public"
    return DataSource(id=None, name=BUILTIN_NAME, db_type=db_type, tables=[f"{schema}.sales"], version="builtin",
                      engine=app_engine if with_engine else None)


def list_sources(db: Session) -> list[DataSource]:
    """Every source with at least one table people may query. No engines are created."""
    out = [_builtin(with_engine=False)]
    for c in db.scalars(select(DataConnection).order_by(func.lower(DataConnection.name))).all():
        if c.allowed_tables:
            out.append(DataSource(id=c.id, name=c.name, db_type=c.db_type, tables=list(c.allowed_tables),
                                  version=c.updated_at.isoformat()))
    return out


def get_source(db: Session, source_id: int | None) -> DataSource:
    if source_id is None:
        return _builtin(with_engine=True)
    c = db.get(DataConnection, source_id)
    if c is None:
        raise SourceError("That database connection no longer exists.")
    if not c.allowed_tables:
        raise SourceError(f"No tables have been shared from {c.name} yet. Ask a manager to choose tables on the Connections page.")
    version = c.updated_at.isoformat()
    if c.db_type == "openpages":
        try:
            client = openpages.get_client(c.id, version, openpages_spec(c))
        except Exception as err:  # the CONNECTIONS_KEY problem, or an unreadable certificate
            raise SourceError(str(err))
        return DataSource(id=c.id, name=c.name, db_type=c.db_type, tables=list(c.allowed_tables), version=version,
                          client=client, options=dict(c.options or {}))
    try:
        spec = connection_spec(c)
    except Exception as err:  # the CONNECTIONS_KEY problem has its own readable message
        raise SourceError(str(err))
    return DataSource(id=c.id, name=c.name, db_type=c.db_type, tables=list(c.allowed_tables), version=version,
                      engine=get_engine(c.id, version, spec))


def narrow(source: DataSource, data_model: str | None) -> DataSource:
    """The same source seen through one OpenPages data model: only that model's object types, and
    its relationships passed on to whoever writes the SQL.

    Narrowing the table list is the whole mechanism. `allowed` and `op_type` are both derived from
    it, so the SQL guard refuses a type outside the model without knowing models exist, and the
    schema description shrinks to what the model covers - which is the point, since a model is how
    someone says "this report is about audits, not vendors".
    """
    model = openpages_model.get(data_model)
    if model is None or not source.is_openpages:
        return source
    want = {e.lower() for e in model.entities}
    tables = [t for t in source.tables if t.split(".", 1)[-1].lower() in want]
    if not tables:
        raise SourceError(f"None of the object types in {model.name} are shared from {source.name}. "
                          "Choose another data model, or ask a manager to share those types on the "
                          "Connections page.")
    return replace(source, tables=tables, options={**source.options, "data_model": model.key})


# ---------- Describing the tables for the model ----------

# The expensive half: one text block per table, read from the database or OpenPages. Cached as a
# whole, because for OpenPages it is one HTTP request per object type and a connection may share
# well over a hundred of them.
_blocks_cache: dict[tuple, tuple[float, dict[str, str]]] = {}


def forget_schema(connection_id: int | None = None):
    """Drops cached schema descriptions so the next one is read from the database again."""
    for key in [k for k in _blocks_cache if connection_id is None or k[0] == connection_id]:
        del _blocks_cache[key]


def _cache_key(source: DataSource) -> tuple:
    return (source.id, source.version, tuple(source.tables))


def warm_schema(source: DataSource) -> int:
    """Reads and caches a source's schema up front. Called when a connection's tables are chosen,
    so the first question doesn't pay for a hundred requests to OpenPages. Returns the table count."""
    return len(_schema_blocks(source))


def _schema_blocks(source: DataSource) -> dict[str, str]:
    """{table: its description}, cached. Reading is what costs; choosing what to show is free."""
    key = _cache_key(source)
    hit = _blocks_cache.get(key)
    if hit and time.time() - hit[0] < SCHEMA_CACHE_SECONDS:
        return hit[1]
    blocks = _openpages_blocks(source) if source.is_openpages else _sql_blocks(source)
    _blocks_cache[key] = (time.time(), blocks)
    return blocks


def _sql_blocks(source: DataSource) -> dict[str, str]:
    insp = inspect(source.engine)
    blocks: dict[str, str] = {}
    for qualified in source.tables:
        schema, _, name = qualified.rpartition(".")
        try:
            columns = insp.get_columns(name, schema=schema or None)
        except Exception:
            continue  # dropped since it was chosen, or no longer visible to the account
        lines = []
        table, reflected = None, False
        for col in columns:
            line = f"  {col['name']} {col['type']}"
            if col.get("comment"):
                line += f"  -- {' '.join(str(col['comment']).split())[:200]}"
            if _is_text(col["type"]) and len(blocks) < 30:
                if not reflected:
                    table, reflected = _reflect(source.engine, name, schema), True
                values = _few_values(source.engine, table, col["name"]) if table is not None else None
                if values:
                    line += ("; " if "  -- " in line else "  -- ") + "values: " + ", ".join(repr(v) for v in values)
            lines.append(line)
        blocks[qualified] = f"{qualified}\n" + "\n".join(lines)
    return blocks


def _openpages_blocks(source: DataSource) -> dict[str, str]:
    blocks: dict[str, str] = {}
    for qualified in source.tables:
        name = qualified.split(".", 1)[-1]
        lines = []
        for f in source.client.type_fields(name)[:80]:
            line = f"  [{f['name']}] {f['type']}"
            if f["values"] and len(f["values"]) <= 15:
                line += "  -- values: " + ", ".join(repr(v) for v in f["values"])
            lines.append(line)
        blocks[qualified] = f"[{name}]\n" + "\n".join(lines)
    return blocks


# ---------- Choosing which tables the model is shown ----------

# Roughly how many characters make a token. Only used to turn a token budget into a character
# budget, so it needs to be about right rather than exact.
CHARS_PER_TOKEN = 3.5

_WORD = re.compile(r"[A-Za-z][A-Za-z0-9]*")
# Words that match almost everything, so they say nothing about which table is wanted.
_STOP = {"the", "and", "for", "with", "all", "any", "show", "give", "list", "chart", "charts", "report",
         "reports", "dashboard", "create", "build", "make", "simple", "using", "available", "include",
         "following", "each", "per", "total", "count", "number", "data", "field", "fields", "object",
         "objects", "table", "tables", "card", "cards", "kpi", "bar", "pie", "donut", "line", "add",
         "interactive", "filter", "filters", "value", "values", "name", "names", "from", "where", "ibm",
         "openpages", "new", "old", "top", "this", "that", "are", "was", "has", "have", "its", "one"}


def _terms(text: str) -> set[str]:
    """The meaningful words in a name or a question, with CamelCase split apart so "SOXProcess"
    matches someone asking about a "process"."""
    out = set()
    for word in _WORD.findall(text):
        parts = re.findall(r"[A-Z]+(?![a-z])|[A-Z][a-z]+|[a-z]+|\d+", word) or [word]
        for part in parts:
            part = part.lower()
            if len(part) > 2 and part not in _STOP:
                out.add(part)
                # "processes" should match "process"; a crude stem is enough here.
                if part.endswith("es") and len(part) > 5:
                    out.add(part[:-2])
                elif part.endswith("s") and len(part) > 4:
                    out.add(part[:-1])
    return out


def _score(qualified: str, block: str, wanted: set[str]) -> float:
    """How well one table answers the question. The table's own name counts for far more than a
    field name, because a question is nearly always about a thing, not about a column."""
    if not wanted:
        return 0.0
    name = qualified.split(".", 1)[-1]
    name_terms = _terms(name)
    score = 4.0 * len(name_terms & wanted)
    # An exact name, as someone would type it: "Action Item", "SOXRisk".
    if name_terms and name_terms <= wanted:
        score += 6.0
    field_terms = _terms(block[len(name):])
    score += min(3.0, 0.5 * len(field_terms & wanted))
    return score


def _fit(blocks: dict[str, str], question: str, budget: int) -> tuple[list[str], list[str]]:
    """Splits the tables into the ones described in full and the ones only named.

    Everything fits for most databases and this does nothing. It matters for a connection sharing
    a hundred-odd OpenPages object types, where describing them all comes to tens of thousands of
    tokens: the model's context would silently drop whatever didn't fit, keeping the tail, and the
    model would then insist that perfectly real object types don't exist. Choosing what to send
    beats letting the context window choose by truncation.
    """
    order = list(blocks)
    total = sum(len(blocks[t]) + 2 for t in order)
    if total <= budget:
        return order, []
    wanted = _terms(question)
    # Best match first, and by the connection's own order among equals so it stays predictable.
    ranked = sorted(order, key=lambda t: (-_score(t, blocks[t], wanted), order.index(t)))
    kept, used = [], 0
    for table in ranked:
        cost = len(blocks[table]) + 2
        if used + cost > budget and kept:
            continue
        kept.append(table)
        used += cost
    keeping = set(kept)
    return [t for t in order if t in keeping], [t for t in order if t not in keeping]


def describe(source: DataSource, question: str = "") -> str:
    """The tables, as the model is shown them: columns with types, and the values of
    low-cardinality text columns (such as region or status) so the model can filter on them.

    `question` is what is being asked. When a source shares more tables than fit the model's
    context, it decides which ones are described in full; the rest are listed by name so the model
    knows they exist and can say it needs one.
    """
    blocks = _schema_blocks(source)
    if not blocks:
        return "(no object types available)" if source.is_openpages else "(no tables available)"
    budget = int(settings.ai_schema_budget_tokens * CHARS_PER_TOKEN)
    kept, left_out = _fit(blocks, question, budget)
    text = "\n\n".join(blocks[t] for t in kept)
    if left_out:
        names = ", ".join(t.split(".", 1)[-1] for t in left_out)
        text += (f"\n\nAlso available, but not described above because there are too many to list "
                 f"({len(left_out)}): {names}.\nIf the question needs one of these, say so in reply "
                 f"rather than guessing its field names.")
    return _openpages_preamble(source, text) if source.is_openpages else text


def _openpages_preamble(source: DataSource, text: str) -> str:
    model = openpages_model.get(source.options.get("data_model"))
    if model is not None:
        text += "\n" + openpages_model.model_note(model)
    audit_id, audit_name = source.options.get("audit_id", ""), source.options.get("audit_name", "")
    if audit_id or audit_name:
        which = " and ".join(x for x in (f"Resource ID {audit_id}" if audit_id else "",
                                          f"name '{audit_name}'" if audit_name else "") if x)
        text += (f"\n\nDefault audit: the business entity with {which}. When a question is about \"the audit\" "
                 "or doesn't name one, limit results to it, e.g. JOIN [SOXBusEntity] ON CHILD([Finding]) WHERE "
                 + (f"[SOXBusEntity].[Resource ID] = {audit_id}" if audit_id else
                    f"[SOXBusEntity].[Name] = {openpages.quote(audit_name)}") + ".")
    return openpages.SQL_GUIDE + "\n\nObject types and their fields:\n\n" + text


def _is_text(sql_type) -> bool:
    try:
        return sql_type.python_type is str
    except NotImplementedError:
        return False


def _reflect(engine: Engine, name: str, schema: str) -> Table | None:
    try:
        return Table(name, MetaData(), schema=schema or None, autoload_with=engine)
    except Exception:
        return None


def _few_values(engine: Engine, table: Table, column: str, limit: int = 12) -> list[str] | None:
    """Up to `limit` distinct values, only when the column has at most that many."""
    col = table.c[column]
    try:
        with engine.connect() as conn:
            values = conn.execute(select(distinct(col)).where(col.is_not(None)).limit(limit + 1)).scalars().all()
            conn.rollback()
    except Exception:
        return None
    if len(values) > limit:
        return None
    return [str(v)[:40] for v in values]


# ---------- Running a query ----------

_results: OrderedDict[tuple, tuple[float, dict]] = OrderedDict()
_results_lock = threading.Lock()

# Placeholders for bound values, as dashboard_filters writes them (sqlglot renders them as :name, or
# %(name)s for PostgreSQL).
_PLACEHOLDER = re.compile(r"%\((bi_p\d+)\)s|:(bi_p\d+)\b")


def run_sql(source: DataSource, sql: str, params: dict | None = None, *, refresh: bool = False) -> dict:
    """Checks and runs one query. Raises sql_guard.UnsafeSQL or QueryFailed.

    params: values for the :bi_pN placeholders in sql (dashboard filters). They're sent to the database
    as bound parameters, never written into the SQL. A result is reused for RESULT_CACHE_SECONDS
    unless refresh is set; the key includes the connection's version, so editing a connection
    starts fresh."""
    safe = check_query(source, sql)
    params = params or {}
    key = (source.id, source.version, safe, tuple(sorted((k, str(v)) for k, v in params.items())))
    if not refresh:
        with _results_lock:
            hit = _results.get(key)
            if hit and time.time() - hit[0] < RESULT_CACHE_SECONDS:
                _results.move_to_end(key)
                return {**hit[1], "cached": True}
    t0 = time.perf_counter()
    if source.is_openpages:
        try:
            columns, rows, truncated = source.client.query(safe, MAX_ROWS)  # filters are already in the SQL
        except openpages.OpenPagesError as err:
            raise QueryFailed(str(err)) from err
    else:
        statement, bound = _bind(safe, params, source.engine.dialect.paramstyle)
        with source.engine.connect() as conn:
            try:
                _start_read_only(conn, source.db_type)
                result = conn.exec_driver_sql(statement, bound) if bound is not None else conn.exec_driver_sql(statement)
                columns = list(result.keys())
                rows = result.fetchmany(MAX_ROWS + 1)
            except Exception as err:
                raise QueryFailed(friendly_error(err)) from err
            finally:
                _finish(conn, source.db_type)
        truncated = len(rows) > MAX_ROWS
    rows = [[_json_value(v) for v in row] for row in rows[:MAX_ROWS]]
    data = {"sql": safe, "columns": columns, "rows": rows, "row_count": len(rows), "truncated": truncated,
            "elapsed_ms": round((time.perf_counter() - t0) * 1000),
            "ran_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")}
    with _results_lock:
        _results[key] = (time.time(), data)
        _results.move_to_end(key)
        while len(_results) > RESULT_CACHE_SIZE:
            _results.popitem(last=False)
    return {**data, "cached": False}


def check_query(source: DataSource, sql: str) -> str:
    """The SQL to run, or raises sql_guard.UnsafeSQL. OpenPages SQL has its own rules."""
    if source.is_openpages:
        try:
            return openpages.check_sql(sql, source.allowed)
        except openpages.UnsafeOpenPagesSQL as err:
            raise UnsafeSQL(str(err))
    return check_sql(sql, source.db_type, source.allowed, MAX_ROWS)


def clear_result_cache():
    with _results_lock:
        _results.clear()


def _bind(sql: str, params: dict, paramstyle: str):
    """Rewrites the placeholders for the driver's parameter style. Returns (sql, parameters), with
    parameters None when there are none, so a % in the SQL isn't read as a placeholder."""
    if not params:
        return sql, None
    parts = _PLACEHOLDER.split(sql)  # text, name, name, text, name, name, text...
    out, positional = [], []
    for i in range(0, len(parts), 3):
        text = parts[i]
        out.append(text.replace("%", "%%") if paramstyle in ("format", "pyformat") else text)
        if i + 1 < len(parts):
            name = parts[i + 1] or parts[i + 2]
            if name not in params:
                raise QueryFailed(f"No value was given for {name}.")
            positional.append(params[name])
            out.append({"qmark": "?", "format": "%s", "pyformat": f"%({name})s", "named": f":{name}",
                        "numeric": f":{len(positional)}"}[paramstyle])
    statement = "".join(out)
    if paramstyle in ("pyformat", "named"):
        return statement, dict(params)
    return statement, tuple(positional)


def table_columns(source: DataSource, qualified: str) -> list[tuple[str, str]]:
    """(name, type) for each column of one allowed table, or [] when it can't be read."""
    if source.is_openpages:
        try:
            return [(f["name"], f["type"]) for f in source.client.type_fields(source.op_type(qualified))]
        except openpages.OpenPagesError:
            return []
    schema, _, name = qualified.rpartition(".")
    try:
        return [(c["name"], str(c["type"])) for c in inspect(source.engine).get_columns(name, schema=schema or None)]
    except Exception:
        return []


def column_values(source: DataSource, qualified: str, column: str, limit: int = 200) -> list[str]:
    """Distinct values of one column, sorted, for a filter's list. At most `limit`."""
    if source.is_openpages:
        return _openpages_values(source, source.op_type(qualified), column, limit)
    schema, _, name = qualified.rpartition(".")
    table = _reflect(source.engine, name, schema)
    if table is None or column not in table.c:
        return []
    col = table.c[column]
    try:
        with source.engine.connect() as conn:
            _start_read_only(conn, source.db_type)
            try:
                values = conn.execute(select(distinct(col)).where(col.is_not(None)).order_by(col).limit(limit)).scalars().all()
            finally:
                _finish(conn, source.db_type)
    except Exception:
        return []
    return [str(v)[:100] for v in values]


def openpages_labels(source: DataSource, type_name: str, field: str) -> dict[str, str]:
    """{label people read: value OpenPages stores} for one enum field, empty when it stores the
    words already. Results come back labelled (see openpages.query), so a filter has to offer the
    same labels and turn the chosen one back into the stored value before it reaches the SQL."""
    if not source.is_openpages:
        return {}
    try:
        by_field = source.client.enum_labels(type_name)
    except openpages.OpenPagesError:
        return {}
    pairs = next((v for k, v in by_field.items() if k.lower() == field.lower()), {})
    return {label: stored for stored, label in pairs.items()}


def openpages_stored(source: DataSource, type_name: str, field: str, value: str) -> str:
    """The value to write into the SQL for what someone picked in a filter."""
    return openpages_labels(source, type_name, field).get(value, value)


def _openpages_values(source: DataSource, type_name: str, field: str, limit: int) -> list[str]:
    """A field's choices from its definition, or else the values in the data."""
    try:
        f = next((x for x in source.client.type_fields(type_name) if x["name"].lower() == field.lower()), None)
        if f and f["values"]:
            labels = openpages_labels(source, type_name, field)
            stored_to_label = {stored: label for label, stored in labels.items()}
            return sorted({stored_to_label.get(v, v) for v in f["values"]})[:limit]
        ref = openpages.field_ref(type_name, field)
        _, rows, _ = source.client.query(f"SELECT {ref} FROM [{type_name}]", MAX_ROWS)
    except openpages.OpenPagesError:
        return []
    return sorted({str(r[0])[:100] for r in rows if r and r[0] not in (None, "")})[:limit]


class QueryFailed(Exception):
    """The database refused or failed the query. The message is the database's error, shortened."""


def _start_read_only(conn, db_type: str):
    if db_type == "postgresql":
        conn.exec_driver_sql("SET TRANSACTION READ ONLY")
        conn.exec_driver_sql(f"SET LOCAL statement_timeout = {TIMEOUT_SECONDS * 1000}")
    elif db_type == "mysql":
        conn.exec_driver_sql(f"SET SESSION MAX_EXECUTION_TIME = {TIMEOUT_SECONDS * 1000}")
        conn.exec_driver_sql("SET SESSION TRANSACTION READ ONLY")
    elif db_type == "mssql":
        conn.connection.dbapi_connection.timeout = TIMEOUT_SECONDS  # pyodbc query timeout
    elif db_type == "sqlite":
        conn.exec_driver_sql("PRAGMA query_only = ON")


def _finish(conn, db_type: str):
    try:
        conn.rollback()
        if db_type == "sqlite":
            conn.exec_driver_sql("PRAGMA query_only = OFF")  # pooled connections are reused
            conn.commit()
    except Exception:
        conn.invalidate()  # don't return a connection in an unknown state to the pool


def _json_value(v):
    if v is None or isinstance(v, (bool, int, float, str)):
        return v
    if isinstance(v, Decimal):
        return float(v)
    if isinstance(v, dt.datetime) and v.time() == dt.time(0):
        return v.date().isoformat()  # DATE_TRUNC and similar return midnight timestamps; show the date
    if isinstance(v, (dt.date, dt.datetime, dt.time)):
        return v.isoformat()
    if isinstance(v, (bytes, bytearray, memoryview)):
        return "(binary)"
    return str(v)
