from datetime import date, datetime, timezone

from sqlalchemy import JSON, Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base

ROLES = ("user", "manager")


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "app_users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(120))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default="user")  # "user" | "manager"
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

    reports: Mapped[list["Report"]] = relationship(back_populates="owner")
    templates: Mapped[list["ReportTemplate"]] = relationship(back_populates="owner")


class ReportCategory(Base):
    """A folder-like label for reports, chosen when a report is published."""

    __tablename__ = "report_categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(60), unique=True)
    description: Mapped[str] = mapped_column(String(200), default="")
    color: Mapped[str] = mapped_column(String(9), default="#00B4D8")
    created_by: Mapped[int | None] = mapped_column(ForeignKey("app_users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

    reports: Mapped[list["Report"]] = relationship(back_populates="category")


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    prompt: Mapped[str] = mapped_column(String(2000))
    status: Mapped[str] = mapped_column(String(20), default="draft")  # "draft" | "published"
    # Query parameters + layout (sections, chart type, palette, number format ...)
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    owner_id: Mapped[int] = mapped_column(ForeignKey("app_users.id"))
    category_id: Mapped[int | None] = mapped_column(
        ForeignKey("report_categories.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)
    # Automatic refresh (see refresh.py). "off" | "15min" | "hourly" | "6hours" | "daily" | "weekly";
    # daily and weekly run at refresh_at (HH:MM, server time), weekly on refresh_weekday (0 = Monday).
    refresh_every: Mapped[str] = mapped_column(String(10), default="off", server_default="off")
    refresh_at: Mapped[str] = mapped_column(String(5), default="08:00", server_default="08:00")
    refresh_weekday: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    next_refresh_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    last_refreshed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_refresh_error: Mapped[str] = mapped_column(String(500), default="", server_default="")
    # How many days of snapshots to keep for trends and comparisons; 0 keeps only the newest few (history.py).
    history_days: Mapped[int] = mapped_column(Integer, default=30, server_default="30")

    owner: Mapped[User] = relationship(back_populates="reports")
    category: Mapped[ReportCategory | None] = relationship(back_populates="reports")


class ReportSnapshot(Base):
    """The data a report showed at one refresh, so viewers see the same numbers without
    querying the database each time. The newest few are kept per report."""

    __tablename__ = "report_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    report_id: Mapped[int] = mapped_column(ForeignKey("reports.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    trigger: Mapped[str] = mapped_column(String(10))  # "schedule" | "manual"
    # Dashboards: {"widgets": [...]}, classic reports: {"result": {...}}
    data: Mapped[dict] = mapped_column(JSON)
    # Dashboards: a few numbers per chart, for trends (history.summarize). None until worked out.
    summary: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class ReportTemplate(Base):
    """A starting point for a report: a question plus an optional layout."""

    __tablename__ = "report_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    description: Mapped[str] = mapped_column(String(200), default="")
    prompt: Mapped[str] = mapped_column(String(2000))
    color: Mapped[str] = mapped_column(String(9), default="#00B4D8")
    # Optional layout applied to reports built from this template (sections, chart, palette ...)
    layout: Mapped[dict] = mapped_column(JSON, default=dict)
    visibility: Mapped[str] = mapped_column(String(20), default="private")  # "private" | "shared"
    is_builtin: Mapped[bool] = mapped_column(Boolean, default=False)
    owner_id: Mapped[int | None] = mapped_column(ForeignKey("app_users.id", ondelete="CASCADE"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)

    owner: Mapped[User | None] = relationship(back_populates="templates")


class DataConnection(Base):
    """A business database that reports can query. Always use a read-only account."""

    __tablename__ = "connections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True)
    db_type: Mapped[str] = mapped_column(String(20))  # a key of connections.engines.DB_TYPES
    host: Mapped[str] = mapped_column(String(255), default="")
    port: Mapped[int | None] = mapped_column(Integer, nullable=True)
    database: Mapped[str] = mapped_column(String(255))  # database name, or the file path for SQLite
    username: Mapped[str] = mapped_column(String(128), default="")
    password_encrypted: Mapped[str] = mapped_column(String(1024), default="")  # Fernet token, never returned
    # Schemas to include when listing tables; empty means all non-system schemas.
    schemas: Mapped[list] = mapped_column(JSON, default=list)
    # Tables users may query, as "schema.table".
    allowed_tables: Mapped[list] = mapped_column(JSON, default=list)
    options: Mapped[dict] = mapped_column(JSON, default=dict)  # {"ssl": bool, "trust_server_certificate": bool}
    status: Mapped[str] = mapped_column(String(20), default="untested")  # "untested" | "ok" | "error"
    last_tested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str] = mapped_column(String(500), default="")
    created_by: Mapped[int | None] = mapped_column(ForeignKey("app_users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)


class AIModel(Base):
    """An AI model people can pick when they ask a question: local (Ollama) or a hosted API."""

    __tablename__ = "ai_models"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True)  # shown to users, e.g. "Qwen 14B (local)"
    provider: Mapped[str] = mapped_column(String(30))  # a key of ai.providers.PROVIDERS
    model: Mapped[str] = mapped_column(String(200))  # the provider's model id, e.g. "qwen2.5-coder:14b"
    base_url: Mapped[str] = mapped_column(String(500), default="")  # Ollama or OpenAI-compatible server
    api_key_encrypted: Mapped[str] = mapped_column(String(2048), default="")  # Fernet token, never returned
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)  # users can pick active models only
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)  # preselected in the Ask box
    status: Mapped[str] = mapped_column(String(20), default="untested")  # "untested" | "ok" | "error"
    last_tested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str] = mapped_column(String(500), default="")
    created_by: Mapped[int | None] = mapped_column(ForeignKey("app_users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)


class ChatConversation(Base):
    """A saved chat with one database. Private to the person who started it."""

    __tablename__ = "chat_conversations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("app_users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(120))
    # The connection it talks to; None is the built-in sample data. Not a foreign key on purpose:
    # if the connection is deleted, the chat must not quietly turn into a chat about the sample data.
    source_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_name: Mapped[str] = mapped_column(String(80))  # kept so the list still reads well if the connection goes
    model_id: Mapped[int | None] = mapped_column(ForeignKey("ai_models.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)

    messages: Mapped[list["ChatMessage"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan", order_by="ChatMessage.id")


class ChatMessage(Base):
    """One question in a chat and what came back: the answer (with SQL, rows and chart) or an error."""

    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("chat_conversations.id", ondelete="CASCADE"), index=True)
    question: Mapped[str] = mapped_column(String(2000))
    status: Mapped[str] = mapped_column(String(10))  # "ok" | "error"
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # what POST /api/assistant/chat returns
    error: Mapped[str] = mapped_column(String(1000), default="")
    model_name: Mapped[str] = mapped_column(String(80), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

    conversation: Mapped[ChatConversation] = relationship(back_populates="messages")


class Sale(Base):
    """Sample business table so the app has real data to query on day one."""

    __tablename__ = "sales"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sale_date: Mapped[date] = mapped_column(Date, index=True)
    invoice_date: Mapped[date] = mapped_column(Date, index=True)
    region: Mapped[str] = mapped_column(String(40))
    product: Mapped[str] = mapped_column(String(80))
    revenue: Mapped[float] = mapped_column(Numeric(14, 2))
    discount: Mapped[float] = mapped_column(Numeric(14, 2))
    refund_amount: Mapped[float] = mapped_column(Numeric(14, 2))
