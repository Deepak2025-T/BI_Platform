"""SQL safety + correctness checks: single read-only statement, row cap, then EXPLAIN dry-run on the target DB."""
from __future__ import annotations

import sqlglot
from sqlglot import exp

from ..connectors import DIALECTS, explain
from ..db import DbConnection

FORBIDDEN = tuple(getattr(exp, n) for n in ("Insert", "Update", "Delete", "Drop", "Create", "Alter", "Command",
                                             "Merge", "TruncateTable", "Grant", "Into") if hasattr(exp, n))


class SQLValidationError(Exception):
    pass


def clean_sql(sql: str) -> str:
    sql = sql.strip().strip("`")
    if sql.lower().startswith("sql\n"):
        sql = sql[4:]
    return sql.rstrip().rstrip(";").strip()


def check_static(sql: str, dialect_key: str, max_rows: int) -> str:
    """Parse, enforce SELECT-only and a row cap. Returns the normalised SQL to run."""
    dialect = DIALECTS[dialect_key].sqlglot
    sql = clean_sql(sql)
    try:
        statements = [s for s in sqlglot.parse(sql, read=dialect) if s is not None]
    except sqlglot.errors.ParseError as e:
        raise SQLValidationError(f"SQL parse error: {str(e).splitlines()[0]}") from e
    if len(statements) != 1:
        raise SQLValidationError("Exactly one SQL statement is allowed.")
    tree = statements[0]
    if not isinstance(tree, exp.Query):
        raise SQLValidationError(f"Only SELECT queries are allowed (got {tree.key.upper()}).")
    for node in tree.walk():
        if isinstance(node, FORBIDDEN):
            raise SQLValidationError(f"Forbidden operation in query: {node.key.upper()}.")
    # cap rows: add LIMIT if missing, or lower an existing one that exceeds the cap
    limit = tree.args.get("limit")
    if limit is None:
        tree = tree.limit(max_rows)
    else:
        try:
            n = int(limit.expression.name)
            if n > max_rows:
                tree = tree.limit(max_rows)
        except (AttributeError, ValueError):
            pass
    return tree.sql(dialect=dialect)


def validate(conn: DbConnection, sql: str, max_rows: int) -> str:
    safe = check_static(sql, conn.dialect, max_rows)
    try:
        explain(conn, safe)
    except Exception as e:  # noqa: BLE001
        msg = str(getattr(e, "orig", e)).strip().splitlines()
        raise SQLValidationError("Database rejected the query: " + " ".join(msg[:3])) from e
    return safe
