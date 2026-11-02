"""
Questions worth asking of one database, worked out from its own columns.

The Ask page shows these under the box, so a connection nobody has used before still suggests
something real to type. No AI model is involved: the shapes below come from what the shared
tables actually hold — a date column, a number worth adding up, something to group by — which
means they appear instantly and cost nothing.

They are only a starting point. Every one is a sentence the person can edit before sending, and
the model (or the builder) still decides how to answer it.
"""

import re

from .datasources import DataSource, table_columns

MAX_IDEAS = 6
# Looking at more than this would mean reading the columns of every table on a big connection.
MAX_TABLES = 6

_DATE_TYPES = ("date", "time", "year")
_NUMBER_TYPES = ("int", "numeric", "decimal", "float", "double", "real", "money", "bigint", "smallint")

# Columns worth adding up, best first. A column whose name says it holds money or a quantity beats
# one that happens to be a number, so "revenue" wins over "id".
_MEASURE_WORDS = ("revenue", "amount", "value", "total", "sales", "price", "cost", "spend", "profit",
                  "quantity", "qty", "hours", "score", "balance", "payable", "outstanding")
# Columns worth grouping by, best first.
_GROUP_WORDS = ("region", "country", "status", "category", "type", "product", "department", "team",
                "channel", "stage", "priority", "name", "agency", "industry", "segment")
# Never interesting on their own: keys and flags.
_SKIP = re.compile(r"(^|_)(id|uuid|guid|key|code|hash|token|password)$", re.I)
# Grouping by free text gives one bar per row, so these are a last resort rather than a choice.
_FREE_TEXT = re.compile(r"(name|description|title|subject|email|address|note|comment|remark)", re.I)


def _label(name: str) -> str:
    """A column or table name as a person would say it: "amount_payable" -> "amount payable"."""
    return name.replace("_", " ").strip().lower()


def _pick(columns: list[tuple[str, str]], types: tuple[str, ...], words: tuple[str, ...],
          avoid: re.Pattern | None = None) -> str:
    """The most promising column of a kind: one whose name says what it is, else the first."""
    fitting = [name for name, ctype in columns
               if any(t in str(ctype).lower() for t in types) and not _SKIP.search(name)]
    # Free text makes a poor grouping, so it is only used when the table holds nothing else.
    ranked = [n for n in fitting if not (avoid and avoid.search(n))] or fitting
    for word in words:
        for name in ranked:
            if word in name.lower():
                return name
    return ranked[0] if ranked else ""


def _for_table(table: str, columns: list[tuple[str, str]]) -> list[str]:
    """Questions this one table can answer, most useful first."""
    thing = _label(table.rpartition(".")[2])
    number = _pick(columns, _NUMBER_TYPES, _MEASURE_WORDS)
    group = _pick(columns, ("char", "text", "string", "enum"), _GROUP_WORDS, avoid=_FREE_TEXT)
    date = _pick(columns, _DATE_TYPES, ("date", "created", "posted", "order", "invoice"))

    ideas = []
    if number and group:
        ideas.append(f"Total {_label(number)} by {_label(group)} in {thing}")
    if number and date:
        ideas.append(f"Monthly {_label(number)} in {thing} over the last year")
    if number and group:
        ideas.append(f"Top 10 {_label(group)} by {_label(number)} in {thing}")
    # Counting by a free-text column would draw one bar per row, so that one is left out.
    if group and not number and not _FREE_TEXT.search(group):
        ideas.append(f"How many {thing} there are by {_label(group)}")
    if date and not number:
        ideas.append(f"How many {thing} were added each month")
    return ideas


def ideas_for(source: DataSource) -> list[str]:
    """A handful of questions to try against this connection, or [] when nothing fits.

    Tables are taken in the order a manager shared them, and each one contributes its best
    question before any table contributes its second, so a connection of many tables suggests
    breadth rather than six questions about the first one."""
    if source.is_openpages:
        # OpenPages fields are named "OPSS-Ctl:Design Effectiveness"; its own templates read better.
        return ["How many controls are ineffective?", "Open issues by priority",
                "Findings by business unit", "Loss events by risk category"]
    per_table = []
    for table in list(source.tables)[:MAX_TABLES]:
        columns = table_columns(source, table)
        if columns:
            per_table.append(_for_table(table, columns))

    out: list[str] = []
    for rank in range(3):                     # best question of every table, then each second, ...
        for ideas in per_table:
            if rank < len(ideas) and len(out) < MAX_IDEAS:
                out.append(ideas[rank])
    return out
