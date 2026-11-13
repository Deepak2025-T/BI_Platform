import { useEffect, useState } from "react";
import { useParams, useSearchParams } from "react-router-dom";
import { errorMessage } from "../api/client";
import { publicApi } from "../api/endpoints";
import type { DashboardConfig, PublicReport, Report } from "../api/types";
import { isDashboard } from "../api/types";
import Dashboard from "../components/Dashboard";

/**
 * A report opened by its share link.
 *
 * This is the one page in the app that never asks who you are: the token in the address is the
 * whole of the permission, so the page sits outside the signed-in shell and talks only to the
 * public endpoints. Everything it shows came back with the queries, the connection and the field
 * specs already stripped off by the server.
 *
 * `?embed=1` leaves off the header, for a link pasted into an iframe on someone else's page.
 */
export default function SharedReport() {
  const token = useParams().token ?? "";
  const [params] = useSearchParams();
  const bare = params.get("embed") === "1";
  const [shared, setShared] = useState<PublicReport | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    publicApi.report(token).then(setShared).catch((e) => setError(errorMessage(e)));
  }, [token]);

  if (error) {
    return (
      <div className="page narrow">
        <div className="alert alert-error">{error}</div>
        <p className="muted small">
          Links can be turned off or given an end date by whoever shared them. Ask them for a new one.
        </p>
      </div>
    );
  }
  if (!shared) return <div className="page">Opening the report…</div>;
  if (!isDashboard(shared.config)) {
    return (
      <div className="page narrow">
        <div className="alert alert-warn">Only dashboards can be opened by a link. This report is a different kind.</div>
      </div>
    );
  }

  // Dashboard draws a Report; a link carries only the handful of fields it actually shows, so the
  // rest stand at their "nothing here" values rather than being invented.
  const stand: Report & { config: DashboardConfig } = {
    id: 0,
    title: shared.title,
    prompt: "",
    status: shared.status,
    config: shared.config,
    owner_id: 0,
    owner_name: "",
    category: null,
    created_at: shared.updated_at,
    updated_at: shared.updated_at,
    refresh_every: "off",
    refresh_at: "08:00",
    refresh_weekday: 0,
    next_refresh_at: null,
    last_refreshed_at: null,
    last_refresh_error: "",
    history_days: 0,
  };

  return <Dashboard key={token} report={stand} editable={false} canEdit={false} shareToken={token} bare={bare} />;
}
