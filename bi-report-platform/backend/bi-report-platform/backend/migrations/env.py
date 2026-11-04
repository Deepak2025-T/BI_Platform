"""
Alembic environment. Run from the backend folder:
    alembic upgrade head                              apply migrations
    alembic revision --autogenerate -m "add x"        after changing models.py
    alembic check                                     models and migrations match?

The database address comes from DATABASE_URL in backend/.env (app.config.settings),
not from alembic.ini.
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

from app import models  # noqa: F401  registers every table on Base.metadata
from app.config import settings
from app.database import Base

config = context.config

# Keep the app's own loggers (uvicorn) working when migrations run from Python.
if config.config_file_name is not None and config.attributes.get("configure_logger", True):
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


def _configure(**kwargs) -> None:
    context.configure(
        target_metadata=target_metadata,
        compare_type=True,
        # SQLite can't ALTER most columns; batch mode copies the table instead.
        render_as_batch=kwargs.pop("dialect_name", "") == "sqlite",
        **kwargs,
    )


def run_migrations_offline() -> None:
    """Writes the SQL to stdout instead of running it (alembic upgrade head --sql)."""
    _configure(url=settings.database_url, literal_binds=True, dialect_opts={"paramstyle": "named"},
               dialect_name=settings.database_url.split(":", 1)[0].split("+", 1)[0])
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    # Code that already has a connection (see app/migrate.py) can pass it in.
    connection = config.attributes.get("connection")
    if connection is not None:
        _configure(connection=connection, dialect_name=connection.dialect.name)
        with context.begin_transaction():
            context.run_migrations()
        return

    engine = create_engine(settings.database_url, poolclass=pool.NullPool)
    with engine.connect() as connection:
        _configure(connection=connection, dialect_name=connection.dialect.name)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
