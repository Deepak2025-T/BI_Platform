"""
Report history: what a dashboard showed at each refresh, kept for the report's history_days.

Every refresh saves a snapshot (see refresh.py). Besides the full results, a snapshot keeps a small
summary per chart, so a trend over hundreds of snapshots reads only a few numbers:

    {"sql": {chart id: sql}, "widgets": {chart id: {"value": 20} | {"values": {"Open": 20, "Closed": 11}}}}

Tables have no summary; "what changed" compares their rows with one past snapshot instead. A chart's
points only count while its SQL is the same as now, so editing a query starts its history afresh.

Thinning keeps storage small: every snapshot of the last day, one per hour for the last week, then
one per day, up to history_days (0 keeps only the newest KEEP_SNAPSHOTS, as before history existed).
"""

import datetime as dt

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Report, ReportSnapshot
from .report_data import query_widgets

KEEP_SNAPSHOTS = 10  # always kept, whatever their age
HISTORY_CHOICES = (0, 30, 90, 365)
MAX_CATEGORIES = 30
CATEGORY_CHARTS = ("bar", "line", "area", "pie")


def _number(v):
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def widget_summary(widget: dict, result: dict) -> dict | None:
    """{"value": n} for a single number, {"values": {category: n}} for a category chart, None otherwise."""
    if not result.get("ok", True) or not result.get("columns"):
        return None
    columns, rows = result["columns"], result.get("rows") or []
    chart = widget.get("chart") or {}
    ys = [c for c in chart.get("y") or [] if c in columns]
    if chart.get("type") == "kpi" or (len(rows) == 1 and not chart.get("x")):
        if not rows:
            return None
        col = ys[0] if ys else next((c for i, c in enumerate(columns) if _number(rows[0][i]) is not None), None)
        return {"value": _number(rows[0][columns.index(col)])} if col else None
    if chart.get("type") in CATEGORY_CHARTS and chart.get("x") in columns and ys:
        xi, yi = columns.index(chart["x"]), columns.index(ys[0])
        values = {}
        for row in rows[:MAX_CATEGORIES]:
            if _number(row[yi]) is not None:
                values[str(row[xi]) if row[xi] is not None else "(blank)"] = row[yi]
        return {"values": values}
    return None


def summarize(config: dict, data: dict) -> dict:
    """The summary stored with a dashboard snapshot."""
    widgets = {w["id"]: w for w in query_widgets(config)}
    out = {}
    for result in data.get("widgets") or []:
        w = widgets.get(result.get("id"))
        s = widget_summary(w, result) if w else None
        if s is not None:
            out[result["id"]] = s
    return {"sql": data.get("sql") or {}, "widgets": out}


def thin(db: Session, report: Report, now: dt.datetime):
    """Deletes snapshots the report no longer needs (see the module docstring)."""
    rows = db.execute(select(ReportSnapshot.id, ReportSnapshot.created_at)
                      .where(ReportSnapshot.report_id == report.id).order_by(ReportSnapshot.id.desc())).all()
    keep_days = report.history_days or 0
    seen_hours, seen_days, drop = set(), set(), []
    for i, (sid, created) in enumerate(rows):
        if i < KEEP_SNAPSHOTS:
            continue
        created = created if created.tzinfo else created.replace(tzinfo=dt.timezone.utc)
        age = now - created
        if keep_days == 0 or age > dt.timedelta(days=keep_days):
            drop.append(sid)
        elif age <= dt.timedelta(days=1):
            continue
        else:  # the newest snapshot of each hour (last week) or day (older) stays
            bucket = created.astimezone().strftime("%Y-%m-%d %H" if age <= dt.timedelta(days=7) else "%Y-%m-%d")
            seen = seen_hours if age <= dt.timedelta(days=7) else seen_days
            if bucket in seen:
                drop.append(sid)
            seen.add(bucket)
    if drop:
        db.query(ReportSnapshot).filter(ReportSnapshot.id.in_(drop)).delete(synchronize_session=False)


def _summary(db: Session, report: Report, snap_id: int, created, summary: dict | None) -> dict:
    """The stored summary, worked out (and stored) for snapshots saved before summaries existed."""
    if summary is not None:
        return summary
    snap = db.get(ReportSnapshot, snap_id)
    snap.summary = summarize(report.config, snap.data)
    return snap.summary


def series(db: Session, report: Report) -> dict:
    """Each chart's points, oldest first: {chart id: [{"t", "value"} | {"t", "values"}]}."""
    current = {w["id"]: w.get("sql") for w in query_widgets(report.config)}
    rows = db.execute(select(ReportSnapshot.id, ReportSnapshot.created_at, ReportSnapshot.summary)
                      .where(ReportSnapshot.report_id == report.id).order_by(ReportSnapshot.created_at)).all()
    out: dict[str, list] = {wid: [] for wid in current}
    for sid, created, summary in rows:
        summary = _summary(db, report, sid, created, summary)
        t = _iso(created)
        for wid, s in (summary.get("widgets") or {}).items():
            if wid in out and (summary.get("sql") or {}).get(wid) == current[wid]:
                out[wid].append({"t": t, **s})
    db.commit()  # summaries worked out for older snapshots
    return {wid: points for wid, points in out.items() if points}


def snapshot_at(db: Session, report: Report, at: dt.datetime | None) -> ReportSnapshot | None:
    """at=None: the snapshot before the newest one. Otherwise the newest snapshot at or before `at`,
    or the oldest one after it when history doesn't go back that far."""
    base = select(ReportSnapshot).where(ReportSnapshot.report_id == report.id)
    if at is None:
        return db.scalar(base.order_by(ReportSnapshot.created_at.desc()).offset(1).limit(1))
    before = db.scalar(base.where(ReportSnapshot.created_at <= at).order_by(ReportSnapshot.created_at.desc()).limit(1))
    return before or db.scalar(base.order_by(ReportSnapshot.created_at).limit(1))


def comparable(report: Report, snap: ReportSnapshot) -> list[dict]:
    """The snapshot's chart results whose SQL is still the chart's SQL now."""
    current = {w["id"]: w.get("sql") for w in query_widgets(report.config)}
    sql = snap.data.get("sql") or {}
    return [{"id": w["id"], "ok": w.get("ok", True), "columns": w.get("columns", []), "rows": w.get("rows", [])}
            for w in snap.data.get("widgets") or []
            if w.get("id") in current and sql.get(w["id"]) == current[w["id"]] and w.get("ok", True)]


def _iso(d: dt.datetime) -> str:
    d = d if d.tzinfo else d.replace(tzinfo=dt.timezone.utc)
    return d.isoformat(timespec="seconds")
