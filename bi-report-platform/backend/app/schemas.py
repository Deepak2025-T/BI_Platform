from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

Role = Literal["user", "manager"]


class LoginIn(BaseModel):
    email: str
    password: str


class UserOut(BaseModel):
    id: int
    email: str
    full_name: str
    role: Role
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class LoginOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class UserCreate(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    full_name: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=8, max_length=128)
    role: Role = "user"


class UserUpdate(BaseModel):
    full_name: str | None = None
    role: Role | None = None
    is_active: bool | None = None
    password: str | None = Field(default=None, min_length=8, max_length=128)


class QueryParams(BaseModel):
    period: Literal["q1_2024", "q4_2023"] = "q1_2024"
    measure: Literal["net", "gross"] = "net"
    date_col: Literal["sale_date", "invoice_date"] = "sale_date"
    region: str = "All"


class GenerateIn(BaseModel):
    prompt: str = Field(min_length=3, max_length=2000)
    params: QueryParams | None = None
    # The AI model to understand the question with; None uses the built-in keyword engine.
    model_id: int | None = None


class ReportIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    prompt: str
    config: dict


class ReportUpdate(BaseModel):
    title: str | None = None
    config: dict | None = None
    # Send null to remove the category. Leave the field out to keep it unchanged.
    category_id: int | None = None


class PublishIn(BaseModel):
    category_id: int | None = None


class CategoryRef(BaseModel):
    id: int
    name: str
    color: str

    model_config = {"from_attributes": True}


class ReportOut(BaseModel):
    id: int
    title: str
    prompt: str
    status: str
    config: dict
    owner_id: int
    owner_name: str
    category: CategoryRef | None
    created_at: datetime
    updated_at: datetime
    # Automatic refresh: see refresh.py
    refresh_every: str = "off"
    refresh_at: str = "08:00"
    refresh_weekday: int = 0
    next_refresh_at: datetime | None = None
    last_refreshed_at: datetime | None = None
    last_refresh_error: str = ""
    history_days: int = 30  # snapshots kept for trends and comparisons; 0 = only the newest few


Visibility = Literal["private", "shared"]


class TemplateLayout(BaseModel):
    """Report layout a template applies. Every field is optional; missing ones use the defaults."""

    sections: list[Literal["kpis", "revenue", "products", "insights"]] | None = Field(default=None, min_length=1)
    chart: Literal["grouped", "stacked", "table"] | None = None
    palette: Literal["ocean", "warm", "slate"] | None = None
    fmt: Literal["short", "full"] | None = None
    showValues: bool | None = None
    topN: Literal[3, 5] | None = None
    # Dashboard templates: ready-written charts built on a chosen connection (see routers/templates.build).
    kind: Literal["dashboard"] | None = None
    source_type: str | None = Field(default=None, max_length=20)  # e.g. "openpages": which connections fit
    widgets: list[dict] | None = Field(default=None, max_length=30)
    filters: list[dict] | None = Field(default=None, max_length=10)


class TemplateIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    description: str = Field(default="", max_length=200)
    prompt: str = Field(min_length=3, max_length=2000)
    color: str = Field(default="#00B4D8", pattern=r"^#[0-9A-Fa-f]{6}$")
    layout: TemplateLayout = TemplateLayout()
    visibility: Visibility = "private"


class TemplateUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    description: str | None = Field(default=None, max_length=200)
    prompt: str | None = Field(default=None, min_length=3, max_length=2000)
    color: str | None = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")
    layout: TemplateLayout | None = None
    visibility: Visibility | None = None


class TemplateOut(BaseModel):
    id: int
    name: str
    description: str
    prompt: str
    color: str
    layout: dict
    visibility: Visibility
    is_builtin: bool
    owner_id: int | None
    owner_name: str | None
    can_edit: bool
    created_at: datetime
    updated_at: datetime


class CategoryIn(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    description: str = Field(default="", max_length=200)
    color: str = Field(default="#00B4D8", pattern=r"^#[0-9A-Fa-f]{6}$")


class CategoryUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=60)
    description: str | None = Field(default=None, max_length=200)
    color: str | None = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")


class CategoryOut(BaseModel):
    id: int
    name: str
    description: str
    color: str
    report_count: int
    can_edit: bool


DbType = Literal["postgresql", "mysql", "mssql", "sqlite", "openpages"]
OpenPagesAuth = Literal["basic", "oauth2", "mpjwt", "iam", "mtls"]


class ConnectionOptions(BaseModel):
    ssl: bool = False  # PostgreSQL: sslmode=require
    trust_server_certificate: bool = False  # SQL Server or OpenPages with a self-signed certificate
    # IBM OpenPages only (host holds the API URL, e.g. https://server/grc/api):
    auth_type: OpenPagesAuth = "basic"
    token_url: str = Field(default="", max_length=500)  # OAuth 2.0; IBM Cloud IAM (blank = iam.cloud.ibm.com)
    client_id: str = Field(default="", max_length=200)  # OAuth 2.0
    client_cert: str = Field(default="", max_length=20000)  # mutual TLS: the certificate (PEM), not secret
    has_client_key: bool = False  # mutual TLS: whether a private key is saved; the key is never returned
    audit_id: str = Field(default="", max_length=40)  # optional: the audit questions are usually about
    audit_name: str = Field(default="", max_length=200)


class ConnectionDraft(BaseModel):
    """The connection details on the form. Used to test before saving."""
    db_type: DbType
    host: str = Field(default="", max_length=255)
    port: int | None = Field(default=None, ge=1, le=65535)
    database: str = Field(default="", max_length=255)
    username: str = Field(default="", max_length=128)
    # None keeps the saved password (when editing); a string replaces it. For OpenPages it holds the
    # password, client secret, MP-JWT token or IBM Cloud API key, depending on the sign-in type.
    password: str | None = Field(default=None, max_length=8192)
    # OpenPages mutual TLS: the private key (PEM). None keeps the saved one.
    client_key: str | None = Field(default=None, max_length=20000)
    schemas: list[str] = Field(default_factory=list, max_length=50)
    options: ConnectionOptions = ConnectionOptions()
    # When testing an edited connection, its id lets the saved password be reused.
    id: int | None = None


class ConnectionIn(ConnectionDraft):
    name: str = Field(min_length=1, max_length=80)


class ConnectionUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    db_type: DbType | None = None
    host: str | None = Field(default=None, max_length=255)
    port: int | None = Field(default=None, ge=1, le=65535)
    database: str | None = Field(default=None, max_length=255)
    username: str | None = Field(default=None, max_length=128)
    password: str | None = Field(default=None, max_length=8192)
    client_key: str | None = Field(default=None, max_length=20000)
    schemas: list[str] | None = Field(default=None, max_length=50)
    options: ConnectionOptions | None = None
    allowed_tables: list[str] | None = Field(default=None, max_length=5000)


class ConnectionOut(BaseModel):
    """What managers see. The password is never returned, only whether one is saved."""
    id: int
    name: str
    db_type: DbType
    type_label: str
    host: str
    port: int | None
    database: str
    username: str
    has_password: bool
    schemas: list[str]
    options: ConnectionOptions
    allowed_tables: list[str]
    status: Literal["untested", "ok", "error"]
    last_tested_at: datetime | None
    last_error: str
    created_at: datetime
    updated_at: datetime


class ConnectionPublic(BaseModel):
    """What everyone else sees: the name and type only."""
    id: int
    name: str
    db_type: DbType
    type_label: str
    status: Literal["untested", "ok", "error"]


class TableInfo(BaseModel):
    name: str
    kind: Literal["table", "view"]


class SchemaTables(BaseModel):
    schema_name: str = Field(alias="schema", serialization_alias="schema")
    tables: list[TableInfo]

    model_config = {"populate_by_name": True}


class ConnectionTestOut(BaseModel):
    ok: bool
    message: str
    elapsed_ms: int | None = None
    server_version: str = ""
    table_count: int = 0
    schemas: list[SchemaTables] = []


AIProvider = Literal["ollama", "anthropic", "openai_compatible"]


class AIModelDraft(BaseModel):
    """The model details on the form. Used to test before saving."""
    provider: AIProvider
    model: str = Field(min_length=1, max_length=200)
    base_url: str = Field(default="", max_length=500)
    # None keeps the saved key (when editing); a string replaces it.
    api_key: str | None = Field(default=None, max_length=1000)
    # When testing an edited model, its id lets the saved key be reused.
    id: int | None = None


class AIModelIn(AIModelDraft):
    name: str = Field(min_length=1, max_length=80)
    is_active: bool = True
    is_default: bool = False


class AIModelUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    provider: AIProvider | None = None
    model: str | None = Field(default=None, min_length=1, max_length=200)
    base_url: str | None = Field(default=None, max_length=500)
    api_key: str | None = Field(default=None, max_length=1000)
    is_active: bool | None = None
    is_default: bool | None = None


class AIModelOut(BaseModel):
    """What managers see. The API key is never returned, only whether one is saved."""
    id: int
    name: str
    provider: AIProvider
    provider_label: str
    model: str
    base_url: str
    has_api_key: bool
    is_active: bool
    is_default: bool
    status: Literal["untested", "ok", "error"]
    last_tested_at: datetime | None
    last_error: str
    created_at: datetime
    updated_at: datetime


class AIModelPublic(BaseModel):
    """What everyone sees in the model picker."""
    id: int
    name: str
    provider: AIProvider
    provider_label: str
    is_default: bool


class AIModelTestOut(BaseModel):
    ok: bool
    message: str
    elapsed_ms: int | None = None


class AIDiscoverIn(BaseModel):
    provider: AIProvider
    base_url: str = Field(default="", max_length=500)
    api_key: str | None = Field(default=None, max_length=1000)
    id: int | None = None


class AIProviderInfo(BaseModel):
    id: AIProvider
    label: str
    needs_base_url: bool
    needs_key: bool
    default_base_url: str
    suggested_models: list[str]


class SourceOut(BaseModel):
    """A database people can chat with. id is None for the built-in sample data."""
    id: int | None
    name: str
    db_type: str
    type_label: str
    table_count: int
    builtin: bool


class ChatTurn(BaseModel):
    question: str = Field(max_length=2000)
    reply: str = Field(default="", max_length=4000)
    sql: str = Field(default="", max_length=8000)


class ChatIn(BaseModel):
    source_id: int | None = None
    model_id: int
    question: str = Field(min_length=2, max_length=2000)
    history: list[ChatTurn] = Field(default_factory=list, max_length=20)


class WidgetIn(BaseModel):
    source_id: int | None = None
    model_id: int
    question: str = Field(min_length=2, max_length=1000)


class DashboardParams(BaseModel):
    date_from: date | None = None
    date_to: date | None = None
    filters: str = Field(default="", max_length=300)


class DashboardIn(BaseModel):
    source_id: int | None = None
    model_id: int
    prompt: str = Field(min_length=3, max_length=2000)
    parameters: DashboardParams = DashboardParams()


class Widget(BaseModel):
    id: str = Field(min_length=1, max_length=40)
    title: str = Field(max_length=120)
    question: str = Field(default="", max_length=500)
    sql: str = Field(min_length=1, max_length=8000)
    chart: dict


class SaveDashboardIn(BaseModel):
    source_id: int | None = None
    title: str = Field(min_length=1, max_length=200)
    prompt: str = Field(default="", max_length=2000)
    widgets: list[Widget] = Field(min_length=1, max_length=12)


class FilterValue(BaseModel):
    """A dashboard filter's value in the viewer: dates for a date filter, values for a category."""
    date_from: date | None = None
    date_to: date | None = None
    values: list[str] = Field(default_factory=list, max_length=50)


class DashboardDataIn(BaseModel):
    filters: dict[str, FilterValue] = Field(default_factory=dict, max_length=10)
    refresh: bool = False  # skip the result cache


class FilterMapIn(BaseModel):
    model_id: int
    label: str = Field(min_length=1, max_length=60)
    kind: Literal["date", "category"]
    id: str | None = Field(default=None, max_length=40)  # set to map an existing filter again
    widgets: list[Widget] = Field(max_length=40)
