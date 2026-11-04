"""
The OpenPages object models, as something to look at and to build a report against.

A data model here is one namespace of the OpenPages reporting framework: the object types a
solution uses and how they nest (see openpages_model.py). The shape is shipped with the product and
never changes; what changes per installation is which of those types exist, which have been shared
with this app on the Connections page, and what fields they carry. That live half is read from the
connection, cached, and re-read on demand - which is what the Refresh button does.
"""

from concurrent.futures import ThreadPoolExecutor

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from .. import openpages_model as om
from ..database import get_db
from ..datasources import SourceError, get_source
from ..datasources import forget_schema
from ..deps import get_current_user
from ..models import User

router = APIRouter(prefix="/api/data-models", tags=["data models"])

# Reading one type's fields is one request to OpenPages, so a 37-type model is 37 of them. They are
# independent, and OpenPages queues what it can't serve at once, so a handful at a time is plenty.
FIELD_WORKERS = 6


def _summary(m: om.DataModel) -> dict:
    return {"key": m.key, "name": m.name, "solution": m.solution, "namespace": m.namespace,
            "is_default": m.is_default, "entity_count": len(m.entities),
            "relationship_count": len(m.relationships)}


@router.get("")
def list_models(_: User = Depends(get_current_user)) -> list[dict]:
    """Every shipped model. No connection is touched: this is the framework's own shape."""
    return [_summary(m) for m in om.MODELS]


def _source_or_none(db: Session, source_id: int | None):
    """The chosen connection, or None when there isn't one. A broken connection is not an error
    here: the model still has a shape worth showing, just without live fields."""
    if source_id is None:
        return None, ""
    try:
        source = get_source(db, source_id)
    except SourceError as err:
        return None, str(err)
    if not source.is_openpages:
        return None, f"{source.name} is not an OpenPages connection, so it has no object model."
    return source, ""


def _detail(db: Session, key: str, source_id: int | None) -> dict:
    model = om.get(key)
    if model is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "That data model doesn't exist.")
    source, note = _source_or_none(db, source_id)
    depth = om.depth_of(model)

    shared: set[str] = set()
    exists: set[str] = set()
    fields: dict[str, list[dict]] = {}
    if source is not None:
        shared = {t.split(".", 1)[-1].lower() for t in source.tables}
        try:
            exists = {t.lower() for t in source.client.list_types()}
        except Exception as err:  # the model still draws; the boxes just can't be marked
            note = note or f"The object types couldn't be read from {source.name}: {err}"
        wanted = [e for e in model.entities if e.lower() in shared]
        if wanted:
            with ThreadPoolExecutor(max_workers=min(FIELD_WORKERS, len(wanted))) as pool:
                for entity, got in zip(wanted, pool.map(lambda e: om.fields_for(source, e), wanted)):
                    fields[entity] = got

    entities = [{
        "name": e,
        "depth": depth.get(e, 0),
        # Three separate facts, because they fail differently: the type may not be installed, or it
        # may be installed but not shared with this app, and only a manager can fix the second.
        "exists": (e.lower() in exists) if exists else None,
        "shared": (e.lower() in shared) if source is not None else None,
        "self_nesting": any(r.is_self and r.parent == e for r in model.relationships),
        "parents": om.parents_of(model, e),
        "children": om.children_of(model, e),
        "fields": fields.get(e, []),
    } for e in model.entities]

    return {**_summary(model),
            "connection": ({"id": source.id, "name": source.name} if source is not None else None),
            "live": bool(fields),
            "note": note,
            "entities": entities,
            "relationships": [{"parent": r.parent, "child": r.child, "self": r.is_self}
                              for r in model.relationships]}


@router.get("/{key:path}")
def read_model(key: str, source_id: int | None = Query(default=None),
               db: Session = Depends(get_db), _: User = Depends(get_current_user)) -> dict:
    """One model: its entities, how they nest, and - with a connection - their real fields."""
    return _detail(db, key, source_id)


@router.post("/{key:path}/refresh")
def refresh_model(key: str, source_id: int | None = Query(default=None),
                  db: Session = Depends(get_db), _: User = Depends(get_current_user)) -> dict:
    """Throws away what was cached about this connection and reads it again, so a field added in
    OpenPages this morning shows up without waiting for the cache to lapse."""
    if source_id is not None:
        om.forget(source_id)
        forget_schema(source_id)
    else:
        om.forget()
    return _detail(db, key, source_id)
