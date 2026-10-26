from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def schema_missing_message() -> str | None:
    """Says what to run when the tables haven't been created by Alembic yet."""
    if inspect(engine).has_table("alembic_version"):
        return None
    return ("The database has no migrations applied. In the backend folder run `alembic upgrade head` "
            "(new database) or `python -m app.migrate` (database from before Alembic). See README Part 5.")
