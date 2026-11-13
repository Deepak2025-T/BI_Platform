import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, joinedload

from .. import dashboard_filters
from ..database import get_db
from ..datasources import QueryFailed, SourceError, get_source, run_sql
from ..erp_templates import template_rows as erp_template_rows
from ..openpages_modules import MODULES, module_template_rows
from ..openpages_templates import template_rows as openpages_template_rows
from ..sql_guard import UnsafeSQL
from ..deps import get_current_user
from ..ai.colors import apply_color_rules, color_rules_from_prompt, normalize_hex
from ..models import ReportTemplate, User
from ..schemas import TemplateIn, TemplateOut, TemplateUpdate
from ..template_data import BUILTIN_TEMPLATES, REPLACED_BUILTINS

router = APIRouter(prefix="/api/templates", tags=["templates"])

# Name prefixes that say which folder a template sits in, not what the report is about, so they come
# off the report title: "ORM: Loss events" builds a report called "Loss events".
TITLE_PREFIXES = {"OpenPages", "ERP", *MODULES}


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
    # Dashboard templates (OpenPages, then ERP) arrived later, and more are added over time.
    rows = openpages_template_rows() + module_template_rows() + erp_template_rows()
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
    # Domains, and later the module folders inside them, arrived after the templates did, so file
    # the ones already here. Templates only move; none are renamed or removed.
    filed = {t["name"]: t for t in rows + BUILTIN_TEMPLATES}
    for row in builtins:
        wanted = filed.get(row.name)
        if not wanted:
            continue
        if row.category != wanted["category"]:
            row.category = wanted["category"]
        if (row.module or "") != wanted.get("module", ""):
            row.module = wanted.get("module", "")
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
                       category=t.category or "Uncategorised", module=t.module or "",
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


def with_known_fields(source, template_widget: dict) -> dict:
    """A summary table's query, written against the fields this installation actually has.

    A table naming six fields can't be settled name by name the way a one-field chart is: a single
    name this installation doesn't have fails the whole query, and trying every combination of the
    names installations use would be hundreds of queries for one answer. The object type's own
    field list settles every one of them in a single read, and a field that is here under none of
    its names is simply not a column."""
    pick = template_widget.get("pick_fields")
    if not pick or not getattr(source, "is_openpages", False):
        return template_widget
    type_name = str(pick.get("type") or "")
    try:
        known = {str(f.get("name") or "") for f in source.client.type_fields(type_name)}
    except Exception:  # the type isn't shared, or the definition can't be read: try the queries
        return template_widget
    chosen = [name for names in (pick.get("fields") or [])
              if (name := next((n for n in names if n in known), ""))]
    if not chosen:
        return template_widget
    return {**template_widget,
            "sql": f"SELECT " + ", ".join(f"[{type_name}].[{n}]" for n in chosen) + f" FROM [{type_name}]",
            "alt_sql": []}


def first_that_runs(source, template_widget: dict, widget: dict) -> str:
    """Settles which of a chart's queries this connection can answer, writing it onto `widget`.

    A template chart may carry the same question written more than once, against the field names
    different OpenPages installations use for the same thing (see openpages_templates.Field). Each
    is run in turn and the first that answers is kept, along with the field names its axes should
    carry. A grid names two fields, so its second axis (the heat map's columns) moves in step with
    the first. Returns "" when one worked, or why the last one didn't when none did."""
    variants = [template_widget.get("sql", "")] + [s for s in (template_widget.get("alt_sql") or [])
                                                   if isinstance(s, str)]
    chart = template_widget.get("chart") or {}
    axes = [chart.get("x", "")] + list(template_widget.get("alt_x") or [])
    legends = [chart.get("legend", "")] + list(template_widget.get("alt_legend") or [])
    failure = "the chart has no query"
    for i, sql in enumerate(variants):
        try:
            run_sql(source, sql)
        except (UnsafeSQL, QueryFailed) as err:
            failure = str(err)
            continue
        widget["sql"] = sql
        picked = {}
        if i < len(axes) and isinstance(axes[i], str) and axes[i]:
            picked["x"] = axes[i]
        if i < len(legends) and isinstance(legends[i], str) and legends[i]:
            picked["legend"] = legends[i]
        if picked:
            widget["chart"] = {**(widget.get("chart") or {}), **picked}
        return ""
    return failure


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
        label = {"openpages": "IBM OpenPages", "postgresql": "PostgreSQL", "mysql": "MySQL",
                 "mssql": "SQL Server", "sqlite": "SQLite"}.get(wanted, wanted)
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"This template is for {label} connections; "
                                                         f"{source.name} is {source.type_label}.")
    widgets, skipped = [], []
    for w in layout.get("widgets") or []:
        widget = {k: v for k, v in w.items()
                  if k in ("kind", "title", "question", "sql", "chart", "size", "text", "style", "rollup", "height")}
        widget["id"] = uuid.uuid4().hex[:8]
        if w.get("kind") == "text":
            widgets.append(widget)
            continue
        reason = first_that_runs(source, with_known_fields(source, w), widget)
        if reason:
            skipped.append({"title": w.get("title", ""), "reason": reason})
        else:
            widgets.append(widget)
    # The template's palette is copied onto each chart, so the report keeps these colours even if
    # the template is later changed. Colour rules in the template's prompt are read the same way.
    palette = [c for c in (normalize_hex(x) for x in (layout.get("chartPalette") or [])) if c][:24]
    if len(palette) >= 2:
        for w in widgets:
            if w.get("kind") != "text":
                w["style"] = {**(w.get("style") or {}), "palette": palette}
    apply_color_rules([w for w in widgets if w.get("kind") != "text"], color_rules_from_prompt(t.prompt))
    # Headings with no chart left under them go too.
    widgets = [w for i, w in enumerate(widgets)
               if w.get("kind") != "text" or any(x.get("kind") != "text" for x in widgets[i + 1:i + 2])]
    if not any(w.get("kind") != "text" for w in widgets):
        reasons = "; ".join(sorted({s["reason"] for s in skipped}))[:400]
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"None of this template's charts can run on {source.name}: {reasons}")
    filters = []
    for f in layout.get("filters") or []:
        # type "*" means "whatever object type this chart reads", so one filter can cover a whole
        # dashboard on a field every type has, such as [Location] — the business entity path an
        # object hangs under. Named types still only reach the charts that read them.
        charts = [w for w in widgets if w.get("kind") != "text"]
        if source.is_openpages and f.get("type") == "*":
            picks = {}
            for w in charts:
                read = dashboard_filters.query_tables(w["sql"], source)
                if read:
                    picks[w["id"]] = {"table": read[0], "column": f.get("field", "")}
            built = dashboard_filters.make_filter(source, f.get("label", "Filter"), f.get("kind", "category"),
                                                  widgets, picks) if picks else None
            if built and built["columns"]:
                filters.append(built)
            continue
        table = f"openpages.{f.get('type', '')}".lower() if source.is_openpages else str(f.get("table", "")).lower()
        reading = [w for w in charts if table in dashboard_filters.query_tables(w["sql"], source)]
        # The field may be known by more than one name here too, so each is tried until one is a
        # real column: make_filter drops a column the table doesn't have, leaving nothing to filter.
        for column in [f.get("field", "")] + list(f.get("alt_fields") or []):
            picks = {w["id"]: {"table": table, "column": column} for w in reading}
            if not picks:
                break
            built = dashboard_filters.make_filter(source, f.get("label", "Filter"), f.get("kind", "category"),
                                                  widgets, picks)
            if built["columns"]:
                filters.append(built)
                break
    # "OpenPages: Controls effectiveness" becomes "Controls effectiveness": the domain belongs on
    # the template, not on every report built from it.
    title = t.name.split(": ", 1)[-1] if t.name.split(": ", 1)[0] in TITLE_PREFIXES else t.name
    # A template may ask for a look as well as a set of charts: the report carries the theme so it
    # still reads as that design after it is saved, published and printed.
    extra = {"filters": filters, "template": t.name}
    if isinstance(layout.get("theme"), str) and layout["theme"]:
        extra["theme"] = layout["theme"][:40]
    report = _save(db, user, title=title, prompt=t.prompt, source=source, widgets=widgets, extra=extra)
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
