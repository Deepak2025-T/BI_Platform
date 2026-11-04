from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, joinedload

from ..database import get_db
from ..deps import get_current_user
from ..models import Report, ReportCategory, User
from ..refresh import as_utc
from ..schemas import CategoryRef, PublishIn, ReportIn, ReportOut, ReportUpdate

router = APIRouter(prefix="/api/reports", tags=["reports"])


def to_out(r: Report) -> ReportOut:
    return ReportOut(id=r.id, title=r.title, prompt=r.prompt, status=r.status, config=r.config,
                     owner_id=r.owner_id, owner_name=r.owner.full_name,
                     category=CategoryRef.model_validate(r.category) if r.category else None,
                     created_at=r.created_at, updated_at=r.updated_at,
                     refresh_every=r.refresh_every, refresh_at=r.refresh_at, refresh_weekday=r.refresh_weekday,
                     next_refresh_at=as_utc(r.next_refresh_at), last_refreshed_at=as_utc(r.last_refreshed_at),
                     last_refresh_error=r.last_refresh_error, history_days=r.history_days)


def get_visible(db: Session, report_id: int, user: User) -> Report:
    r = db.get(Report, report_id, options=[joinedload(Report.owner), joinedload(Report.category)])
    if r is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Report not found")
    if user.role != "manager" and r.owner_id != user.id and r.status != "published":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Report not found")
    return r


def set_category(db: Session, r: Report, category_id: int | None):
    if category_id is not None and db.get(ReportCategory, category_id) is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "That category no longer exists. Pick another one.")
    r.category_id = category_id


def check_can_edit(r: Report, user: User):
    if user.role != "manager" and r.owner_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the owner or a manager can change this report")


@router.get("", response_model=list[ReportOut])
def list_reports(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    stmt = select(Report).options(joinedload(Report.owner), joinedload(Report.category)).order_by(Report.updated_at.desc())
    if user.role != "manager":
        # Users see their own reports plus everything published.
        stmt = stmt.where(or_(Report.owner_id == user.id, Report.status == "published"))
    return [to_out(r) for r in db.scalars(stmt).all()]


@router.post("", response_model=ReportOut, status_code=201)
def create_report(body: ReportIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    r = Report(title=body.title, prompt=body.prompt, config=body.config, owner_id=user.id)
    db.add(r)
    db.commit()
    return to_out(get_visible(db, r.id, user))


@router.get("/{report_id}", response_model=ReportOut)
def get_report(report_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return to_out(get_visible(db, report_id, user))


@router.put("/{report_id}", response_model=ReportOut)
def update_report(report_id: int, body: ReportUpdate, db: Session = Depends(get_db),
                  user: User = Depends(get_current_user)):
    r = get_visible(db, report_id, user)
    check_can_edit(r, user)
    if body.title is not None:
        r.title = body.title
    if body.config is not None:
        r.config = body.config
    if "category_id" in body.model_fields_set:
        set_category(db, r, body.category_id)
    db.commit()
    db.expire(r, ["category"])
    return to_out(get_visible(db, report_id, user))


@router.post("/{report_id}/publish", response_model=ReportOut)
def publish_report(report_id: int, body: PublishIn | None = None, db: Session = Depends(get_db),
                   user: User = Depends(get_current_user)):
    r = get_visible(db, report_id, user)
    check_can_edit(r, user)
    if body is not None and "category_id" in body.model_fields_set:
        set_category(db, r, body.category_id)
    r.status = "published"
    db.commit()
    db.expire(r, ["category"])
    return to_out(get_visible(db, report_id, user))


@router.delete("/{report_id}", status_code=204)
def delete_report(report_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    r = get_visible(db, report_id, user)
    check_can_edit(r, user)
    db.delete(r)
    db.commit()
