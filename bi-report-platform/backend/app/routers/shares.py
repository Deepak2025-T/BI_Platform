"""Links that open one report without signing in, and the pages those links serve.

A share link is the whole of the secret: anyone holding it sees the report. So it is made on
purpose by the report's owner or a manager, never as a side effect of publishing; it only exists
for a published report, so making a link is never the step that makes a draft visible; and it can
be taken back at any moment.

What a link serves is a picture of the numbers, not a way into the database behind them. The
public endpoints hand back the layout with every query, connection id and field spec removed, a
chart that fails says only that it failed, and no public request can make the server re-run
anything: it reads the cache or the latest saved refresh.
"""

import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..datasources import SourceError, get_source
from ..deps import get_current_user
from ..models import Report, ReportShare, User, now_utc
from ..refresh import as_utc, keep_results, saved_data, snapshot_body
from ..report_data import active_filters, run_widgets
from ..schemas import DashboardDataIn, PublicReportOut, ShareIn, ShareOut
from .reports import check_can_edit, get_visible

router = APIRouter(tags=["shares"])

# Where a share link opens in the browser. The frontend route matches this.
SHARE_PATH = "/shared/{token}"

# What never leaves the building: the query a chart runs, the queries it might have run instead,
# the fields it was built from, and the field list a summary table was resolved against.
PRIVATE_WIDGET_KEYS = ("sql", "alt_sql", "alt_x", "alt_legend", "pick_fields", "visual", "rollup")


def _out(share: ReportShare) -> ShareOut:
    return ShareOut(token=share.token, path=SHARE_PATH.format(token=share.token),
                    created_at=as_utc(share.created_at), expires_at=as_utc(share.expires_at),
                    views=share.views, last_viewed_at=as_utc(share.last_viewed_at))


def _live(db: Session, report_id: int) -> ReportShare | None:
    """The report's working link, if it has one: not revoked, not past its date."""
    now = datetime.now(timezone.utc)
    for share in db.scalars(select(ReportShare).where(ReportShare.report_id == report_id)
                            .order_by(ReportShare.created_at.desc())).all():
        expires = as_utc(share.expires_at)
        if share.revoked_at is None and (expires is None or expires > now):
            return share
    return None


def public_config(config: dict) -> dict:
    """The report's layout with everything that is about the database taken out.

    What is left is what the page draws: titles, chart types, columns, colours, sizes and filters.
    The connection is dropped rather than kept, because a name like "Finance production" is itself
    worth keeping off a page anyone may open."""
    widgets = [{k: v for k, v in w.items() if k not in PRIVATE_WIDGET_KEYS}
               for w in (config.get("widgets") or []) if isinstance(w, dict)]
    kept = {k: v for k, v in config.items() if k not in ("widgets", "source_id", "source_name")}
    return {**kept, "source_id": None, "source_name": "", "widgets": widgets}


def _shared_report(db: Session, token: str) -> tuple[ReportShare, Report]:
    """The report one token opens. A link that was never made, has been taken back, has run out,
    or whose report has gone back to a draft all answer the same way: there is nothing here."""
    share = db.scalar(select(ReportShare).where(ReportShare.token == token))
    gone = HTTPException(status.HTTP_404_NOT_FOUND, "This link doesn't open anything. It may have been turned off.")
    if share is None or share.revoked_at is not None:
        raise gone
    expires = as_utc(share.expires_at)
    if expires is not None and expires <= datetime.now(timezone.utc):
        raise gone
    report = db.get(Report, share.report_id)
    if report is None or report.status != "published":
        raise gone
    return share, report


@router.get("/api/reports/{report_id}/share", response_model=ShareOut | None)
def get_share(report_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """The report's share link, or null when it has none."""
    report = get_visible(db, report_id, user)
    check_can_edit(report, user)
    share = _live(db, report.id)
    return _out(share) if share else None


@router.post("/api/reports/{report_id}/share", response_model=ShareOut, status_code=201)
def create_share(report_id: int, body: ShareIn | None = None, db: Session = Depends(get_db),
                 user: User = Depends(get_current_user)):
    """Makes a link that opens this report without signing in, or hands back the one it has.

    Asking twice gives the same link back rather than a second one, so an address someone has
    already pasted into a page keeps working."""
    report = get_visible(db, report_id, user)
    check_can_edit(report, user)
    if report.status != "published":
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            "Publish this report before sharing a link to it. A link opens the report for anyone "
                            "who has it, so it can't be the thing that makes a draft public.")
    existing = _live(db, report.id)
    if existing is not None:
        return _out(existing)
    body = body or ShareIn()
    share = ReportShare(
        report_id=report.id, token=secrets.token_urlsafe(32), created_by=user.id,
        expires_at=now_utc() + timedelta(days=body.expires_days) if body.expires_days else None)
    db.add(share)
    db.commit()
    db.refresh(share)
    return _out(share)


@router.delete("/api/reports/{report_id}/share", status_code=204)
def revoke_share(report_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Turns off every live link to this report. Anything embedding it stops showing the data."""
    report = get_visible(db, report_id, user)
    check_can_edit(report, user)
    for share in db.scalars(select(ReportShare).where(ReportShare.report_id == report.id)).all():
        if share.revoked_at is None:
            share.revoked_at = now_utc()
    db.commit()


@router.get("/api/public/reports/{token}", response_model=PublicReportOut)
def public_report(token: str, db: Session = Depends(get_db)):
    """A shared report's layout. No sign-in, and nothing about the database it came from."""
    share, report = _shared_report(db, token)
    share.views += 1
    share.last_viewed_at = now_utc()
    db.commit()
    return PublicReportOut(title=report.title, status=report.status, updated_at=as_utc(report.updated_at),
                           config=public_config(report.config or {}))


@router.post("/api/public/reports/{token}/data")
def public_data(token: str, body: DashboardDataIn | None = None, db: Session = Depends(get_db)):
    """The numbers behind a shared report, with its filters applied.

    A public caller can never ask for a refresh: the report's saved numbers are served where there
    are any, and otherwise the queries run through the ordinary cache and what they produce is
    saved for the next visitor. An open link is not a way to put load on the database behind it."""
    _, report = _shared_report(db, token)
    config = report.config or {}
    if config.get("kind") != "dashboard":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "This report isn't a dashboard")
    body = body or DashboardDataIn()
    values = {k: v.model_dump() for k, v in body.filters.items()}
    filtered = active_filters(config, values)
    if not filtered:
        snap = saved_data(db, report)
        if snap is not None:
            # The connection's name is the owner's business, not the visitor's, so it is dropped
            # here as it is below.
            return {**snapshot_body(snap), "source": ""}
    try:
        source = get_source(db, config.get("source_id"))
    except SourceError as err:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(err))
    widgets = run_widgets(config, source, values, refresh=False)
    if not filtered:
        keep_results(db, report, widgets, source.name)   # for the next visitor; these are live
    # A failed query can name tables and columns in its message, which is the one thing a public
    # page must not hand out. Whoever can open the report itself still sees the real reason.
    safe = [w if w.get("ok") else {**w, "error": "This chart couldn't be shown."} for w in widgets]
    return {"source": "", "snapshot_at": None, "widgets": safe}
