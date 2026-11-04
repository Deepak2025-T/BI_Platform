"""
Automatic report refresh.

A report can refresh every 15 minutes, hourly, every 6 hours, daily at a time, or weekly on a day
at a time (server time). A refresh runs the report's saved queries against its database, with no
AI, and saves the results as a snapshot. Viewers then see the latest snapshot, so everyone sees
the same numbers and opening a report doesn't query the database each time.

The scheduler is a thread inside the API process that checks for due reports every
CHECK_SECONDS. Each due report is claimed with a conditional UPDATE first, so two API processes
never refresh the same report twice.
"""

import datetime as dt
import logging
import threading

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from .database import SessionLocal
from .datasources import get_source
from .history import summarize, thin
from .models import Report, ReportSnapshot
from .query_engine import run_query
from .report_data import query_widgets, run_widgets
from .schemas import QueryParams

log = logging.getLogger("uvicorn.error")

INTERVALS = {"15min": dt.timedelta(minutes=15), "hourly": dt.timedelta(hours=1), "6hours": dt.timedelta(hours=6)}
SCHEDULES = ("off", *INTERVALS, "daily", "weekly")
CHECK_SECONDS = 30
MANUAL_REFRESH_GAP = dt.timedelta(seconds=30)  # "Refresh now" more often than this reuses the last snapshot


class RefreshFailed(Exception):
    """The report's data couldn't be refreshed. The message is safe to show."""


def utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def as_utc(d: dt.datetime | None) -> dt.datetime | None:
    """SQLite returns datetimes without a time zone; they are stored in UTC."""
    return d.replace(tzinfo=dt.timezone.utc) if d is not None and d.tzinfo is None else d


def next_run(every: str, at: str, weekday: int, after: dt.datetime) -> dt.datetime | None:
    """The first run time strictly after `after`, in UTC. Daily and weekly times are server local time."""
    if every == "off":
        return None
    if every in INTERVALS:
        return after + INTERVALS[every]
    hour, minute = (int(p) for p in at.split(":"))
    local = after.astimezone()  # server time zone
    run = local.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if every == "daily":
        if run <= local:
            run += dt.timedelta(days=1)
    else:  # weekly
        run += dt.timedelta(days=(weekday - local.weekday()) % 7)
        if run <= local:
            run += dt.timedelta(days=7)
    return run.astimezone(dt.timezone.utc)


def latest_snapshot(db: Session, report_id: int) -> ReportSnapshot | None:
    return db.scalar(select(ReportSnapshot).where(ReportSnapshot.report_id == report_id)
                     .order_by(ReportSnapshot.id.desc()).limit(1))


def is_dashboard(report: Report) -> bool:
    return (report.config or {}).get("kind") == "dashboard"


def snapshot_matches(report: Report, snap: ReportSnapshot) -> bool:
    """False when the report's queries changed after the snapshot was taken (a chart added or edited)."""
    if is_dashboard(report):
        return snap.data.get("sql") == {w["id"]: w["sql"] for w in query_widgets(report.config)}
    return snap.data.get("params") == report.config.get("params")


def refresh_report(db: Session, report: Report, trigger: str) -> ReportSnapshot:
    """Runs the report's saved queries now (no AI) and saves the result as a snapshot.
    Raises RefreshFailed; the error is also recorded on the report."""
    now = utcnow()
    try:
        if is_dashboard(report):
            source = get_source(db, report.config.get("source_id"))
            widgets = run_widgets(report.config, source, {}, refresh=True)
            failed = [w for w in widgets if not w["ok"]]
            if widgets and len(failed) == len(widgets):
                raise RefreshFailed(f"No chart could be refreshed: {failed[0]['error']}")
            data = {"widgets": widgets, "source": source.name,
                    "sql": {w["id"]: w["sql"] for w in query_widgets(report.config)}}
            error = f"{len(failed)} of {len(widgets)} charts failed: {failed[0]['error']}" if failed else ""
        else:
            params = report.config.get("params") or {}
            result = run_query(db, QueryParams(**params))
            data = {"result": result, "params": params}
            error = ""
    except RefreshFailed as err:
        _record(db, report.id, now, str(err))
        raise
    except Exception as err:  # database unreachable, connection removed, query failed ...
        message = str(err).strip().splitlines()[0][:300] if str(err).strip() else type(err).__name__
        _record(db, report.id, now, message)
        raise RefreshFailed(message) from err

    summary = summarize(report.config, data) if is_dashboard(report) else None
    snap = ReportSnapshot(report_id=report.id, created_at=now, trigger=trigger, data=data, summary=summary)
    db.add(snap)
    db.flush()
    thin(db, report, now)
    _record(db, report.id, now, error)
    db.refresh(report)
    return snap


def _record(db: Session, report_id: int, when: dt.datetime, error: str):
    """Saves the refresh outcome without changing the report's "updated" time."""
    db.execute(update(Report).where(Report.id == report_id)
               .values(last_refreshed_at=when, last_refresh_error=error[:500], updated_at=Report.updated_at))
    db.commit()


def run_due(now: dt.datetime | None = None) -> int:
    """Refreshes every report whose next refresh time has passed. Returns how many were refreshed."""
    now = now or utcnow()
    done = 0
    with SessionLocal() as db:
        due = db.execute(select(Report.id, Report.refresh_every, Report.refresh_at, Report.refresh_weekday,
                                Report.next_refresh_at)
                         .where(Report.refresh_every != "off", Report.next_refresh_at.is_not(None),
                                Report.next_refresh_at <= now)).all()
        for row in due:
            following = next_run(row.refresh_every, row.refresh_at, row.refresh_weekday, now)
            claimed = db.execute(update(Report)
                                 .where(Report.id == row.id, Report.next_refresh_at == row.next_refresh_at)
                                 .values(next_refresh_at=following, updated_at=Report.updated_at))
            db.commit()
            if claimed.rowcount != 1:
                continue  # another process took it
            report = db.get(Report, row.id)
            try:
                refresh_report(db, report, "schedule")
                done += 1
            except RefreshFailed as err:
                log.warning("Scheduled refresh of report %s failed: %s", row.id, err)
    return done


class Scheduler:
    """Background thread that runs run_due every CHECK_SECONDS until stopped."""

    def __init__(self):
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self):
        if self._thread is None:
            self._thread = threading.Thread(target=self._loop, name="report-refresh", daemon=True)
            self._thread.start()

    def stop(self):
        self._stop.set()

    def _loop(self):
        while not self._stop.wait(CHECK_SECONDS):
            try:
                run_due()
            except Exception:  # keep the scheduler alive whatever one round does
                log.exception("Report refresh round failed")


scheduler = Scheduler()
