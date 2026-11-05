import re
import uuid
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from .. import dashboard_filters

from ..ai.assistant import AssistantError, chat, new_widget, plan_dashboard, write_widget
from ..ai.providers import AIError, ModelSpec
from ..connections import crypto
from ..datasources import QueryFailed, SourceError, get_source, list_sources, narrow, run_sql
from ..database import get_db
from ..deps import get_current_user
from ..models import AIModel, Report, User
from ..prompt_ideas import ideas_for
from ..excel_export import dashboard_workbook
from ..ppt_export import dashboard_deck
from ..schemas import (AddWidgetsIn, ChatIn, DashboardDataIn, DashboardIn, DrillIn, FilterMapIn, ReportOut,
                       SaveDashboardIn, SourceOut, WidgetIn)
from ..refresh import RefreshFailed, as_utc, latest_snapshot, refresh_report, snapshot_matches
from ..report_data import active_filters, run_widgets
from ..datasources import check_query
from ..sql_guard import UnsafeSQL
from ..visual_query import SpecError, compile_spec
from .reports import check_can_edit, get_visible, to_out

router = APIRouter(tags=["assistant"])


def _model(db: Session, model_id: int) -> tuple[AIModel, ModelSpec]:
    m = db.get(AIModel, model_id)
    if m is None or not m.is_active:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "That AI model has been turned off or removed. Pick another one.")
    try:
        key = crypto.decrypt(m.api_key_encrypted)
    except crypto.ConnectionsKeyError as err:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(err))
    return m, ModelSpec(provider=m.provider, model=m.model, base_url=m.base_url, api_key=key)


def _source(db: Session, source_id: int | None, data_model: str | None = None):
    """The database to query, seen through one OpenPages data model when one was chosen. The
    model narrows which object types exist as far as everything downstream is concerned."""
    try:
        return narrow(get_source(db, source_id), data_model)
    except SourceError as err:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(err))


def _ai_call(fn, *args):
    """Runs an AI step, turning its failures into readable HTTP errors."""
    try:
        return fn(*args)
    except AIError as err:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"The AI model couldn't be used: {err}")
    except AssistantError as err:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(err))


@router.get("/api/sources", response_model=list[SourceOut])
def sources(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    """Databases people can chat with: names and types only, never servers or accounts."""
    return [SourceOut(id=s.id, name=s.name, db_type=s.db_type, type_label=s.type_label, table_count=len(s.tables),
                      builtin=s.id is None) for s in list_sources(db)]


@router.get("/api/assistant/prompt-ideas")
def prompt_ideas(source_id: int | None = None, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    """Questions worth asking of one database, from its own columns. No AI model is used."""
    return {"ideas": ideas_for(_source(db, source_id))}


@router.post("/api/assistant/chat")
def chat_message(body: ChatIn, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    model, spec = _model(db, body.model_id)
    source = _source(db, body.source_id, body.data_model)
    result = _ai_call(chat, spec, source, body.question, [t.model_dump() for t in body.history])
    return {**result, "model": model.name, "source": source.name}


@router.post("/api/assistant/widget")
def widget_from_question(body: WidgetIn, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    """One chart for a dashboard, from a question. Nothing is saved."""
    _, spec = _model(db, body.model_id)
    return _ai_call(write_widget, spec, _source(db, body.source_id, body.data_model), body.question)


@router.post("/api/assistant/dashboard", status_code=201)
def build_dashboard(body: DashboardIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Plans a dashboard with the AI model, runs every chart, and saves it as a draft report."""
    model, spec = _model(db, body.model_id)
    source = _source(db, body.source_id, body.data_model)
    params = body.parameters.model_dump(mode="json")
    plan = _ai_call(plan_dashboard, spec, source, body.prompt, params)
    # The data model is kept on the report so a refresh, a drill or an added chart later on sees
    # the same object types this dashboard was planned against.
    extra = {"parameters": params, "model": model.name}
    if body.data_model:
        extra["data_model"] = body.data_model
    report = _save(db, user, title=plan["title"], prompt=body.prompt, source=source, widgets=plan["widgets"],
                   extra=extra)
    return {"report": report, "failed": plan["failed"]}


@router.post("/api/assistant/save", response_model=ReportOut, status_code=201)
def save_dashboard(body: SaveDashboardIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Saves charts from a chat as a new draft dashboard report."""
    source = _source(db, body.source_id)
    widgets = []
    for w in body.widgets:
        try:
            check_query(source, w.sql)
        except UnsafeSQL as err:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f'"{w.title}" can\'t be saved: {err}')
        widgets.append(new_widget(w.title, w.question, w.sql, w.chart,
                                  {"style": w.style, "size": w.size, "visual": w.visual}))
    return _save(db, user, title=body.title, prompt=body.prompt, source=source, widgets=widgets, extra={})


@router.post("/api/reports/{report_id}/widgets", response_model=ReportOut)
def add_widgets(report_id: int, body: AddWidgetsIn, db: Session = Depends(get_db),
                user: User = Depends(get_current_user)):
    """Adds charts to a dashboard that already exists — from a chat answer, or from the chart
    builder — instead of starting another report for them.

    Every query is checked against the tables shared now, and the report has to read the same
    database: its filters, refresh and export all assume one connection."""
    report, source = _dashboard(db, report_id, user)
    check_can_edit(report, user)
    if body.source_id != report.config.get("source_id"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            f"{report.title} reads {source.name}. A chart from another database can't be added to it.")
    widgets = list(report.config.get("widgets") or [])
    taken = {w.get("id") for w in widgets}
    for w in body.widgets:
        try:
            check_query(source, w.sql)
        except UnsafeSQL as err:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f'"{w.title}" can\'t be added: {err}')
        added = new_widget(w.title, w.question, w.sql, w.chart,
                           {"style": w.style, "size": w.size, "visual": w.visual})
        while added["id"] in taken:          # ids only have to be unique within one report
            added["id"] = uuid.uuid4().hex[:8]
        taken.add(added["id"])
        widgets.append(added)
    # Reassigning makes SQLAlchemy notice the change; editing the list in place would not.
    report.config = {**report.config, "widgets": widgets}
    db.commit()
    return to_out(get_visible(db, report.id, user))


@router.post("/api/reports/{report_id}/data")
def dashboard_data(report_id: int, body: DashboardDataIn | None = None, db: Session = Depends(get_db),
                   user: User = Depends(get_current_user)):
    """Runs every chart's saved SQL (no AI), with the dashboard filters applied. Each chart is checked
    again against the tables that are allowed now, so a table a manager has since removed stops
    working. Results come from the cache for 15 minutes unless refresh is set.

    A dashboard with automatic refresh shows its latest snapshot instead, unless filters are set:
    everyone sees the same numbers, and refresh runs the queries now and saves a new snapshot."""
    report, source = _dashboard(db, report_id, user)
    body = body or DashboardDataIn()
    values = {k: v.model_dump() for k, v in body.filters.items()}
    if report.refresh_every != "off" and not active_filters(report.config, values):
        snap = None if body.refresh else latest_snapshot(db, report.id)
        if snap is None or not snapshot_matches(report, snap):
            try:
                snap = refresh_report(db, report, "manual")
            except RefreshFailed as err:
                raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"The dashboard couldn't be refreshed: {err}")
        at = as_utc(snap.created_at).isoformat(timespec="seconds")
        return {"source": snap.data.get("source", source.name), "snapshot_at": at,
                "widgets": [{**w, "ran_at": at, "cached": False} for w in snap.data["widgets"]]}
    return {"source": source.name, "snapshot_at": None, "widgets": _run_widgets(report.config, source, body)}


@router.post("/api/reports/{report_id}/drill")
def drill_widget(report_id: int, body: DrillIn, db: Session = Depends(get_db),
                 user: User = Depends(get_current_user)):
    """One level deeper into a chart built from fields.

    The chart keeps the fields it was built from, and any after the first on its axis are its
    drill levels. `values` is the trail of what was clicked, so one value asks for the second
    level inside that value, two values for the third, and so on. The columns come from the saved
    chart, never from the request: the request only says what was clicked.

    The query is built here rather than filtered in the browser, so a drilled chart is a real
    GROUP BY over the whole table and its totals are right."""
    report, source = _dashboard(db, report_id, user)
    widget = next((w for w in report.config.get("widgets") or [] if w.get("id") == body.widget_id), None)
    if widget is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "That chart isn't on this dashboard")
    visual = widget.get("visual") or {}
    levels = [d for d in (visual.get("drill") or []) if isinstance(d, dict)]
    shown = [d for d in (visual.get("dimensions") or []) if isinstance(d, dict)]
    if not levels or not shown:
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            "This chart has nothing to drill into. Charts built in Build a chart drill down when "
                            "their axis has more than one field.")
    depth = len(body.values)
    if not 1 <= depth <= len(levels):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"This chart has {len(levels)} level(s) to drill into.")

    trail = [shown[0]] + levels            # level 0 is what the chart shows to begin with
    dimensions = [trail[depth]] + shown[1:]  # the new level, keeping any legend field
    conditions = list(visual.get("filters") or [])
    for item, value in zip(trail, body.values):
        conditions.append({"column": item.get("column"), "bucket": item.get("bucket"),
                           "op": "is_null" if value is None else "=",
                           "values": [] if value is None else [value]})
    measures = [m for m in (visual.get("measures") or []) if isinstance(m, dict)]
    axis, first = dimensions[0], (measures[0].get("alias") if measures else None)
    # Dates read in time order; everything else ranks by its first number, as the builder does.
    order = ([{"ref": axis.get("alias"), "dir": "asc"}] if axis.get("bucket") and axis.get("alias")
             else [{"ref": first, "dir": "desc"}] if first else [])
    spec = {**visual, "dimensions": dimensions, "filters": conditions, "order": order}
    try:
        # Inlined, so the dashboard's own filters can still bind values of their own below.
        sql, _ = compile_spec(source, spec, inline=True)
    except SpecError as err:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"This chart can't be drilled into: {err}")

    values = {k: v.model_dump() for k, v in body.filters.items()}
    sql, params, _, skipped = dashboard_filters.apply(sql, source, report.config.get("filters") or [],
                                                      values, body.widget_id)
    try:
        data = run_sql(source, sql, params, refresh=body.refresh)
    except (UnsafeSQL, QueryFailed) as err:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"The drilled chart couldn't run: {err}")
    return {**data, "chart": {**(widget.get("chart") or {}), "x": axis.get("alias")},
            "depth": depth, "levels": len(levels), "not_filtered": skipped,
            "label": axis.get("alias") or axis.get("column")}


@router.post("/api/reports/{report_id}/export")
def dashboard_export(report_id: int, body: DashboardDataIn | None = None, db: Session = Depends(get_db),
                     user: User = Depends(get_current_user)):
    """The dashboard as an Excel file, one sheet per chart, with the same filters as the viewer."""
    report, source = _dashboard(db, report_id, user)
    body = body or DashboardDataIn()
    results = _run_widgets(report.config, source, body)
    content = dashboard_workbook(report.title, report.config, source.name, results, body.model_dump(mode="json")["filters"])
    name = " ".join(re.sub(r'[\\/:*?"<>|]+', " ", report.title).split())[:80] or "Dashboard"
    return Response(content, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": f"attachment; filename=\"dashboard.xlsx\"; filename*=UTF-8''{quote(name)}.xlsx"})


@router.post("/api/reports/{report_id}/export-ppt")
def dashboard_export_ppt(report_id: int, body: DashboardDataIn | None = None, db: Session = Depends(get_db),
                         user: User = Depends(get_current_user)):
    """The dashboard as a PowerPoint deck, one slide per chart, with the same filters as the viewer.

    The charts are real PowerPoint charts, so a slide can be restyled or pasted into another deck
    with its numbers intact."""
    report, source = _dashboard(db, report_id, user)
    body = body or DashboardDataIn()
    results = _run_widgets(report.config, source, body)
    content = dashboard_deck(report.title, report.config, source.name, results, body.model_dump(mode="json")["filters"])
    name = " ".join(re.sub(r'[\\/:*?"<>|]+', " ", report.title).split())[:80] or "Dashboard"
    return Response(content,
                    media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                    headers={"Content-Disposition": f"attachment; filename=\"dashboard.pptx\"; "
                                                    f"filename*=UTF-8''{quote(name)}.pptx"})


@router.post("/api/reports/{report_id}/filters/map")
def map_dashboard_filter(report_id: int, body: FilterMapIn, db: Session = Depends(get_db),
                         user: User = Depends(get_current_user)):
    """Design time: the AI model picks the column each chart filters on. Nothing is saved here; the
    editor adds the filter to the report config."""
    report, source = _dashboard(db, report_id, user)
    check_can_edit(report, user)
    _, spec = _model(db, body.model_id)
    widgets = [w.model_dump() for w in body.widgets]
    return _ai_call(dashboard_filters.map_filter, spec, source, body.label, body.kind, widgets, body.id)


def _dashboard(db: Session, report_id: int, user: User):
    report = get_visible(db, report_id, user)
    if (report.config or {}).get("kind") != "dashboard":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "This report isn't a dashboard")
    return report, _source(db, report.config.get("source_id"))


def _run_widgets(config: dict, source, body: DashboardDataIn) -> list[dict]:
    return run_widgets(config, source, {k: v.model_dump() for k, v in body.filters.items()}, refresh=body.refresh)


def _save(db: Session, user: User, *, title: str, prompt: str, source, widgets: list[dict], extra: dict) -> ReportOut:
    config = {"kind": "dashboard", "source_id": source.id, "source_name": source.name, "widgets": widgets, **extra}
    r = Report(title=title[:200], prompt=(prompt or title)[:2000], config=config, owner_id=user.id)
    db.add(r)
    db.commit()
    return to_out(get_visible(db, r.id, user))
