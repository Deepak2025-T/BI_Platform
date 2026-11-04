import { api } from "./client";
import type { HistoryPoint } from "../lib/history";
import type { Cell, QueryResult, RefreshEvery, Report, WidgetData } from "./types";

/** The data saved by one refresh. Dashboards: widgets; classic reports: the query result. */
export interface Snapshot {
  id: number;
  created_at: string;
  trigger: "schedule" | "manual";
  data: { widgets?: WidgetData[]; result?: QueryResult; params?: unknown };
}

export interface RefreshResponse {
  report: Report;
  snapshot: Snapshot | null;
  /** Set when the schedule was saved but the first refresh failed. */
  error: string;
}

export const scheduleApi = {
  /** Owner or manager. Turning it on refreshes once straight away. */
  set: (id: number, body: { every: RefreshEvery; at: string; weekday: number; history_days?: number }) =>
    api.put<RefreshResponse>(`/api/reports/${id}/schedule`, body, { timeout: 120000 }).then((r) => r.data),
  /** Runs the report's queries now and saves the result for everyone. */
  refresh: (id: number) => api.post<RefreshResponse>(`/api/reports/${id}/refresh`, null, { timeout: 120000 }).then((r) => r.data),
  /** The latest saved data, or null if never refreshed. */
  snapshot: (id: number) => api.get<Snapshot | null>(`/api/reports/${id}/snapshot`).then((r) => r.data),
  /** Dashboards: each chart's numbers at every kept refresh, oldest first. */
  history: (id: number) =>
    api.get<{ history_days: number; widgets: Record<string, HistoryPoint[]> }>(`/api/reports/${id}/history`).then((r) => r.data),
  /** Dashboards: the charts' results at an earlier refresh (the previous one when `at` is left out), or null. */
  compare: (id: number, at?: string) =>
    api.get<{ taken_at: string; widgets: { id: string; columns: string[]; rows: Cell[][] }[] } | null>(
      `/api/reports/${id}/history/compare`, { params: at ? { at } : {} }).then((r) => r.data),
};
