"""Runs a dashboard's charts. Shared by the viewer, Excel export and scheduled refreshes."""

from . import dashboard_filters
from .datasources import DataSource, QueryFailed, run_sql
from .sql_guard import UnsafeSQL


def is_chart(w: dict) -> bool:
    """Charts run a query; text tiles (headings and notes between charts) don't."""
    return w.get("kind", "chart") != "text"


def query_widgets(config: dict) -> list[dict]:
    return [w for w in config.get("widgets", []) if is_chart(w)]


def active_filters(config: dict, values: dict) -> list[dict]:
    """The dashboard filters that have a value set."""
    return [f for f in config.get("filters") or []
            if isinstance(f, dict) and f.get("id") and dashboard_filters.is_active(f, values.get(f["id"]))]


def run_widgets(config: dict, source: DataSource, values: dict, refresh: bool = False) -> list[dict]:
    """Runs every chart's saved SQL with the filter values applied. A chart that fails gets an error
    entry instead of stopping the others. refresh skips the result cache."""
    filters = [f for f in config.get("filters") or [] if isinstance(f, dict) and f.get("id")]
    out = []
    for w in query_widgets(config):
        sql, params, applied, skipped = dashboard_filters.apply(w["sql"], source, filters, values, w["id"])
        try:
            out.append({"id": w["id"], "ok": True, **run_sql(source, sql, params, refresh=refresh),
                        "filtered": applied, "not_filtered": skipped})
        except (UnsafeSQL, QueryFailed) as err:
            out.append({"id": w["id"], "ok": False, "error": str(err), "filtered": applied, "not_filtered": skipped})
    return out
