import { useEffect, useState } from "react";
import { errorMessage } from "../api/client";
import { queryApi, reportsApi } from "../api/endpoints";
import type { QueryParams, QueryResult, Report } from "../api/types";

/** Loads a report, then runs its saved query with the given parameters. */
export function useReport(id: number) {
  const [report, setReport] = useState<Report | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    reportsApi.get(id).then(setReport).catch((e) => setError(errorMessage(e)));
  }, [id]);
  return { report, setReport, error };
}

export function useQueryResult(params: QueryParams | undefined) {
  const [result, setResult] = useState<QueryResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const key = params ? JSON.stringify(params) : "";
  useEffect(() => {
    if (!params) return;
    let alive = true;
    setLoading(true);
    queryApi
      .run(params)
      .then((r) => alive && (setResult(r), setError("")))
      .catch((e) => alive && setError(errorMessage(e)))
      .finally(() => alive && setLoading(false));
    return () => { alive = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);
  return { result, loading, error };
}
