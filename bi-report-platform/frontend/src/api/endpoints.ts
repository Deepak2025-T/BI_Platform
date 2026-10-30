import { api } from "./client";
import type {
  ChatResult, DashboardConfig, DashboardDataRequest, DashboardFilter, DashboardParameters, DataSourceInfo, QueryData, Widget, WidgetData,
  AIModel, AIModelInput, AIModelPublic, AIModelTestResult, AIProvider, AIProviderInfo, Category, CategoryInput, ConnectionInput, ConnectionTestResult, DataConnection, QueryParams, QueryResult, Report,
  ReportConfig, ReportTemplate, Role, SchemaTables, TemplateInput, User,
} from "./types";

export const authApi = {
  login: (email: string, password: string) =>
    api.post<{ access_token: string; user: User }>("/api/auth/login", { email, password }).then((r) => r.data),
  me: () => api.get<User>("/api/auth/me").then((r) => r.data),
};

export const queryApi = {
  /** modelId null uses the built-in keyword engine. Local models can be slow, so allow 2 minutes. */
  generate: (prompt: string, modelId: number | null = null) =>
    api.post<QueryResult>("/api/query/generate", { prompt, model_id: modelId }, { timeout: 120000 }).then((r) => r.data),
  run: (params: QueryParams) => api.post<QueryResult>("/api/query/run", params).then((r) => r.data),
};

export const reportsApi = {
  list: () => api.get<Report[]>("/api/reports").then((r) => r.data),
  get: (id: number) => api.get<Report>(`/api/reports/${id}`).then((r) => r.data),
  create: (title: string, prompt: string, config: ReportConfig) =>
    api.post<Report>("/api/reports", { title, prompt, config }).then((r) => r.data),
  /** Pass category_id: null to remove the category; leave it out to keep it. */
  update: (id: number, body: { title?: string; config?: ReportConfig | DashboardConfig; category_id?: number | null }) =>
    api.put<Report>(`/api/reports/${id}`, body).then((r) => r.data),
  publish: (id: number, categoryId: number | null) =>
    api.post<Report>(`/api/reports/${id}/publish`, { category_id: categoryId }).then((r) => r.data),
  remove: (id: number) => api.delete(`/api/reports/${id}`),
};

export const templatesApi = {
  list: () => api.get<ReportTemplate[]>("/api/templates").then((r) => r.data),
  create: (body: TemplateInput) => api.post<ReportTemplate>("/api/templates", body).then((r) => r.data),
  update: (id: number, body: Partial<TemplateInput>) =>
    api.put<ReportTemplate>(`/api/templates/${id}`, body).then((r) => r.data),
  remove: (id: number) => api.delete(`/api/templates/${id}`),
  /** Dashboard templates: builds a draft dashboard on a connection. Charts that can't run there are skipped. */
  build: (id: number, sourceId: number) =>
    api.post<{ report: Report; skipped: { title: string; reason: string }[] }>(`/api/templates/${id}/build`,
      { source_id: sourceId }, { timeout: 180000 }).then((r) => r.data),
};

export const categoriesApi = {
  list: () => api.get<Category[]>("/api/categories").then((r) => r.data),
  create: (body: CategoryInput) => api.post<Category>("/api/categories", body).then((r) => r.data),
  update: (id: number, body: Partial<CategoryInput>) => api.put<Category>(`/api/categories/${id}`, body).then((r) => r.data),
  remove: (id: number) => api.delete(`/api/categories/${id}`),
};

export const connectionsApi = {
  list: () => api.get<DataConnection[]>("/api/connections").then((r) => r.data),
  create: (body: ConnectionInput) => api.post<DataConnection>("/api/connections", body).then((r) => r.data),
  update: (id: number, body: Partial<ConnectionInput> & { allowed_tables?: string[] }) =>
    api.put<DataConnection>(`/api/connections/${id}`, body).then((r) => r.data),
  remove: (id: number) => api.delete(`/api/connections/${id}`),
  /** Tests the form's details without saving. Pass id to reuse a saved password. */
  testDraft: (body: Omit<ConnectionInput, "name"> & { id?: number }) =>
    api.post<ConnectionTestResult>("/api/connections/test", body, { timeout: 60000 }).then((r) => r.data),
  test: (id: number) => api.post<ConnectionTestResult>(`/api/connections/${id}/test`, null, { timeout: 60000 }).then((r) => r.data),
  tables: (id: number) => api.get<SchemaTables[]>(`/api/connections/${id}/tables`, { timeout: 60000 }).then((r) => r.data),
};

export const aiModelsApi = {
  providers: () => api.get<AIProviderInfo[]>("/api/ai-models/providers").then((r) => r.data),
  available: () => api.get<AIModelPublic[]>("/api/ai-models/available").then((r) => r.data),
  list: () => api.get<AIModel[]>("/api/ai-models").then((r) => r.data),
  create: (body: AIModelInput) => api.post<AIModel>("/api/ai-models", body).then((r) => r.data),
  update: (id: number, body: Partial<AIModelInput>) => api.put<AIModel>(`/api/ai-models/${id}`, body).then((r) => r.data),
  remove: (id: number) => api.delete(`/api/ai-models/${id}`),
  /** Tests the form's details without saving. Pass id to reuse a saved key. */
  testDraft: (body: { provider: AIProvider; model: string; base_url: string; api_key?: string | null; id?: number }) =>
    api.post<AIModelTestResult>("/api/ai-models/test", body, { timeout: 310000 }).then((r) => r.data),
  test: (id: number) => api.post<AIModelTestResult>(`/api/ai-models/${id}/test`, null, { timeout: 310000 }).then((r) => r.data),
  discover: (body: { provider: AIProvider; base_url: string; api_key?: string | null; id?: number }) =>
    api.post<string[]>("/api/ai-models/discover", body, { timeout: 30000 }).then((r) => r.data),
};

/** AI chat with a database, and AI-built dashboards. Model calls can be slow, so allow a few minutes. */
export const assistantApi = {
  sources: () => api.get<DataSourceInfo[]>("/api/sources").then((r) => r.data),
  chat: (body: { source_id: number | null; model_id: number; question: string;
                 history: { question: string; reply: string; sql: string }[] }) =>
    api.post<ChatResult>("/api/assistant/chat", body, { timeout: 240000 }).then((r) => r.data),
  widget: (body: { source_id: number | null; model_id: number; question: string }) =>
    api.post<{ widget: Widget; data: QueryData }>("/api/assistant/widget", body, { timeout: 240000 }).then((r) => r.data),
  dashboard: (body: { source_id: number | null; model_id: number; prompt: string; parameters: DashboardParameters }) =>
    api.post<{ report: Report; failed: { title: string; error: string }[] }>("/api/assistant/dashboard", body, { timeout: 420000 })
      .then((r) => r.data),
  save: (body: { source_id: number | null; title: string; prompt: string; widgets: Widget[] }) =>
    api.post<Report>("/api/assistant/save", body).then((r) => r.data),
  data: (reportId: number, body: DashboardDataRequest = { filters: {} }) =>
    api.post<{ source: string; widgets: WidgetData[]; snapshot_at: string | null }>(`/api/reports/${reportId}/data`, body, { timeout: 120000 }).then((r) => r.data),
  /** The dashboard as an .xlsx file, one sheet per chart, with the same filters. */
  exportExcel: (reportId: number, body: DashboardDataRequest) =>
    api.post<Blob>(`/api/reports/${reportId}/export`, body, { timeout: 180000, responseType: "blob" }).then((r) => r.data),
  /** Design time: the AI model picks the column each chart filters on. Nothing is saved. */
  mapFilter: (reportId: number, body: { model_id: number; label: string; kind: DashboardFilter["kind"]; id?: string; widgets: Widget[] }) =>
    api.post<DashboardFilter>(`/api/reports/${reportId}/filters/map`, body, { timeout: 240000 }).then((r) => r.data),
};

export const usersApi = {
  list: () => api.get<User[]>("/api/users").then((r) => r.data),
  create: (body: { email: string; full_name: string; password: string; role: Role }) =>
    api.post<User>("/api/users", body).then((r) => r.data),
  update: (id: number, body: Partial<{ full_name: string; role: Role; is_active: boolean; password: string }>) =>
    api.patch<User>(`/api/users/${id}`, body).then((r) => r.data),
};

export interface Usage {
  users: number;
  active_users: number;
  reports: number;
  published: number;
  templates: number;
  categories: number;
  connections: number;
  connections_ok: number;
  ai_models: number;
  ai_models_active: number;
  /** Configuration problems to fix, e.g. a default JWT secret. */
  warnings: string[];
}

export const adminApi = {
  usage: () => api.get<Usage>("/api/admin/usage").then((r) => r.data),
};
