"""
The visual builder: build a chart by choosing fields, without writing SQL.

The browser asks for the tables a connection shares, then the columns of one table, then sends a
spec saying what to put on the axis and what to add up. visual_query turns the spec into SQL and
datasources runs it read-only, the same way it runs SQL an AI model wrote.

Everything here needs a signed-in user, not a manager: these read only the tables a manager has
already shared on the Connections page.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..database import get_db
from ..datasources import QueryFailed, SourceError, column_values, get_source, run_sql
from ..deps import get_current_user
from ..models import User
from ..sql_guard import UnsafeSQL
from ..visual_query import AGGS, BUCKETS, MAX_IN_VALUES, OPS, SpecError, compile_spec, describe_table

router = APIRouter(prefix="/api/visuals", tags=["visual builder"])


class SpecIn(BaseModel):
    """One chart as the builder describes it. Every name is checked against the shared tables."""

    table: str = Field(min_length=1, max_length=200)
    # {"column", "bucket" (dates only), "alias"}
    dimensions: list[dict] = Field(default_factory=list, max_length=8)
    # {"column", "agg", "alias"}
    measures: list[dict] = Field(default_factory=list, max_length=12)
    # {"column", "op", "values"}
    filters: list[dict] = Field(default_factory=list, max_length=30)
    # {"ref", "dir"}
    order: list[dict] = Field(default_factory=list, max_length=4)
    limit: int | None = Field(default=None, ge=1, le=5000)


class BuildIn(BaseModel):
    source_id: int | None = None
    spec: SpecIn
    refresh: bool = False
    # Saving a chart: write the filter values into the SQL, because the saved query is later run
    # on its own by the dashboard, which carries no parameters with it.
    inline: bool = False


def _source(db: Session, source_id: int | None):
    try:
        return get_source(db, source_id)
    except SourceError as err:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(err))


def _compile(db: Session, body: BuildIn, *, inline: bool = False):
    source = _source(db, body.source_id)
    try:
        sql, params = compile_spec(source, body.spec.model_dump(), inline=inline)
    except SpecError as err:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(err))
    return source, sql, params


@router.get("/options")
def options(_: User = Depends(get_current_user)):
    """What the builder may ask for: how to summarise numbers, group dates and filter rows."""
    return {
        "aggs": [{"id": key, "label": label} for key, label in AGGS.items()],
        "buckets": list(BUCKETS),
        "ops": list(OPS),
        "max_filter_values": MAX_IN_VALUES,
    }


@router.get("/tables")
def tables(source_id: int | None = None, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    """The tables of one connection that a manager has shared, for the builder's table picker."""
    source = _source(db, source_id)
    return [{"table": t, "schema": t.rpartition(".")[0], "name": t.rpartition(".")[2]} for t in source.tables]


@router.get("/fields")
def fields(table: str = Query(min_length=1, max_length=200), source_id: int | None = None,
           db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    """The columns of one shared table, each marked as something to group by or something to add up."""
    source = _source(db, source_id)
    try:
        return describe_table(source, table)
    except SpecError as err:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(err))


@router.get("/values")
def values(table: str = Query(min_length=1, max_length=200), column: str = Query(min_length=1, max_length=200),
           limit: int = Query(default=200, ge=1, le=1000), source_id: int | None = None,
           db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    """The values one column holds, for a filter's or slicer's list."""
    source = _source(db, source_id)
    try:
        # describe_table checks the table is shared and the column is real before reading any values.
        described = describe_table(source, table)
        real = next((f["name"] for f in described["fields"] if f["name"].lower() == column.strip().lower()), None)
        if real is None:
            raise SpecError(f'{described["table"]} has no column called "{column}".')
        return {"table": described["table"], "column": real,
                "values": column_values(source, described["table"], real, limit=limit)}
    except SpecError as err:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(err))


@router.post("/compile")
def compile_only(body: BuildIn, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    """The SQL a chart would run, to show in the builder's "SQL" tab. Nothing is queried."""
    _, sql, params = _compile(db, body, inline=body.inline)
    return {"sql": sql, "parameters": len(params)}


@router.post("/run")
def run(body: BuildIn, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    """Builds the chart's SQL and runs it, for the builder's live preview."""
    source, sql, params = _compile(db, body)
    try:
        return run_sql(source, sql, params, refresh=body.refresh)
    except UnsafeSQL as err:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(err))
    except QueryFailed as err:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(err))
