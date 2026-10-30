"""
Builds SQL from a chart people drag together, instead of writing it by hand.

The visual builder never sends SQL. It sends a spec saying which table to read, which columns go
on the axis, which numbers to aggregate, and how to filter them:

    {"table": "public.sales",
     "dimensions": [{"column": "region"}, {"column": "sale_date", "bucket": "month"}],
     "measures": [{"column": "amount", "agg": "sum", "alias": "Revenue"}],
     "filters": [{"column": "status", "op": "in", "values": ["open"]}],
     "order": [{"ref": "Revenue", "dir": "desc"}],
     "limit": 500}

compile_spec turns that into one SELECT ... GROUP BY for the connection's dialect, with every
value the person typed sent as a bound parameter (:bi_pN), never written into the SQL. The result
goes through datasources.run_sql, which checks it with sql_guard and runs it read-only, exactly
like SQL an AI model wrote.

Nothing here trusts the request: the table must be one a manager shared, and every column must be
a real column of that table. A name that isn't on those lists is refused rather than quoted into
the query, so the spec can't reach a table or column the person isn't allowed to read.

Dates are grouped into sortable text labels ("2024-03", "2024-Q1", "2024-W05") so every database
produces the same labels and charts sort them correctly without extra work in the browser.
"""

import datetime as dt

import sqlglot
from sqlglot import exp
from sqlglot.errors import SqlglotError

from .datasources import DataSource, table_columns
from .sql_guard import DIALECTS

MAX_DIMENSIONS = 4
MAX_MEASURES = 8
MAX_FILTERS = 20
MAX_IN_VALUES = 500
DEFAULT_LIMIT = 500
MAX_LIMIT = 5000

# Aggregate -> how it reads in a generated column name.
AGGS = {
    "sum": "Sum", "avg": "Average", "min": "Minimum", "max": "Maximum",
    "count": "Count", "count_distinct": "Distinct count",
}

BUCKETS = ("year", "quarter", "month", "week", "day")

# Operators, and how many values each one needs.
_OPS_VALUES = {"=": 1, "!=": 1, ">": 1, ">=": 1, "<": 1, "<=": 1,
               "contains": 1, "starts_with": 1, "ends_with": 1,
               "between": 2, "in": -1, "not_in": -1, "is_null": 0, "is_not_null": 0}
OPS = tuple(_OPS_VALUES)

# Date grouping, per dialect. {col} is the quoted column. Each one returns a sortable text label.
_BUCKET_SQL = {
    "postgres": {
        "year": "TO_CHAR({col}, 'YYYY')",
        "quarter": "TO_CHAR({col}, 'YYYY-\"Q\"Q')",
        "month": "TO_CHAR({col}, 'YYYY-MM')",
        "week": "TO_CHAR({col}, 'IYYY-\"W\"IW')",
        "day": "TO_CHAR({col}, 'YYYY-MM-DD')",
    },
    "mysql": {
        "year": "DATE_FORMAT({col}, '%Y')",
        "quarter": "CONCAT(YEAR({col}), '-Q', QUARTER({col}))",
        "month": "DATE_FORMAT({col}, '%Y-%m')",
        "week": "DATE_FORMAT({col}, '%x-W%v')",
        "day": "DATE_FORMAT({col}, '%Y-%m-%d')",
    },
    "tsql": {
        "year": "FORMAT({col}, 'yyyy')",
        "quarter": "CONCAT(YEAR({col}), '-Q', DATEPART(QUARTER, {col}))",
        "month": "FORMAT({col}, 'yyyy-MM')",
        "week": "CONCAT(YEAR({col}), '-W', FORMAT(DATEPART(ISO_WEEK, {col}), '00'))",
        "day": "FORMAT({col}, 'yyyy-MM-dd')",
    },
    "sqlite": {
        "year": "STRFTIME('%Y', {col})",
        "quarter": "STRFTIME('%Y', {col}) || '-Q' || ((CAST(STRFTIME('%m', {col}) AS INTEGER) + 2) / 3)",
        "month": "STRFTIME('%Y-%m', {col})",
        "week": "STRFTIME('%Y-W%W', {col})",
        "day": "STRFTIME('%Y-%m-%d', {col})",
    },
}

# Column types that a date bucket makes sense on.
_DATE_TYPES = ("date", "time", "year")
# Column types that can be summed or averaged.
_NUMBER_TYPES = ("int", "numeric", "decimal", "float", "double", "real", "money", "number", "bigint", "smallint")


class SpecError(Exception):
    """The chart can't be built. The message says what to change, and is safe to show."""


def _dialect(source: DataSource) -> str:
    if source.is_openpages:
        raise SpecError("The visual builder doesn't support IBM OpenPages connections yet. "
                        "Build this chart by asking a question instead.")
    try:
        return DIALECTS[source.db_type]
    except KeyError:
        raise SpecError(f"The visual builder doesn't support {source.type_label} connections yet.") from None


def _resolve_table(source: DataSource, name: str) -> str:
    """The allowed "schema.table" a spec means, however the caller spelled it."""
    wanted = str(name or "").strip().lower()
    if not wanted:
        raise SpecError("Choose a table for this chart.")
    if wanted in source.allowed:
        return wanted
    bare = wanted.rpartition(".")[2]
    matches = [t for t in sorted(source.allowed) if t.rpartition(".")[2] == bare]
    if len(matches) == 1:
        return matches[0]
    if matches:
        raise SpecError(f'Several shared tables are called "{bare}". Give the schema too, as "schema.{bare}".')
    raise SpecError(f'"{name}" isn\'t one of the tables shared from {source.name}.')


class _Columns:
    """The real columns of one table, matched without caring about case."""

    def __init__(self, source: DataSource, table: str):
        self._types = {name.lower(): (name, str(ctype).lower()) for name, ctype in table_columns(source, table)}
        self.table = table
        if not self._types:
            raise SpecError(f"The columns of {table} can't be read right now. Check the connection.")

    def real(self, column: str) -> str:
        """The column's name as the database spells it. Raises when there is no such column."""
        found = self._types.get(str(column or "").strip().lower())
        if found is None:
            raise SpecError(f'{self.table} has no column called "{column}".')
        return found[0]

    def type_of(self, column: str) -> str:
        return self._types[column.strip().lower()][1]

    def is_date(self, column: str) -> bool:
        return any(t in self.type_of(column) for t in _DATE_TYPES)

    def is_number(self, column: str) -> bool:
        return any(t in self.type_of(column) for t in _NUMBER_TYPES)


def _unique(name: str, taken: set[str]) -> str:
    """A column name nothing else in this query uses, so two measures never collide."""
    base = name[:60] or "value"
    candidate, n = base, 2
    while candidate.lower() in taken:
        candidate, n = f"{base} {n}", n + 1
    taken.add(candidate.lower())
    return candidate


def _bucket_expression(column: str, bucket: str, dialect: str) -> exp.Expression:
    template = _BUCKET_SQL[dialect][bucket]
    quoted = exp.column(column, quoted=True).sql(dialect=dialect)
    # The column name is already checked against the table, so this only ever builds a known shape.
    return sqlglot.parse_one(template.format(col=quoted), read=dialect)


def _dimension(item: dict, columns: _Columns, dialect: str, taken: set[str]) -> tuple[exp.Expression, str]:
    """(expression, output name) for one axis or legend field."""
    column = columns.real(item.get("column", ""))
    bucket = str(item.get("bucket") or "").strip().lower()
    if bucket:
        if bucket not in BUCKETS:
            raise SpecError(f'"{bucket}" isn\'t a way to group dates. Use one of: {", ".join(BUCKETS)}.')
        if not columns.is_date(column):
            raise SpecError(f'"{column}" isn\'t a date column, so it can\'t be grouped by {bucket}.')
        body = _bucket_expression(column, bucket, dialect)
        default = f"{column} ({bucket})"
    else:
        body = exp.column(column, quoted=True)
        default = column
    alias = _unique(str(item.get("alias") or "").strip() or default, taken)
    return body, alias


def _measure(item: dict, columns: _Columns, taken: set[str]) -> tuple[exp.Expression, str]:
    """(expression, output name) for one number field."""
    agg = str(item.get("agg") or "sum").strip().lower()
    if agg not in AGGS:
        raise SpecError(f'"{agg}" isn\'t a way to summarise numbers. Use one of: {", ".join(AGGS)}.')
    raw = str(item.get("column") or "").strip()

    # Count with no column counts rows.
    if agg == "count" and not raw:
        body: exp.Expression = exp.Count(this=exp.Star())
        default = "Count"
    else:
        column = columns.real(raw)
        if agg in ("sum", "avg") and not columns.is_number(column):
            raise SpecError(f'"{column}" holds {columns.type_of(column)}, which can\'t be added up. '
                            f"Count it instead, or pick a number column.")
        col = exp.column(column, quoted=True)
        if agg == "count_distinct":
            body = exp.Count(this=exp.Distinct(expressions=[col]))
        elif agg == "count":
            body = exp.Count(this=col)
        else:
            body = {"sum": exp.Sum, "avg": exp.Avg, "min": exp.Min, "max": exp.Max}[agg](this=col)
        default = f"{AGGS[agg]} of {column}"
    alias = _unique(str(item.get("alias") or "").strip() or default, taken)
    return body, alias


class _Binder:
    """Collects the values a filter compares against.

    Normally they travel as parameters, so nothing a person typed is ever part of the SQL. A saved
    chart is the exception: its SQL is stored on its own and run later by the dashboard, which has
    no way to carry parameters with it, so `inline` writes the values into the query as literals
    instead. sqlglot escapes them, and sql_guard checks the result before it runs."""

    def __init__(self, inline: bool = False) -> None:
        self.params: dict = {}
        self.inline = inline

    def bind(self, value) -> exp.Expression:
        if self.inline:
            if isinstance(value, bool):
                return exp.convert(value)
            if isinstance(value, (int, float)):
                return exp.Literal.number(value)
            # Dates are written as text: every dialect compares a date column to 'YYYY-MM-DD'.
            return exp.Literal.string(value.isoformat() if isinstance(value, dt.date) else str(value))
        name = f"bi_p{len(self.params)}"
        self.params[name] = value
        return exp.Placeholder(this=name)


def _filter_value(raw, column: str, columns: _Columns, source: DataSource):
    """One comparison value, as the database wants it."""
    if columns.is_date(column):
        try:
            parsed = raw if isinstance(raw, dt.date) else dt.date.fromisoformat(str(raw)[:10])
        except ValueError:
            raise SpecError(f'"{raw}" isn\'t a date. Write dates as YYYY-MM-DD.') from None
        # SQLite keeps dates as text, so compare with text; the others get real dates.
        return parsed.isoformat() if source.db_type == "sqlite" else parsed
    if columns.is_number(column):
        try:
            return float(raw) if "." in str(raw) else int(raw)
        except (TypeError, ValueError):
            raise SpecError(f'"{raw}" isn\'t a number, but "{column}" holds numbers.') from None
    return str(raw)


def _condition(item: dict, columns: _Columns, source: DataSource, binder: _Binder) -> exp.Expression:
    column = columns.real(item.get("column", ""))
    op = str(item.get("op") or "=").strip().lower()
    if op not in _OPS_VALUES:
        raise SpecError(f'"{op}" isn\'t a way to filter. Use one of: {", ".join(OPS)}.')
    col = exp.column(column, quoted=True)

    raw_values = item.get("values")
    values = list(raw_values) if isinstance(raw_values, (list, tuple)) else ([] if raw_values is None else [raw_values])
    needed = _OPS_VALUES[op]
    if needed >= 0 and len(values) != needed:
        word = "no value" if needed == 0 else "one value" if needed == 1 else f"{needed} values"
        raise SpecError(f'The "{op}" filter on "{column}" needs {word}.')
    if needed < 0 and not values:
        raise SpecError(f'The "{op}" filter on "{column}" needs at least one value.')
    if len(values) > MAX_IN_VALUES:
        raise SpecError(f'The filter on "{column}" has {len(values)} values; at most {MAX_IN_VALUES} are allowed.')

    if op == "is_null":
        return col.is_(exp.Null())
    if op == "is_not_null":
        return exp.Not(this=col.is_(exp.Null()))
    if op in ("contains", "starts_with", "ends_with"):
        text = str(values[0]).replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        pattern = {"contains": f"%{text}%", "starts_with": f"{text}%", "ends_with": f"%{text}"}[op]
        return exp.Like(this=col, expression=binder.bind(pattern))

    bind = lambda v: binder.bind(_filter_value(v, column, columns, source))  # noqa: E731
    if op == "in":
        return col.isin(*[bind(v) for v in values])
    if op == "not_in":
        return exp.Not(this=col.isin(*[bind(v) for v in values]))
    if op == "between":
        return exp.Between(this=col, low=bind(values[0]), high=bind(values[1]))
    builder = {"=": col.eq, "!=": col.neq, ">": col.__gt__, ">=": col.__ge__, "<": col.__lt__, "<=": col.__le__}[op]
    return builder(bind(values[0]))


def _limit(spec: dict) -> int:
    raw = spec.get("limit", DEFAULT_LIMIT)
    if raw in (None, ""):
        return DEFAULT_LIMIT
    try:
        value = int(raw)
    except (TypeError, ValueError):
        raise SpecError("The row limit must be a whole number.") from None
    if value < 1:
        raise SpecError("The row limit must be at least 1.")
    return min(value, MAX_LIMIT)


def _order(spec: dict, outputs: dict[str, exp.Expression], grouped: bool) -> list[exp.Ordered]:
    """ORDER BY entries. Each one names a column the chart already shows."""
    items = spec.get("order") or []
    if not isinstance(items, list):
        raise SpecError("The sort order must be a list.")
    out = []
    by_name = {name.lower(): name for name in outputs}
    for item in items:
        if not isinstance(item, dict):
            raise SpecError("Each sort entry needs a column to sort by.")
        ref = str(item.get("ref") or item.get("column") or "").strip().lower()
        name = by_name.get(ref)
        if name is None:
            raise SpecError(f'Can\'t sort by "{item.get("ref") or item.get("column")}": '
                            f"the chart doesn't show it. Sort by one of: {', '.join(outputs)}.")
        descending = str(item.get("dir") or "asc").strip().lower() in ("desc", "descending")
        # Grouped queries repeat the expression, because not every database can sort by output name.
        body = outputs[name].copy() if grouped else exp.column(name, quoted=True)
        out.append(exp.Ordered(this=body, desc=descending))
    return out


def compile_spec(source: DataSource, spec: dict, *, inline: bool = False) -> tuple[str, dict]:
    """(sql, parameters) for one visual-builder chart.

    inline writes the filter values into the SQL instead of returning them as parameters, for a
    chart that is being saved and will later be run on its own by the dashboard.

    Raises SpecError when the spec names a table or column the person can't read, or asks for
    something the data doesn't support. The SQL still goes through sql_guard when it runs."""
    if not isinstance(spec, dict):
        raise SpecError("The chart is missing.")
    dialect = _dialect(source)
    table = _resolve_table(source, spec.get("table", ""))
    columns = _Columns(source, table)

    dimension_items = spec.get("dimensions") or []
    measure_items = spec.get("measures") or []
    filter_items = spec.get("filters") or []
    for name, items, cap in (("fields", dimension_items, MAX_DIMENSIONS), ("numbers", measure_items, MAX_MEASURES),
                             ("filters", filter_items, MAX_FILTERS)):
        if not isinstance(items, list):
            raise SpecError(f"The chart's {name} must be a list.")
        if len(items) > cap:
            raise SpecError(f"A chart can use at most {cap} {name}; this one has {len(items)}.")
    if not dimension_items and not measure_items:
        raise SpecError("Drag at least one field onto the chart.")
    for items, what in ((dimension_items, "field"), (measure_items, "number"), (filter_items, "filter")):
        for item in items:
            if not isinstance(item, dict):
                raise SpecError(f"Each {what} must say which column it uses.")

    taken: set[str] = set()
    outputs: dict[str, exp.Expression] = {}
    selects, groups = [], []
    for item in dimension_items:
        body, alias = _dimension(item, columns, dialect, taken)
        selects.append(exp.alias_(body.copy(), alias, quoted=True))
        groups.append(body)
        outputs[alias] = body
    for item in measure_items:
        body, alias = _measure(item, columns, taken)
        selects.append(exp.alias_(body.copy(), alias, quoted=True))
        outputs[alias] = body

    binder = _Binder(inline=inline)
    conditions = [_condition(item, columns, source, binder) for item in filter_items]

    schema, _, name = table.rpartition(".")
    query = exp.select(*selects).from_(exp.table_(name, db=schema or None, quoted=True))
    if conditions:
        query = query.where(exp.and_(*conditions))
    # Measures without fields are one total row, so there is nothing to group by.
    if groups and measure_items:
        query = query.group_by(*[g.copy() for g in groups])
    elif groups and not measure_items:
        query = query.distinct()
    ordering = _order(spec, outputs, grouped=bool(groups and measure_items))
    if ordering:
        query = query.order_by(*ordering)
    query = query.limit(_limit(spec))

    try:
        sql = query.sql(dialect=dialect, pretty=True)
    except SqlglotError as err:
        raise SpecError(f"The chart can't be turned into a query: {err}") from err
    return sql, binder.params


def describe_table(source: DataSource, table: str) -> dict:
    """The fields pane for one table: each column, and whether it can go on an axis or be summed."""
    resolved = _resolve_table(source, table)
    columns = _Columns(source, resolved)
    fields = []
    for name, ctype in table_columns(source, resolved):
        fields.append({"name": name, "type": ctype,
                       "role": "measure" if columns.is_number(name) else "dimension",
                       "is_date": columns.is_date(name),
                       "is_number": columns.is_number(name)})
    return {"table": resolved, "fields": fields}
