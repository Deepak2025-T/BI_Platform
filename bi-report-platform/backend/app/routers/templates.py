import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, joinedload

from .. import dashboard_filters
from ..database import get_db
from ..datasources import QueryFailed, SourceError, get_source, run_sql
from ..openpages_templates import template_rows
from ..sql_guard import UnsafeSQL
from ..deps import get_current_user
from ..models import ReportTemplate, User
from ..schemas import TemplateIn, TemplateOut, TemplateUpdate
from ..template_data import BUILTIN_TEMPLATES, REPLACED_BUILTINS

router = APIRouter(prefix="/api/templates", tags=["templates"])


def builtin_fields(t: dict) -> dict:
    return {"layout": {}, **t, "visibility": "shared", "is_builtin": True}


def ensure_builtin_templates(db: Session):
    """Creates the built-in templates once (deleted ones are not brought back),
    and swaps retired built-ins for their replacements."""
    builtins = db.scalars(select(ReportTemplate).where(ReportTemplate.is_builtin.is_(True))).all()
    if not builtins:
        db.add_all(ReportTemplate(**builtin_fields(t)) for t in BUILTIN_TEMPLATES)
    by_name = {t["name"]: t for t in BUILTIN_TEMPLATES}
    for row in builtins:
        if row.name in REPLACED_BUILTINS:
            for field, value in builtin_fields(by_name[REPLACED_BUILTINS[row.name]]).items():
                setattr(row, field, value)
    # Dashboard templates (OpenPages) arrived later, and more are added over time.
    rows = template_rows()
    first_time = not any((row.layout or {}).get("kind") == "dashboard" for row in builtins)
    if first_time:
        db.add_all(ReportTemplate(**builtin_fields(t)) for t in rows)
    else:
        layouts = {t["name"]: t["layout"] for t in rows}
        for row in builtins:  # keep the charts of the ones already here current with this version
            if row.name in layouts and row.layout != layouts[row.name]:
                row.layout = layouts[row.name]
        # Dashboard templates added since this database was set up. Nothing records which names
        # were ever seeded, so a dashboard template someone deletes comes back on the next start;
        # the trade is that new ones reach existing installations at all.
        known = {row.name for row in builtins}
        db.add_all(ReportTemplate(**builtin_fields(t)) for t in rows if t["name"] not in known)
    db.commit()


def clean(field: str, value):
    """Normalises a field before it is stored."""
    if field == "color":
        return value.upper()
    return value.strip() if isinstance(value, str) else value


def can_edit(t: ReportTemplate, user: User) -> bool:
    if user.role == "manager":
        return True
    return not t.is_builtin and t.owner_id == user.id


def to_out(t: ReportTemplate, user: User) -> TemplateOut:
    return TemplateOut(id=t.id, name=t.name, description=t.description, prompt=t.prompt, color=t.color,
                       layout=t.layout or {}, visibility=t.visibility, is_builtin=t.is_builtin,
                       owner_id=t.owner_id, owner_name=t.owner.full_name if t.owner else None,
                       can_edit=can_edit(t, user), created_at=t.created_at, updated_at=t.updated_at)


def get_visible(db: Session, template_id: int, user: User) -> ReportTemplate:
    t = db.get(ReportTemplate, template_id, options=[joinedload(ReportTemplate.owner)])
    if t is None or (t.visibility == "private" and t.owner_id != user.id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Template not found")
    return t


class BuildIn(BaseModel):
    source_id: int | None = None


@router.post("/{template_id}/build", status_code=201)
def build_dashboard(template_id: int, body: BuildIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Builds a draft dashboard from a dashboard template on the chosen connection. Every chart's query
    runs once first: charts that can't run there (an object type that isn't shared, a field this
    installation doesn't have) are left out and listed in "skipped"."""
    from .assistant import _save  # the same save as dashboards built in chat

    t = get_visible(db, template_id, user)
    layout = t.layout or {}
    if layout.get("kind") != "dashboard":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "This template builds a report from a question; use it from Ask a question.")
    try:
        source = get_source(db, body.source_id)
    except SourceError as err:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(err))
    wanted = layout.get("source_type")
    if wanted and source.db_type != wanted:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"This template is for {wanted.replace('openpages', 'IBM OpenPages')} "
                                                         f"connections; {source.name} is {source.type_label}.")
    widgets, skipped = [], []
    for w in layout.get("widgets") or []:
        widget = {k: v for k, v in w.items() if k in ("kind", "title", "question", "sql", "chart", "size", "text", "style")}
        widget["id"] = uuid.uuid4().hex[:8]
        if w.get("kind") == "text":
            widgets.append(widget)
            continue
        try:
            run_sql(source, w.get("sql", ""))
        except (UnsafeSQL, QueryFailed) as err:
            skipped.append({"title": w.get("title", ""), "reason": str(err)})
            continue
        widgets.append(widget)
    # Headings with no chart left under them go too.
    widgets = [w for i, w in enumerate(widgets)
               if w.get("kind") != "text" or any(x.get("kind") != "text" for x in widgets[i + 1:i + 2])]
    if not any(w.get("kind") != "text" for w in widgets):
        reasons = "; ".join(sorted({s["reason"] for s in skipped}))[:400]
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"None of this template's charts can run on {source.name}: {reasons}")
    filters = []
    for f in layout.get("filters") or []:
        table = f"openpages.{f.get('type', '')}".lower() if source.is_openpages else str(f.get("table", "")).lower()
        picks = {w["id"]: {"table": table, "column": f.get("field", "")} for w in widgets
                 if w.get("kind") != "text" and table in dashboard_filters.query_tables(w["sql"], source)}
        if picks:
            built = dashboard_filters.make_filter(source, f.get("label", "Filter"), f.get("kind", "category"), widgets, picks)
            if built["columns"]:
                filters.append(built)
    title = t.name.split(": ", 1)[-1] if t.name.startswith("OpenPages: ") else t.name
    report = _save(db, user, title=title, prompt=t.prompt, source=source, widgets=widgets,
                   extra={"filters": filters, "template": t.name})
    return {"report": report, "skipped": skipped}


def check_can_share(visibility: str | None, user: User):
    if visibility == "shared" and user.role != "manager":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only managers can share templates with everyone")


@router.get("", response_model=list[TemplateOut])
def list_templates(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    # Everyone sees shared and built-in templates plus their own private ones.
    stmt = (select(ReportTemplate).options(joinedload(ReportTemplate.owner))
            .where(or_(ReportTemplate.visibility == "shared", ReportTemplate.owner_id == user.id))
            .order_by(ReportTemplate.is_builtin, ReportTemplate.updated_at.desc()))
    return [to_out(t, user) for t in db.scalars(stmt).all()]


@router.post("", response_model=TemplateOut, status_code=201)
def create_template(body: TemplateIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    check_can_share(body.visibility, user)
    t = ReportTemplate(owner_id=user.id, **{k: clean(k, v) for k, v in body.model_dump(exclude_none=True).items()})
    db.add(t)
    db.commit()
    return to_out(get_visible(db, t.id, user), user)


@router.put("/{template_id}", response_model=TemplateOut)
def update_template(template_id: int, body: TemplateUpdate, db: Session = Depends(get_db),
                    user: User = Depends(get_current_user)):
    t = get_visible(db, template_id, user)
    if not can_edit(t, user):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the owner or a manager can change this template")
    check_can_share(body.visibility, user)
    changes = body.model_dump(exclude_none=True)
    if t.is_builtin:
        changes.pop("visibility", None)  # built-in templates are always shared
    for field, value in changes.items():
        setattr(t, field, clean(field, value))
    db.commit()
    return to_out(get_visible(db, template_id, user), user)


@router.delete("/{template_id}", status_code=204)
def delete_template(template_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    t = get_visible(db, template_id, user)
    if not can_edit(t, user):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the owner or a manager can delete this template")
    db.delete(t)
    db.commit()
