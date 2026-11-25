"""Asking the connection which fields actually hold something, before planning a report around them.

A loss report is mostly about money, and on this installation none of the money could be read. The
query ran, the column came back, and every cell in it was empty - for Gross Loss, Net Loss,
Recovery Amount on the event, and for Actual Loss and Actual Recovery Amount on the records
underneath. Three of those are read-only fields OpenPages calculates from their children, and all
of them are the Currency data type; what they have in common is that the Query Service returned
nothing for any of them while every ordinary field beside them came back filled.

Nothing in a field list says this. A field exists, has a type, and is empty, and the first anyone
knows is a report with eight charts missing and three number tiles that will not draw.

So the fields a report is built around are asked about first, with one small query each, and what
comes back goes into the prompt as a fact: these can be read, these cannot, and if none of them
can, build the report from counts and leave the money out rather than planning eight charts that
cannot exist. A report that says "no amounts are readable here" in one line is worth far more than
one that fails eight times and explains none of them.
"""

from __future__ import annotations

from dataclasses import dataclass

from .connections import openpages
from .datasources import DataSource, run_sql, table_columns

# Enough rows to tell an empty column from a sparse one, few enough to cost nothing.
SAMPLE = 200


@dataclass(frozen=True)
class Field:
    """One field to ask about: the object type that holds it and what it is called."""

    type_name: str
    label: str

    def __str__(self) -> str:
        return f"[{self.type_name}].[{self.label}]"


def real_column(source: DataSource, type_name: str, label: str) -> str | None:
    """The column of this type whose name is `label`, as the Query Service spells it.

    OpenPages files a field under its group - "Gross Loss" is reported as "OPSS-LossEv:Gross Loss"
    on some connections and as the bare name on others - so the group prefix is matched through.
    """
    wanted = label.strip().lower()
    for name, _ in table_columns(source, f"openpages.{type_name}"):
        if name.lower() == wanted or name.split(":", 1)[-1].strip().lower() == wanted:
            return name
    return None


def _holds_values(source: DataSource, type_name: str, column: str) -> bool:
    """Whether any of the first rows of this type has something in this column."""
    sql = f"SELECT {openpages.field_ref(type_name, column)} FROM [{type_name}]"
    try:
        result = run_sql(source, sql)
    except Exception:  # a field the service will not select, a connection that would not answer
        return False
    return any(row and row[0] not in (None, "") for row in result.get("rows", [])[:SAMPLE])


def readable(source: DataSource, fields: tuple[Field, ...]):
    """(the fields that hold values, the ones that do not). A field the type does not have at all
    counts as one that cannot be read, which is what it is as far as a chart is concerned."""
    # Only types this connection shares. Asking about one it does not is not a slower answer, it
    # is a different kind of failure - the field list of a type OpenPages will not describe - and
    # a report must not be lost to a question it did not have to ask.
    shared = {t.split(".", 1)[-1].lower() for t in source.tables}
    found, empty = [], []
    for field in fields:
        if field.type_name.lower() not in shared:
            empty.append(field)
            continue
        column = real_column(source, field.type_name, field.label)
        (found if column and _holds_values(source, field.type_name, column) else empty).append(field)
    return found, empty


def advice(source: DataSource, fields: tuple[Field, ...]) -> tuple[str, list[str]]:
    """(what to add to the prompt, the fields that cannot be read) - "" when there is nothing to
    say, which is what happens when a report names no fields to ask about."""
    if not fields:
        return "", []
    found, empty = readable(source, fields)
    if not empty:
        return "", []

    lines = ["FIELDS ON THIS CONNECTION",
             "These were read before you were asked, so they are facts about this installation "
             "rather than advice."]
    if found:
        lines.append("These amount fields hold figures and are the ones to use: "
                     + ", ".join(str(f) for f in found) + ".")
    lines.append("These came back empty for every record and must not be used - not in a chart, "
                 "not in a number tile, not as a column of a table: "
                 + ", ".join(str(f) for f in empty) + ".")
    if not found:
        lines.append("No amount on this connection can be read at all. Build this report from "
                     "counts alone: no totals, no money tiles, no amount columns, and nothing in "
                     "a title that promises a figure. Give the same number of charts by breaking "
                     "the records down by their other fields instead - category, status, entity, "
                     "business line, severity, outcome, cause, owner and month.")
    return "\n".join(lines), [str(f) for f in empty]
