"""
Editing tools for reports: duplicate a report, try SQL for a chart, ask the AI to change a chart, and
set up a filter by choosing its columns by hand.
"""

import copy

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .. import dashboard_filters
from ..ai.assistant import revise_widget
from ..database import get_db
from ..datasources import QueryFailed, run_sql
from ..deps import get_current_user
from ..models import Report, User
from ..schemas import ReportOut
from ..sql_guard import UnsafeSQL
from .assistant import _ai_call, _dashboard, _model
from .reports import check_can_edit, get_visible, to_out

router = APIRouter(prefix="/api/reports", tags=["report editing"])


class DuplicateIn(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)


class SqlIn(BaseModel):
    sql: str = Field(min_length=1, max_length=8000)


class WidgetBody(BaseModel):
    id: str = Field(min_length=1, max_length=40)
    title: str = Field(default="", max_length=120)
    question: str = Field(default="", max_length=500)
    sql: str = Field(min_length=1, max_length=8000)
    chart: dict = Field(default_factory=dict)
    size: str | None = None


class ReviseIn(BaseModel):
    model_id: int
    widget: WidgetBody
    instruction: str = Field(min_length=2, max_length=500)


class FilterColumnsIn(BaseModel):
    widgets: list[WidgetBody] = Field(max_length=20)


class ManualFilterIn(BaseModel):
    label: str = Field(min_length=1, max_length=60)
    kind: str = Field(pattern="^(date|category)$")
    widgets: list[WidgetBody] = Field(max_length=20)
    # Chart id -> {"table", "column"}. Charts left out aren't filtered.
    columns: dict[str, dict] = Field(default_factory=dict)
    id: str | None = Field(default=None, max_length=40)


@router.post("/{report_id}/duplicate", response_model=ReportOut, status_code=201)
def duplicate_report(report_id: int, body: DuplicateIn | None = None, db: Session = Depends(get_db),
                     user: User = Depends(get_current_user)):
    """Copies a report you can see into a new draft of your own, to change freely. The copy has no
    category and no auto-refresh; it reads the same database and keeps every chart, filter and setting."""
    original = get_visible(db, report_id, user)
    title = (body.title if body and body.title else f"Copy of {original.title}")[:200]
    copy_ = Report(title=title.strip(), prompt=original.prompt, config=copy.deepcopy(original.config or {}),
                   owner_id=user.id)
    db.add(copy_)
    db.commit()
    return to_out(get_visible(db, copy_.id, user))


@router.post("/{report_id}/preview-sql")
def preview_sql(report_id: int, body: SqlIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Runs SQL for one chart of this dashboard, to try it before saving. Checked like every query:
    one SELECT on the tables shared from this database. Nothing is saved."""
    report, source = _dashboard(db, report_id, user)
    check_can_edit(report, user)
    try:
        return run_sql(source, body.sql, refresh=True)
    except (UnsafeSQL, QueryFailed) as err:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(err))


@router.post("/{report_id}/widgets/revise")
def revise_chart(report_id: int, body: ReviseIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Asks the AI model to change one chart. Returns the changed chart and its data; nothing is saved
    until the editor saves the report."""
    report, source = _dashboard(db, report_id, user)
    check_can_edit(report, user)
    _, spec = _model(db, body.model_id)
    return _ai_call(revise_widget, spec, source, body.widget.model_dump(exclude_none=True), body.instruction)


@router.post("/{report_id}/filters/columns")
def filter_columns(report_id: int, body: FilterColumnsIn, db: Session = Depends(get_db),
                   user: User = Depends(get_current_user)):
    """For each chart, the tables its query reads and their columns, to choose a filter's columns by hand."""
    report, source = _dashboard(db, report_id, user)
    check_can_edit(report, user)
    return dashboard_filters.filter_columns(source, [w.model_dump() for w in body.widgets])


@router.post("/{report_id}/filters/manual")
def manual_filter(report_id: int, body: ManualFilterIn, db: Session = Depends(get_db),
                  user: User = Depends(get_current_user)):
    """Builds a filter from columns chosen by hand. Each choice is checked against the tables that
    chart reads; nothing is saved until the editor saves the report."""
    report, source = _dashboard(db, report_id, user)
    check_can_edit(report, user)
    widgets = [w.model_dump() for w in body.widgets]
    return dashboard_filters.make_filter(source, body.label, body.kind, widgets, body.columns, body.id)
