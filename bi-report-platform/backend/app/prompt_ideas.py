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

MAX_IDEAS = 12
# Looking at more than this would mean reading the columns of every table on a big connection.
MAX_TABLES = 10
# How many questions each table may contribute before any is left out.
MAX_RANKS = 4

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
    # A second column to group by, so the table can suggest a comparison and not only a list.
    second_group = _pick([c for c in columns if c[0] != group],
                         ("char", "text", "string", "enum"), _GROUP_WORDS, avoid=_FREE_TEXT)

    ideas = []
    if number and group:
        ideas.append(f"Total {_label(number)} by {_label(group)} in {thing}")
    if number and date:
        ideas.append(f"Monthly {_label(number)} in {thing} over the last year")
    if number and group:
        ideas.append(f"Top 10 {_label(group)} by {_label(number)} in {thing}")
    # Counting by a free-text column would draw one bar per row, so that one is left out.
    if group and not _FREE_TEXT.search(group):
        ideas.append(f"How many {thing} there are by {_label(group)}")
    if date:
        ideas.append(f"How many {thing} were added each month")
    # Two groupings at once is the question a single bar chart can't answer, and the one people
    # reach for second: it is what turns a list into a comparison.
    if second_group and group and second_group != group:
        ideas.append(f"{thing.capitalize()} by {_label(group)} and {_label(second_group)}")
    if number and group:
        ideas.append(f"Average {_label(number)} per {_label(group)} in {thing}")
    if number and date and group:
        ideas.append(f"{_label(number).capitalize()} by {_label(group)}, this year against last")
    return ideas


def ideas_for(source: DataSource) -> list[str]:
    """A handful of questions to try against this connection, or [] when nothing fits.

    Tables are taken in the order a manager shared them, and each one contributes its best
    question before any table contributes its second, so a connection of many tables suggests
    breadth rather than six questions about the first one."""
    if source.is_openpages:
        return _openpages_ideas(source)
    per_table = []
    for table in list(source.tables)[:MAX_TABLES]:
        columns = table_columns(source, table)
        if columns:
            per_table.append(_for_table(table, columns))

    out: list[str] = []
    for rank in range(MAX_RANKS):             # best question of every table, then each second, ...
        for ideas in per_table:
            if rank < len(ideas) and len(out) < MAX_IDEAS:
                out.append(ideas[rank])
    return out


# Questions worth asking of each OpenPages object type, best first. OpenPages field names look
# like "OPSS-Ctl:Design Effectiveness", so a question written from the columns would read as
# gibberish; these are written in the words the people who use OpenPages actually use.
_OP_IDEAS: dict[str, list[str]] = {
    "soxrisk": ["Risks by residual rating", "Inherent against residual rating",
                "Risks by domain and treatment", "How many risks are accepted without treatment"],
    "soxcontrol": ["Controls by design and operating effectiveness", "How many controls are ineffective",
                   "Controls by type and method", "Controls by business entity"],
    "soxissue": ["Open issues by priority", "Issues by status and root cause", "Overdue issues by owner",
                 "How many issues were raised each month"],
    "soxprocess": ["Processes by category", "Processes in scope for SOX", "Processes by business entity"],
    "soxbusentity": ["Business entities by type", "Entities in RCSA scope", "Entities by region"],
    "lossevent": ["Loss events by risk category", "Loss amount by business entity",
                  "Loss events by outcome and severity", "Monthly loss amount over the last year"],
    "actionitem": ["Action items by status", "Overdue action items by owner",
                   "Action items falling due by month", "How complete are the open action items"],
    "kriindicator": ["Indicators breaching their threshold", "Indicator values against target by month"],
    "policy": ["Policies by approval status", "Policies due for review this quarter", "Policies by department"],
    "sauditaction": ["Audit actions by status", "Overdue audit actions by owner"],
    "auditplan": ["Audits by status and year", "Audit coverage by business entity"],
    "vendor": ["Vendors by risk tier", "Vendors by status and country", "How many vendors are due for review"],
}

# Asked of any OpenPages connection, whatever it shares: they read across object types, which is
# where the interesting questions in a GRC model tend to live.
_OP_GENERAL = [
    "Which business entities carry the most high residual risk",
    "Which risks have no effective control on them",
    "Open issues and the action items closing them",
]


def _openpages_ideas(source: DataSource) -> list[str]:
    """Questions for an OpenPages connection, from the object types it shares.

    A connection that shares only risks is never asked about vendors, and one that shares a type
    this list has never heard of simply contributes nothing rather than a question built out of
    its field names."""
    shared = [t.split(".", 1)[-1].lower() for t in source.tables]
    per_type = [_OP_IDEAS[name] for name in shared if name in _OP_IDEAS]

    out: list[str] = []
    for rank in range(MAX_RANKS):            # best question of every type, then each second, ...
        for ideas in per_type:
            if rank < len(ideas) and len(out) < MAX_IDEAS:
                out.append(ideas[rank])
    for idea in _OP_GENERAL:
        if len(out) < MAX_IDEAS:
            out.append(idea)
    return out
