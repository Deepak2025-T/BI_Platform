export type Role = "user" | "manager";

export interface User {
  id: number;
  email: string;
  full_name: string;
  role: Role;
  is_active: boolean;
  created_at: string;
}

export type PeriodId = "q1_2024" | "q4_2023";
export type MeasureId = "net" | "gross";
export type DateCol = "sale_date" | "invoice_date";

export interface QueryParams {
  period: PeriodId;
  measure: MeasureId;
  date_col: DateCol;
  region: string; // "All" or a region name
}

export interface Attempt {
  ok: boolean;
  message: string;
}

export interface QueryResult {
  params: QueryParams;
  title: string;
  measure_label: string;
  period_label: string;
  period_short: string;
  months: string[];
  regions: string[];
  series: Record<string, number[]>;
  total: number;
  compare: { pct: number; label: string } | null;
  products: { name: string; value: number }[];
  sql: string;
  explanation: string;
  row_count: number;
  elapsed_ms: number;
  source: string;
  attempts?: Attempt[];
  /** The AI model that understood the question, or null for the built-in engine. */
  model?: string | null;
  needs_confirmation?: { kind: "date_col"; message: string; options: DateCol[] } | null;
}

export interface GenerationFailure {
  reason: string;
  attempts: Attempt[];
  last_sql: string;
  can_edit_sql: boolean;
}

export type SectionId = "kpis" | "revenue" | "products" | "insights";
export type ChartKind = "grouped" | "stacked" | "table";
export type PaletteId = "ocean" | "warm" | "slate";
export type NumberFormat = "short" | "full";

export interface ReportConfig {
  params: QueryParams;
  sections: SectionId[];
  chart: ChartKind;
  palette: PaletteId;
  fmt: NumberFormat;
  showValues: boolean;
  topN: 3 | 5;
  /** Width and height of each section; missing means full width and the default height. */
  sizes?: Partial<Record<SectionId, SectionSize>>;
}

export interface SectionSize {
  size?: WidgetSize;
  /** Revenue chart only: height in pixels. */
  height?: number;
}

export interface CategoryRef {
  id: number;
  name: string;
  color: string;
}

export interface Category extends CategoryRef {
  description: string;
  /** Reports in this category that you can see. */
  report_count: number;
  can_edit: boolean;
}

export interface CategoryInput {
  name: string;
  description: string;
  color: string;
}

export interface Report {
  id: number;
  title: string;
  prompt: string;
  status: "draft" | "published";
  /** A classic sales report, or a dashboard built by an AI model. */
  config: ReportConfig | DashboardConfig;
  owner_id: number;
  owner_name: string;
  category: CategoryRef | null;
  created_at: string;
  updated_at: string;
  /** Automatic refresh: the report's queries run on this schedule and the results are saved. */
  refresh_every: RefreshEvery;
  /** Daily and weekly: HH:MM, server time. */
  refresh_at: string;
  /** Weekly: 0 = Monday. */
  refresh_weekday: number;
  next_refresh_at: string | null;
  last_refreshed_at: string | null;
  last_refresh_error: string;
  /** Days of refreshes kept for trends and comparisons; 0 keeps only the newest few. */
  history_days: number;
}

export type RefreshEvery = "off" | "15min" | "hourly" | "6hours" | "daily" | "weekly";

/** Layout a template applies to new reports. Missing fields use the defaults. */
export type ClassicLayout = Partial<Pick<ReportConfig, "sections" | "chart" | "palette" | "fmt" | "showValues" | "topN">>;
export type TemplateLayout = ClassicLayout & {
  /** Dashboard templates: ready-written charts, built on a connection you choose. */
  kind?: "dashboard";
  /** Which connections fit, e.g. "openpages". */
  source_type?: DbType;
  widgets?: Omit<Widget, "id">[];
  filters?: { label: string; kind: "date" | "category"; type?: string; field?: string }[];
};
export type TemplateVisibility = "private" | "shared";
/** The domain a template is filed under. */
export type TemplateCategory = "ERP" | "GRC" | "Common" | "Uncategorised";

export interface ReportTemplate {
  id: number;
  name: string;
  description: string;
  prompt: string;
  color: string;
  category: TemplateCategory;
  layout: TemplateLayout;
  visibility: TemplateVisibility;
  is_builtin: boolean;
  owner_id: number | null;
  owner_name: string | null;
  can_edit: boolean;
  created_at: string;
  updated_at: string;
}

export interface TemplateInput {
  name: string;
  description: string;
  prompt: string;
  color: string;
  category: TemplateCategory;
  layout: TemplateLayout;
  visibility: TemplateVisibility;
}

export type DbType = "postgresql" | "mysql" | "mssql" | "sqlite" | "openpages";
export type OpenPagesAuth = "basic" | "oauth2" | "mpjwt" | "iam" | "mtls";
export type ConnectionStatus = "untested" | "ok" | "error";

export interface ConnectionOptions {
  ssl: boolean;
  /** SQL Server, or OpenPages with a self-signed certificate. */
  trust_server_certificate: boolean;
  /** IBM OpenPages only. */
  auth_type?: OpenPagesAuth;
  token_url?: string;
  client_id?: string;
  client_cert?: string;
  /** Whether a private key is saved (mutual TLS); the key itself is never sent back. */
  has_client_key?: boolean;
  audit_id?: string;
  audit_name?: string;
}

/** A database connection as managers see it. The password is never sent back. */
export interface DataConnection {
  id: number;
  name: string;
  db_type: DbType;
  type_label: string;
  host: string;
  port: number | null;
  database: string;
  username: string;
  has_password: boolean;
  schemas: string[];
  options: ConnectionOptions;
  allowed_tables: string[];
  status: ConnectionStatus;
  last_tested_at: string | null;
  last_error: string;
  created_at: string;
  updated_at: string;
}

export interface ConnectionInput {
  name: string;
  db_type: DbType;
  host: string;
  port: number | null;
  database: string;
  username: string;
  /** Leave out (or null) to keep the saved password. For OpenPages: password, client secret, token or API key. */
  password?: string | null;
  /** OpenPages mutual TLS private key (PEM). Leave out to keep the saved one. */
  client_key?: string | null;
  schemas: string[];
  options: ConnectionOptions;
}

export interface SchemaTables {
  schema: string;
  tables: { name: string; kind: "table" | "view" }[];
}

export interface ConnectionTestResult {
  ok: boolean;
  message: string;
  elapsed_ms: number | null;
  server_version: string;
  table_count: number;
  schemas: SchemaTables[];
}

export type AIProvider = "ollama" | "anthropic" | "openai_compatible";

/** An AI model as managers see it. The API key is never sent back. */
export interface AIModel {
  id: number;
  name: string;
  provider: AIProvider;
  provider_label: string;
  model: string;
  base_url: string;
  has_api_key: boolean;
  is_active: boolean;
  is_default: boolean;
  status: ConnectionStatus;
  last_tested_at: string | null;
  last_error: string;
  created_at: string;
  updated_at: string;
}

/** What everyone sees in the model picker. */
export interface AIModelPublic {
  id: number;
  name: string;
  provider: AIProvider;
  provider_label: string;
  is_default: boolean;
}

export interface AIModelInput {
  name: string;
  provider: AIProvider;
  model: string;
  base_url: string;
  /** Leave out (or null) to keep the saved key. */
  api_key?: string | null;
  is_active: boolean;
  is_default: boolean;
}

export interface AIProviderInfo {
  id: AIProvider;
  label: string;
  needs_base_url: boolean;
  needs_key: boolean;
  default_base_url: string;
  suggested_models: string[];
}

export interface AIModelTestResult {
  ok: boolean;
  message: string;
  elapsed_ms: number | null;
}

/** A database people can chat with. id is null for the built-in sample data. */
export interface DataSourceInfo {
  id: number | null;
  name: string;
  db_type: DbType;
  type_label: string;
  table_count: number;
  builtin: boolean;
}

/**
 * How a chart is drawn. The first six are the original set and are still what older reports save;
 * the rest came with the visual builder. Clustered, stacked and 100% bars are all "bar" with
 * different `WidgetStyle` flags, the way the renderer has always handled them.
 */
export type ChartType =
  | "kpi" | "bar" | "line" | "area" | "pie" | "table"
  | "combo" | "scatter" | "donut" | "gauge" | "matrix";

export interface ChartSpec {
  type: ChartType;
  /** Column with categories or dates (empty for kpi and table). */
  x: string;
  /** Numeric columns to plot. */
  y: string[];
  /** Combo charts: the columns drawn as a line instead of bars. Scatter: y[0] is X, y2[0] is Y. */
  y2?: string[];
  /** Scatter: the column that sets each point's size. Gauge: the column holding the target. */
  extra?: string;
  /** Matrix and multi-series charts: the column whose values become one series or column each. */
  legend?: string;
}

export type Cell = string | number | boolean | null;

export interface QueryData {
  sql: string;
  columns: string[];
  rows: Cell[][];
  row_count: number;
  truncated: boolean;
  elapsed_ms: number;
  /** Dashboards: whether the result came from the 15-minute cache, and when the query ran. */
  cached?: boolean;
  ran_at?: string;
}

export interface ChatAttempt extends Attempt {
  sql?: string;
}

export type ChatResult =
  | { kind: "reply"; reply: string; attempts: ChatAttempt[]; elapsed_ms: number; model: string; source: string }
  | ({ kind: "result"; reply: string; title: string; chart: ChartSpec; attempts: ChatAttempt[]; model: string; source: string } & QueryData);

/** How a number column is summarised. Matches AGGS in backend/app/visual_query.py. */
export type Agg = "sum" | "avg" | "min" | "max" | "count" | "count_distinct";

/** How a date column is grouped. The query returns sortable text: "2024", "2024-Q1", "2024-03". */
export type DateBucket = "year" | "quarter" | "month" | "week" | "day";

export type FilterOp =
  | "=" | "!=" | ">" | ">=" | "<" | "<="
  | "contains" | "starts_with" | "ends_with"
  | "between" | "in" | "not_in" | "is_null" | "is_not_null";

/** A column people drag onto an axis or a legend. */
export interface VisualDimension {
  column: string;
  /** Date columns only: group by year, quarter, month, week or day. */
  bucket?: DateBucket;
  /** The name the chart shows. Missing uses the column name. */
  alias?: string;
}

/** A column people drag onto Values, with the way it is summarised. */
export interface VisualMeasure {
  /** Empty with agg "count" counts rows. */
  column: string;
  agg: Agg;
  alias?: string;
}

export interface VisualFilter {
  column: string;
  op: FilterOp;
  /** "is_null" and "is_not_null" take none, "between" takes two, "in" takes any number. */
  values?: (string | number)[];
}

/**
 * One chart as the builder describes it, before it becomes SQL. The backend compiles this with
 * visual_query.compile_spec; the browser never writes SQL.
 */
export interface VisualSpec {
  table: string;
  dimensions: VisualDimension[];
  measures: VisualMeasure[];
  filters: VisualFilter[];
  order: { ref: string; dir: "asc" | "desc" }[];
  limit?: number | null;
}

/** A column of a shared table, as the fields pane lists it. */
export interface VisualField {
  name: string;
  type: string;
  /** What it is good for by default: a number to add up, or something to group by. */
  role: "dimension" | "measure";
  is_date: boolean;
  is_number: boolean;
}

export interface VisualFields {
  table: string;
  fields: VisualField[];
}

export interface VisualTable {
  /** "schema.table", the name specs use. */
  table: string;
  schema: string;
  name: string;
}

export interface VisualBuildRequest {
  source_id: number | null;
  spec: VisualSpec;
  refresh?: boolean;
}

export interface Widget {
  id: string;
  title: string;
  question: string;
  sql: string;
  chart: ChartSpec;
  /**
   * Set when the chart was built by dragging fields instead of being written or asked for.
   * `sql` still holds the compiled query, so the viewer, dashboard filters, refresh and export
   * treat it like any other chart; this is kept only so the builder can reopen it.
   */
  visual?: VisualSpec;
  /** Width on the dashboard; "auto" (or missing) picks from the chart type. */
  size?: WidgetSize;
  /** "text" tiles are headings and notes between charts: no SQL, just title and text. */
  kind?: "chart" | "text";
  text?: string;
  style?: WidgetStyle;
  /** Chart height in pixels (default 280). Tables scroll inside it. */
  height?: number;
}

export type WidgetSize = "auto" | "quarter" | "third" | "half" | "twothird" | "full";

/** How a chart looks. Everything is optional; missing means the default. */
export interface WidgetStyle {
  /** Main colour (first series, KPI number). */
  color?: string;
  showValues?: boolean;
  /** Show the legend when there are several series or a pie (default true). */
  legend?: boolean;
  format?: "auto" | "full" | "currency" | "percent";
  /** Symbol for the currency format, e.g. £, $, ₹. */
  currency?: string;
  sort?: "none" | "desc" | "asc";
  horizontal?: boolean;
  stacked?: boolean;
  /** How several series sit together. "full" is 100% stacked. Falls back to `stacked` when missing. */
  stackMode?: "none" | "stacked" | "full";
  /** Gauge: the ends of the dial. Missing means 0 and the value's own scale. */
  gaugeMin?: number;
  gaugeMax?: number;
  /** Number tiles: which way is good, for colouring the change since an earlier refresh. */
  goodWhen?: "up" | "down";
  /** The tile's header band and card background. Text switches to white on dark colours. */
  headBg?: string;
  cardBg?: string;
}

export interface DashboardParameters {
  date_from: string | null;
  date_to: string | null;
  filters: string;
}

/** A report built by an AI model: charts, each with its own saved SQL. */
export interface DashboardConfig {
  kind: "dashboard";
  source_id: number | null;
  source_name: string;
  widgets: Widget[];
  parameters?: DashboardParameters;
  model?: string;
  filters?: DashboardFilter[];
}

/** A dashboard-wide filter. The AI model picks each chart's column once, when the filter is added. */
export interface DashboardFilter {
  id: string;
  label: string;
  kind: "date" | "category";
  /** Category filters: the values people can pick. */
  options: string[];
  /** Chart id -> the column it filters on. Charts missing here aren't filtered. */
  columns: Record<string, { table: string; column: string }>;
}

export interface FilterValue {
  date_from?: string | null;
  date_to?: string | null;
  values?: string[];
}

export interface DashboardDataRequest {
  filters: Record<string, FilterValue>;
  refresh?: boolean;
}

/** Ids of the active filters that did and didn't apply to a chart. */
type FilterInfo = { filtered?: string[]; not_filtered?: string[] };
export type WidgetData = (({ id: string; ok: true } & QueryData) | { id: string; ok: false; error: string }) & FilterInfo;

export function isDashboard(config: Report["config"]): config is DashboardConfig {
  return (config as DashboardConfig).kind === "dashboard";
}
