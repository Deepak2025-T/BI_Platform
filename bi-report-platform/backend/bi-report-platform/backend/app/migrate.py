"""
Brings the app database up to the latest migration. Run from the backend folder:
    python -m app.migrate

Same as `alembic upgrade head`, except it also handles a database created before Alembic
was added (tables present, no alembic_version table): it adds reports.category_id if that
column is missing, marks the database as being at the baseline migration, then upgrades.
"""

import sys
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text

from .database import engine

BACKEND_DIR = Path(__file__).resolve().parents[1]
BASELINE = "0001_baseline"
BASELINE_TABLES = {"app_users", "reports", "report_categories", "report_templates", "connections", "sales"}


def alembic_config() -> Config:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    return cfg


def adopt_pre_alembic_database(cfg: Config) -> None:
    tables = set(inspect(engine).get_table_names())
    if "alembic_version" in tables or "app_users" not in tables:
        return
    missing = BASELINE_TABLES - tables
    if missing:
        sys.exit(f"This database predates Alembic and is missing tables: {', '.join(sorted(missing))}.\n"
                 "Back it up and create a fresh database with `alembic upgrade head`, then copy the data across.")
    columns = {c["name"] for c in inspect(engine).get_columns("reports")}
    if "category_id" not in columns:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE reports ADD COLUMN category_id INTEGER "
                              "REFERENCES report_categories(id) ON DELETE SET NULL"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_reports_category_id ON reports (category_id)"))
        print("  added reports.category_id")
    command.stamp(cfg, BASELINE)
    print(f"  existing database marked as migration {BASELINE}")


def upgrade() -> None:
    cfg = alembic_config()
    adopt_pre_alembic_database(cfg)
    command.upgrade(cfg, "head")


if __name__ == "__main__":
    upgrade()
    print("Database is up to date.")
