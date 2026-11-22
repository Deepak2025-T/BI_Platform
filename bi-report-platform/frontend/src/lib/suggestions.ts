import { useCallback, useEffect, useRef, useState } from "react";
import { errorMessage } from "../api/client";
import { assistantApi } from "../api/endpoints";
import type { SuggestionRequest, SuggestionResult } from "../api/types";

/**
 * Suggestions are fetched once per place: one chat answer, one report, one empty chat on one
 * database. What came back is kept here for the visit, so re-rendering, reopening a chat or
 * coming back to a report never asks again, and a request already on its way is shared rather
 * than sent twice (React's development double effects included).
 */
const cache = new Map<string, SuggestionResult>();
const inflight = new Map<string, Promise<SuggestionResult>>();
const dismissed = new Set<string>();

export interface SuggestionsState {
  data: SuggestionResult | null;
  loading: boolean;
  error: string;
  dismissed: boolean;
  /** Asks again for different ones; the ones on screen are sent as already shown. */
  refresh: () => void;
  dismiss: () => void;
}

/**
 * `key` names the place (null waits, e.g. until a database is chosen). `build` makes the request
 * and is only called when one is actually sent; `shown` is what is on screen now, so a refresh
 * can ask for something new.
 */
export function useSuggestions(key: string | null, build: (shown: string[]) => SuggestionRequest): SuggestionsState {
  const [data, setData] = useState<SuggestionResult | null>(() => (key && cache.get(key)) || null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [hidden, setHidden] = useState(() => !!key && dismissed.has(key));
  const [nonce, setNonce] = useState(0);
  const buildRef = useRef(build);
  buildRef.current = build;
  const dataRef = useRef(data);
  dataRef.current = data;
  // The key the last run was for, so a refresh is told apart from moving to another place.
  const lastKey = useRef<string | null>(null);

  useEffect(() => {
    const refreshing = nonce > 0 && lastKey.current === key;
    lastKey.current = key;
    setHidden(!!key && dismissed.has(key));
    if (!key) { setData(null); return; }
    const cached = cache.get(key);
    if (cached && !refreshing) { setData(cached); setError(""); setLoading(false); return; }
    // Another place: the old place's chips must not stay on screen while the new ones load.
    if (!refreshing) setData(null);
    let live = true;
    setLoading(true);
    setError("");
    let request = refreshing ? undefined : inflight.get(key);
    if (!request) {
      const shown = refreshing ? (dataRef.current?.suggestions ?? []).map((s) => s.text) : [];
      const body = buildRef.current(shown);
      request = assistantApi.suggestions(refreshing ? { ...body, refresh: true,
        previous: [...(body.previous ?? []), ...shown] } : body);
      inflight.set(key, request);
      request.finally(() => { if (inflight.get(key) === request) inflight.delete(key); }).catch(() => {});
    }
    request.then((res) => {
      cache.set(key, res);
      if (live) setData(res);
    }).catch((err) => {
      if (live) setError(errorMessage(err, "Suggestions couldn't be loaded."));
    }).finally(() => { if (live) setLoading(false); });
    return () => { live = false; };
  }, [key, nonce]);

  const refresh = useCallback(() => { setNonce((n) => n + 1); }, []);
  const dismiss = useCallback(() => { if (key) dismissed.add(key); setHidden(true); }, [key]);
  return { data, loading, error, dismissed: hidden, refresh, dismiss };
}

/** Every suggestion shown so far under any of these keys: none of them is suggested again. */
export function shownUnder(keys: string[]): string[] {
  return keys.flatMap((k) => (cache.get(k)?.suggestions ?? []).map((s) => s.text));
}

/** The result of a chat answer as a CSV file, built in the browser from the rows already here. */
export function downloadCsv(name: string, columns: string[], rows: (string | number | boolean | null)[][]) {
  const cell = (v: unknown) => {
    const s = v === null || v === undefined ? "" : String(v);
    return /[",\n\r]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  const text = [columns, ...rows].map((r) => r.map(cell).join(",")).join("\r\n");
  const url = URL.createObjectURL(new Blob(["\ufeff" + text], { type: "text/csv;charset=utf-8" }));
  const a = document.createElement("a");
  a.href = url;
  a.download = `${name.replace(/[\\/:*?"<>|]+/g, " ").trim().slice(0, 80) || "results"}.csv`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
