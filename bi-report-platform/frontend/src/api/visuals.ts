import { api } from "./client";
import type { QueryData, VisualFields, VisualSpec, VisualTable } from "./types";

/** The visual builder: browse a connection's shared tables, then build a chart from its columns. */
export const visualsApi = {
  tables: (sourceId: number | null) =>
    api.get<VisualTable[]>("/api/visuals/tables", { params: { source_id: sourceId }, timeout: 60000 }).then((r) => r.data),

  fields: (sourceId: number | null, table: string) =>
    api.get<VisualFields>("/api/visuals/fields", { params: { source_id: sourceId, table }, timeout: 60000 }).then((r) => r.data),

  /** The values one column holds, for a filter's list. */
  values: (sourceId: number | null, table: string, column: string, limit = 200) =>
    api.get<{ table: string; column: string; values: string[] }>("/api/visuals/values",
      { params: { source_id: sourceId, table, column, limit }, timeout: 60000 }).then((r) => r.data),

  /**
   * The SQL the chart would run, without running it.
   *
   * inline writes the filter values into the SQL. Use it when saving: the dashboard runs a saved
   * chart's SQL on its own and has no way to carry separate values with it.
   */
  compile: (sourceId: number | null, spec: VisualSpec, inline = false) =>
    api.post<{ sql: string; parameters: number }>("/api/visuals/compile",
      { source_id: sourceId, spec, inline }).then((r) => r.data),

  /** Builds the SQL and runs it, for the preview. */
  run: (sourceId: number | null, spec: VisualSpec, refresh = false) =>
    api.post<QueryData>("/api/visuals/run", { source_id: sourceId, spec, refresh }, { timeout: 120000 }).then((r) => r.data),
};
