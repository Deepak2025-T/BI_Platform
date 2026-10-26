import { api } from "./client";
import type { ChatAttempt, DashboardFilter, QueryData, Report, Widget } from "./types";

/** Columns a chart's query reads, to choose a filter column by hand. */
export type FilterColumns = Record<string, { table: string; columns: { name: string; type: string }[] }[]>;

/** Editing tools for reports. AI calls can be slow, so they get a few minutes. */
export const reportToolsApi = {
  /** Copies a report into a new draft of your own. */
  duplicate: (id: number, title?: string) =>
    api.post<Report>(`/api/reports/${id}/duplicate`, title ? { title } : {}).then((r) => r.data),
  /** Runs SQL for one chart to try it. Nothing is saved. */
  previewSql: (id: number, sql: string) =>
    api.post<QueryData>(`/api/reports/${id}/preview-sql`, { sql }, { timeout: 60000 }).then((r) => r.data),
  /** Asks the AI model to change one chart. Nothing is saved. */
  reviseWidget: (id: number, body: { model_id: number; widget: Widget; instruction: string }) =>
    api.post<{ widget: Widget; data: QueryData; attempts: ChatAttempt[] }>(`/api/reports/${id}/widgets/revise`, body, { timeout: 240000 })
      .then((r) => r.data),
  filterColumns: (id: number, widgets: Widget[]) =>
    api.post<FilterColumns>(`/api/reports/${id}/filters/columns`, { widgets }, { timeout: 60000 }).then((r) => r.data),
  /** Builds a filter from columns chosen by hand. Nothing is saved. */
  manualFilter: (id: number, body: { label: string; kind: DashboardFilter["kind"]; widgets: Widget[];
                                     columns: Record<string, { table: string; column: string }>; id?: string }) =>
    api.post<DashboardFilter>(`/api/reports/${id}/filters/manual`, body, { timeout: 60000 }).then((r) => r.data),
};
