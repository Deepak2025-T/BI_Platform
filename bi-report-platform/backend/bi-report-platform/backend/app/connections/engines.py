"""Builds SQLAlchemy engines for saved connections and reads their table lists."""

import time
from dataclasses import dataclass, field

from sqlalchemy import Engine, create_engine, inspect, text
from sqlalchemy.engine import URL
from sqlalchemy.pool import NullPool

DB_TYPES = {
    "postgresql": {"label": "PostgreSQL", "driver": "postgresql+psycopg", "port": 5432},
    "mysql": {"label": "MySQL or MariaDB", "driver": "mysql+pymysql", "port": 3306},
    "mssql": {"label": "SQL Server", "driver": "mssql+pyodbc", "port": 1433},
    "sqlite": {"label": "SQLite", "driver": "sqlite", "port": None},
    "openpages": {"label": "IBM OpenPages", "driver": None, "port": None},  # REST API, see openpages.py
}

MSSQL_ODBC_DRIVER = "ODBC Driver 18 for SQL Server"
CONNECT_TIMEOUT = 5  # seconds

# Schemas that hold the database's own catalog, never business data.
SYSTEM_SCHEMAS = {"information_schema", "pg_catalog", "pg_toast", "sys", "guest", "mysql", "performance_schema"}


@dataclass
class ConnSpec:
    """Everything needed to connect, from a saved connection or from the unsaved form."""
    db_type: str
    database: str
    host: str = ""
    port: int | None = None
    username: str = ""
    password: str = ""
    options: dict = field(default_factory=dict)


def build_url(s: ConnSpec) -> URL:
    if s.db_type == "sqlite":
        return URL.create("sqlite", database=s.database)
    query: dict[str, str] = {}
    if s.db_type == "postgresql" and s.options.get("ssl"):
        query["sslmode"] = "require"
    if s.db_type == "mssql":
        query["driver"] = MSSQL_ODBC_DRIVER
        query["TrustServerCertificate"] = "yes" if s.options.get("trust_server_certificate") else "no"
    return URL.create(DB_TYPES[s.db_type]["driver"], username=s.username or None, password=s.password or None,
                      host=s.host or None, port=s.port or DB_TYPES[s.db_type]["port"], database=s.database,
                      query=query)


CONNECT_ARGS = {
    "postgresql": {"connect_timeout": CONNECT_TIMEOUT},
    "mysql": {"connect_timeout": CONNECT_TIMEOUT, "read_timeout": 30},
    "mssql": {"timeout": CONNECT_TIMEOUT},
    "sqlite": {},
}


def make_engine(s: ConnSpec, pooled: bool = True) -> Engine:
    kwargs: dict = {"connect_args": CONNECT_ARGS[s.db_type], "pool_pre_ping": True}
    if not pooled:
        kwargs["poolclass"] = NullPool
    elif s.db_type != "sqlite":
        kwargs.update(pool_size=5, max_overflow=2)
    return create_engine(build_url(s), **kwargs)


# One engine per saved connection, rebuilt when the connection changes.
_engines: dict[int, tuple[str, Engine]] = {}


def get_engine(connection_id: int, version: str, spec: ConnSpec) -> Engine:
    cached = _engines.get(connection_id)
    if cached and cached[0] == version:
        return cached[1]
    dispose_engine(connection_id)
    engine = make_engine(spec)
    _engines[connection_id] = (version, engine)
    return engine


def dispose_engine(connection_id: int):
    cached = _engines.pop(connection_id, None)
    if cached:
        cached[1].dispose()


def _is_system(db_type: str, schema: str) -> bool:
    return schema.lower() in SYSTEM_SCHEMAS or (db_type == "mssql" and schema.lower().startswith("db_"))


def list_tables(engine: Engine, s: ConnSpec, only_schemas: list[str]) -> list[dict]:
    """Returns [{"schema": ..., "tables": [{"name": ..., "kind": "table" | "view"}]}]."""
    insp = inspect(engine)
    if s.db_type in ("mysql", "sqlite"):
        schemas: list[str | None] = [None]  # one schema: the connection's own database
    else:
        schemas = [n for n in insp.get_schema_names() if not _is_system(s.db_type, n)]
        if only_schemas:
            wanted = {n.lower() for n in only_schemas}
            schemas = [n for n in schemas if n.lower() in wanted]
    out = []
    for schema in schemas:
        tables = [{"name": t, "kind": "table"} for t in sorted(insp.get_table_names(schema=schema))]
        views = [{"name": v, "kind": "view"} for v in sorted(insp.get_view_names(schema=schema))]
        label = schema or ("main" if s.db_type == "sqlite" else s.database)
        out.append({"schema": label, "tables": tables + views})
    return out


def run_test(engine: Engine, s: ConnSpec, only_schemas: list[str]) -> dict:
    """Connects, runs SELECT 1 and lists the tables. Raises if anything fails."""
    t0 = time.perf_counter()
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    version = ".".join(str(p) for p in (engine.dialect.server_version_info or ()))
    schemas = list_tables(engine, s, only_schemas)
    return {
        "elapsed_ms": round((time.perf_counter() - t0) * 1000),
        "server_version": version,
        "schemas": schemas,
        "table_count": sum(len(x["tables"]) for x in schemas),
    }


def friendly_error(err: Exception) -> str:
    """A short, readable error without driver noise. Drivers don't include the password."""
    if isinstance(err, ModuleNotFoundError):
        return f"The database driver isn't installed ({err.name}). Run pip install -r requirements.txt."
    lines = str(getattr(err, "orig", None) or err).strip().splitlines()
    first = next((line.strip() for line in lines if line.strip()), "Unknown error")
    if "Can't open lib" in first or "Data source name not found" in first:
        return f"The SQL Server ODBC driver isn't installed on the server. Install Microsoft {MSSQL_ODBC_DRIVER}."
    return first[:300]
