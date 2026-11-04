"""
Checks SQL written by an AI model before it runs.

Allowed: exactly one read-only query (SELECT, WITH ... SELECT, UNION ...) that reads only the
tables a manager chose for the connection, with a row limit added. Everything else is refused:
writes and schema changes anywhere in the statement, SELECT INTO, row locks, table functions,
and functions that read files or reach other servers.

This is one layer. The others: connections use read-only accounts, and queries run in a
read-only transaction with a timeout where the database supports it (see datasources.run_sql).
"""

import sqlglot
from sqlglot import exp
from sqlglot.errors import ParseError, SqlglotError

# Database type -> sqlglot dialect.
DIALECTS = {"postgresql": "postgres", "mysql": "mysql", "mssql": "tsql", "sqlite": "sqlite"}

# Node types that change data or schema, wherever they appear in the statement.
_WRITE_NODES = tuple(getattr(exp, n) for n in (
    "Insert", "Update", "Delete", "Merge", "Create", "Drop", "Alter", "TruncateTable", "Command",
    "Copy", "Into", "Grant", "Revoke", "Use", "Set", "Pragma", "Transaction", "Commit", "Rollback",
) if hasattr(exp, n))

# Functions that read server files, sleep, change settings, or reach other servers.
DENIED_FUNCTIONS = {
    # PostgreSQL
    "pg_read_file", "pg_read_binary_file", "pg_ls_dir", "pg_stat_file", "lo_import", "lo_export",
    "lo_get", "dblink", "dblink_exec", "dblink_connect", "pg_sleep", "set_config", "pg_terminate_backend",
    "pg_cancel_backend", "pg_reload_conf", "current_setting", "query_to_xml", "pg_logical_emit_message",
    # MySQL
    "load_file", "sleep", "benchmark", "get_lock", "sys_exec", "sys_eval",
    # SQL Server
    "openrowset", "opendatasource", "openquery", "openxml", "xp_cmdshell", "xp_dirtree", "waitfor",
    # SQLite
    "load_extension", "readfile", "writefile", "edit", "fts3_tokenizer",
}


class UnsafeSQL(Exception):
    """The SQL can't run. The message explains why, for the person and for the model to fix it."""


def _function_name(f: exp.Func) -> str:
    return (f.name if isinstance(f, exp.Anonymous) else f.sql_name()).lower()


def check_sql(sql: str, db_type: str, allowed_tables: set[str], max_rows: int) -> str:
    """Returns the SQL to run (with a row limit), or raises UnsafeSQL.

    allowed_tables holds lower-case "schema.table" names. A table written without a schema is
    allowed when exactly that table name appears in the allowed list.
    """
    dialect = DIALECTS[db_type]
    text = (sql or "").strip().rstrip(";").strip()
    if not text:
        raise UnsafeSQL("No SQL was written.")
    try:
        statements = [s for s in sqlglot.parse(text, read=dialect) if s is not None]
    except (ParseError, SqlglotError) as err:
        raise UnsafeSQL(f"The SQL couldn't be read: {str(err).splitlines()[0][:200]}")
    if len(statements) != 1:
        raise UnsafeSQL("Only one statement can run at a time.")
    tree = statements[0]
    if not isinstance(tree, exp.Query):
        raise UnsafeSQL("Only SELECT queries can run.")
    if tree.find(*_WRITE_NODES):
        raise UnsafeSQL("The query tries to change data or the database. Only reading is allowed.")
    if any(s.args.get("locks") for s in tree.find_all(exp.Select)):
        raise UnsafeSQL("Row locks (FOR UPDATE) aren't allowed.")

    for f in tree.find_all(exp.Func):
        if _function_name(f) in DENIED_FUNCTIONS:
            raise UnsafeSQL(f"The function {_function_name(f)} isn't allowed.")

    cte_names = {c.alias_or_name.lower() for c in tree.find_all(exp.CTE)}
    bare_names = {t.split(".")[-1] for t in allowed_tables}
    for table in tree.find_all(exp.Table):
        name, schema = table.name.lower(), table.db.lower()
        if not name:
            raise UnsafeSQL("Table functions aren't allowed. Read from the listed tables only.")
        if table.catalog:
            raise UnsafeSQL(f"Write table names as schema.table, not with a database name ({table.sql(dialect=dialect)}).")
        if not schema and name in cte_names:
            continue
        if f"{schema}.{name}" in allowed_tables or (not schema and name in bare_names):
            continue
        raise UnsafeSQL(f"The table {table.sql(dialect=dialect)} isn't one of the tables you can query.")

    existing = tree.args.get("limit")
    limit_value = existing.expression if isinstance(existing, exp.Limit) else None
    keep = isinstance(limit_value, exp.Literal) and limit_value.is_int and int(limit_value.this) <= max_rows
    if not keep:
        tree = tree.limit(max_rows)
    return tree.sql(dialect=dialect)
