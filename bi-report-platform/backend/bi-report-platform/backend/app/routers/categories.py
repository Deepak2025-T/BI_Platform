from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import Report, ReportCategory, User
from ..schemas import CategoryIn, CategoryOut, CategoryUpdate

router = APIRouter(prefix="/api/categories", tags=["categories"])


def can_edit(c: ReportCategory, user: User) -> bool:
    return user.role == "manager" or c.created_by == user.id


def visible_reports(user: User):
    """Reports this person can see: their own and published ones (managers see all)."""
    if user.role == "manager":
        return Report.id.is_not(None)
    return or_(Report.owner_id == user.id, Report.status == "published")


def to_out(c: ReportCategory, count: int, user: User) -> CategoryOut:
    return CategoryOut(id=c.id, name=c.name, description=c.description, color=c.color,
                       report_count=count, can_edit=can_edit(c, user))


def report_count(db: Session, category_id: int, user: User) -> int:
    return db.scalar(select(func.count(Report.id))
                     .where(Report.category_id == category_id, visible_reports(user))) or 0


def get_category(db: Session, category_id: int) -> ReportCategory:
    c = db.get(ReportCategory, category_id)
    if c is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Category not found")
    return c


def check_name_free(db: Session, name: str, except_id: int | None = None):
    stmt = select(ReportCategory.id).where(func.lower(ReportCategory.name) == name.lower())
    if except_id is not None:
        stmt = stmt.where(ReportCategory.id != except_id)
    if db.scalar(stmt) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, f'A category called "{name}" already exists')


@router.get("", response_model=list[CategoryOut])
def list_categories(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    counts = (select(Report.category_id, func.count(Report.id).label("n"))
              .where(visible_reports(user)).group_by(Report.category_id).subquery())
    rows = db.execute(select(ReportCategory, func.coalesce(counts.c.n, 0))
                      .outerjoin(counts, counts.c.category_id == ReportCategory.id)
                      .order_by(func.lower(ReportCategory.name))).all()
    return [to_out(c, n, user) for c, n in rows]


@router.post("", response_model=CategoryOut, status_code=201)
def create_category(body: CategoryIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    name = body.name.strip()
    check_name_free(db, name)
    c = ReportCategory(name=name, description=body.description.strip(), color=body.color.upper(), created_by=user.id)
    db.add(c)
    db.commit()
    return to_out(c, 0, user)


@router.put("/{category_id}", response_model=CategoryOut)
def update_category(category_id: int, body: CategoryUpdate, db: Session = Depends(get_db),
                    user: User = Depends(get_current_user)):
    c = get_category(db, category_id)
    if not can_edit(c, user):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the person who made this category or a manager can change it")
    if body.name is not None:
        check_name_free(db, body.name.strip(), except_id=c.id)
        c.name = body.name.strip()
    if body.description is not None:
        c.description = body.description.strip()
    if body.color is not None:
        c.color = body.color.upper()
    db.commit()
    return to_out(c, report_count(db, c.id, user), user)


@router.delete("/{category_id}", status_code=204)
def delete_category(category_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    c = get_category(db, category_id)
    if not can_edit(c, user):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the person who made this category or a manager can delete it")
    # Reports in the category are kept and become uncategorised.
    db.execute(update(Report).where(Report.category_id == c.id).values(category_id=None))
    db.delete(c)
    db.commit()
