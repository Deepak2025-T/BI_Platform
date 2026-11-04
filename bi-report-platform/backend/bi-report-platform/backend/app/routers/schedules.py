from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .. import history
from ..database import get_db
from ..deps import get_current_user
from ..models import ReportSnapshot, User
from ..refresh import MANUAL_REFRESH_GAP, RefreshFailed, as_utc, latest_snapshot, next_run, refresh_report, utcnow
from ..schemas import ReportOut
from .reports import check_can_edit, get_visible, to_out

router = APIRouter(prefix="/api/reports", tags=["report refresh"])


class ScheduleIn(BaseModel):
    every: Literal["off", "15min", "hourly", "6hours", "daily", "weekly"]
    at: str = Field(default="08:00", pattern=r"^([01]\d|2[0-3]):[0-5]\d$")  # daily and weekly, server time
    weekday: int = Field(default=0, ge=0, le=6)  # weekly: 0 = Monday
    history_days: int | None = None  # one of history.HISTORY_CHOICES; None keeps the current setting


class SnapshotOut(BaseModel):
    id: int
    created_at: datetime
    trigger: str
    data: dict


class RefreshOut(BaseModel):
    report: ReportOut
    snapshot: SnapshotOut | None
    error: str = ""


def snapshot_out(s: ReportSnapshot | None) -> SnapshotOut | None:
    return SnapshotOut(id=s.id, created_at=as_utc(s.created_at), trigger=s.trigger, data=s.data) if s else None


@router.put("/{report_id}/schedule", response_model=RefreshOut)
def set_schedule(report_id: int, body: ScheduleIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Turns automatic refresh on or off. Turning it on refreshes once straight away, so viewers have data."""
    report = get_visible(db, report_id, user)
    check_can_edit(report, user)
    if body.history_days is not None:
        if body.history_days not in history.HISTORY_CHOICES:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Keep history for 0, 30, 90 or 365 days")
        report.history_days = body.history_days
    report.refresh_every, report.refresh_at, report.refresh_weekday = body.every, body.at, body.weekday
    report.next_refresh_at = next_run(body.every, body.at, body.weekday, utcnow())
    if body.every == "off":
        report.last_refresh_error = ""
    db.commit()
    snap, error = None, ""
    if body.every != "off":
        try:
            snap = refresh_report(db, report, "manual")
        except RefreshFailed as err:
            error = str(err)
    return RefreshOut(report=to_out(get_visible(db, report_id, user)), snapshot=snapshot_out(snap), error=error)


@router.post("/{report_id}/refresh", response_model=RefreshOut)
def refresh_now(report_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Runs the report's queries now and saves the result for everyone. Anyone who can see the report
    can do this; within a few seconds of the last refresh the existing snapshot is returned instead."""
    report = get_visible(db, report_id, user)
    last = as_utc(report.last_refreshed_at)
    snap = latest_snapshot(db, report_id)
    if snap and last and utcnow() - last < MANUAL_REFRESH_GAP and not report.last_refresh_error:
        return RefreshOut(report=to_out(report), snapshot=snapshot_out(snap))
    try:
        snap = refresh_report(db, report, "manual")
    except RefreshFailed as err:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"The report couldn't be refreshed: {err}")
    return RefreshOut(report=to_out(get_visible(db, report_id, user)), snapshot=snapshot_out(snap))


@router.get("/{report_id}/snapshot", response_model=SnapshotOut | None)
def get_snapshot(report_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """The data saved by the latest refresh, or null if the report has never been refreshed."""
    get_visible(db, report_id, user)
    return snapshot_out(latest_snapshot(db, report_id))


# ---------- History: trends and comparisons (dashboards) ----------

def _dashboard_report(db: Session, report_id: int, user: User):
    report = get_visible(db, report_id, user)
    if (report.config or {}).get("kind") != "dashboard":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "History is kept for dashboards.")
    return report


@router.get("/{report_id}/history")
def report_history(report_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Each chart's numbers at every kept refresh, oldest first, for trends and number-tile changes."""
    report = _dashboard_report(db, report_id, user)
    return {"history_days": report.history_days, "widgets": history.series(db, report)}


@router.get("/{report_id}/history/compare")
def report_compare(report_id: int, at: datetime | None = None, db: Session = Depends(get_db),
                   user: User = Depends(get_current_user)):
    """The charts' results at an earlier refresh: the one before the newest (no `at`), or the newest at or
    before `at` (the oldest kept, when history doesn't go back that far). Charts whose query changed since
    are left out. null when there is nothing to compare with."""
    report = _dashboard_report(db, report_id, user)
    if at is not None and at.tzinfo is None:
        at = at.replace(tzinfo=timezone.utc)
    snap = history.snapshot_at(db, report, at)
    latest = latest_snapshot(db, report_id)
    if snap is None or (latest is not None and snap.id == latest.id):
        return None
    return {"taken_at": as_utc(snap.created_at), "widgets": history.comparable(report, snap)}
