"""Metadata database: connections, model settings, reports, RAG chunks (pgvector), ETL runs, forecasts."""
import base64
import hashlib
from datetime import datetime, timezone

from cryptography.fernet import Fernet
from pgvector.sqlalchemy import Vector
from sqlalchemy import (JSON, Boolean, DateTime, ForeignKey, Integer, String, Text,
                        create_engine, text)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from .config import get_settings

settings = get_settings()
engine = create_engine(settings.app_db_url, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Base(DeclarativeBase):
    pass


class DbConnection(Base):
    __tablename__ = "db_connections"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    dialect: Mapped[str] = mapped_column(String(30))          # postgres, mysql, mssql, oracle, db2, sqlite
    host: Mapped[str | None] = mapped_column(String(255))
    port: Mapped[int | None] = mapped_column(Integer)
    database: Mapped[str] = mapped_column(String(255))
    username: Mapped[str | None] = mapped_column(String(255))
    password_enc: Mapped[str | None] = mapped_column(Text)
    schema_name: Mapped[str | None] = mapped_column(String(120))
    options: Mapped[dict] = mapped_column(JSON, default=dict)
    indexed_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class AppSetting(Base):
    __tablename__ = "app_settings"
    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    value: Mapped[dict] = mapped_column(JSON)


class RagChunk(Base):
    """Schema docs, glossary entries and verified prompt→SQL examples, embedded for retrieval."""
    __tablename__ = "rag_chunks"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    connection_id: Mapped[int] = mapped_column(ForeignKey("db_connections.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(20))              # table | glossary | example
    ref: Mapped[str] = mapped_column(String(255))              # table name / term / prompt
    content: Mapped[str] = mapped_column(Text)
    meta: Mapped[dict] = mapped_column(JSON, default=dict)
    embedding = mapped_column(Vector(settings.embedding_dim))


class Report(Base):
    __tablename__ = "reports"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(255))
    prompt: Mapped[str | None] = mapped_column(Text)
    connection_id: Mapped[int | None] = mapped_column(ForeignKey("db_connections.id", ondelete="SET NULL"))
    template_id: Mapped[str | None] = mapped_column(String(50))
    spec: Mapped[dict] = mapped_column(JSON)                   # layout + widgets (sql, chart config, style)
    published: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class QueryLog(Base):
    __tablename__ = "query_log"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    connection_id: Mapped[int | None] = mapped_column(Integer)
    prompt: Mapped[str | None] = mapped_column(Text)
    sql: Mapped[str | None] = mapped_column(Text)
    provider: Mapped[str | None] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(20))
    error: Mapped[str | None] = mapped_column(Text)
    attempts: Mapped[int] = mapped_column(Integer, default=1)
    row_count: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class EtlRun(Base):
    __tablename__ = "etl_runs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    connection_id: Mapped[int] = mapped_column(ForeignKey("db_connections.id", ondelete="CASCADE"))
    file_name: Mapped[str] = mapped_column(String(255))
    file_type: Mapped[str] = mapped_column(String(20))
    target_table: Mapped[str | None] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(20), default="extracted")  # extracted|mapped|validated|loaded|failed
    mapping: Mapped[dict] = mapped_column(JSON, default=dict)
    change_log: Mapped[list] = mapped_column(JSON, default=list)
    issues: Mapped[list] = mapped_column(JSON, default=list)
    rows_extracted: Mapped[int] = mapped_column(Integer, default=0)
    rows_loaded: Mapped[int] = mapped_column(Integer, default=0)
    staging_path: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


def init_db() -> None:
    with engine.begin() as c:
        c.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    Base.metadata.create_all(engine)
    with engine.begin() as c:
        c.execute(text(
            "CREATE INDEX IF NOT EXISTS rag_chunks_embedding_idx ON rag_chunks "
            "USING hnsw (embedding vector_cosine_ops)"))


# ---------- secrets ----------
def _fernet() -> Fernet:
    key = base64.urlsafe_b64encode(hashlib.sha256(settings.secret_key.encode()).digest())
    return Fernet(key)


def encrypt(value: str | None) -> str | None:
    return _fernet().encrypt(value.encode()).decode() if value else None


def decrypt(value: str | None) -> str | None:
    return _fernet().decrypt(value.encode()).decode() if value else None
