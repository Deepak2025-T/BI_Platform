from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..connections import connection_spec as spec_of
from ..connections import crypto, openpages, openpages_spec
from ..connections.engines import DB_TYPES, ConnSpec, dispose_engine, friendly_error, get_engine, make_engine, run_test
from ..connections.engines import list_tables as read_tables
from ..database import get_db
from ..deps import get_current_user, require_manager
from ..models import DataConnection, User
from ..schemas import (ConnectionDraft, ConnectionIn, ConnectionOut, ConnectionPublic, ConnectionTestOut,
                       ConnectionUpdate, SchemaTables)

router = APIRouter(prefix="/api/connections", tags=["connections"])

# Changing any of these means the old test result no longer applies.
CONNECT_FIELDS = {"db_type", "host", "port", "database", "username", "password", "options"}


def to_out(c: DataConnection) -> ConnectionOut:
    options = {**(c.options or {}), "has_client_key": bool((c.options or {}).get("client_key_encrypted"))}
    return ConnectionOut(id=c.id, name=c.name, db_type=c.db_type, type_label=DB_TYPES[c.db_type]["label"],
                         host=c.host, port=c.port, database=c.database, username=c.username,
                         has_password=bool(c.password_encrypted), schemas=c.schemas or [],
                         options=options, allowed_tables=c.allowed_tables or [], status=c.status,
                         last_tested_at=c.last_tested_at, last_error=c.last_error,
                         created_at=c.created_at, updated_at=c.updated_at)


def key_error(err: crypto.ConnectionsKeyError) -> HTTPException:
    return HTTPException(status.HTTP_400_BAD_REQUEST, str(err))


def get_connection(db: Session, connection_id: int) -> DataConnection:
    c = db.get(DataConnection, connection_id)
    if c is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Connection not found")
    return c


def check_details(db_type: str, host: str, database: str = "x") -> str:
    """Returns the host to save: for OpenPages, the API URL in its standard form."""
    if db_type == "openpages":
        try:
            return openpages.normalize_base(host)
        except ValueError as err:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(err))
    if db_type != "sqlite" and not host.strip():
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Enter the server name or address")
    if not database.strip():
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            "Enter the database file path" if db_type == "sqlite" else "Enter the database name")
    return host.strip()


def save_options(c: DataConnection, options: dict, client_key: str | None):
    """Options from the form, keeping the saved OpenPages private key unless a new one is given."""
    options = {k: v for k, v in options.items() if k != "has_client_key"}
    if options.get("auth_type") != "mtls" or client_key == "":
        options["client_key_encrypted"] = ""
    elif client_key:
        options["client_key_encrypted"] = crypto.encrypt(client_key)
    else:
        options["client_key_encrypted"] = (c.options or {}).get("client_key_encrypted", "")
    c.options = options


def check_name_free(db: Session, name: str, except_id: int | None = None):
    stmt = select(DataConnection.id).where(func.lower(DataConnection.name) == name.lower())
    if except_id is not None:
        stmt = stmt.where(DataConnection.id != except_id)
    if db.scalar(stmt) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, f'A connection called "{name}" already exists')





@router.get("/available", response_model=list[ConnectionPublic])
def available_connections(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    """Connection names for everyone, e.g. for a connection picker. No hosts, users or passwords."""
    rows = db.scalars(select(DataConnection).order_by(func.lower(DataConnection.name))).all()
    return [ConnectionPublic(id=c.id, name=c.name, db_type=c.db_type, type_label=DB_TYPES[c.db_type]["label"],
                             status=c.status) for c in rows]


@router.get("", response_model=list[ConnectionOut], dependencies=[Depends(require_manager)])
def list_connections(db: Session = Depends(get_db)):
    return [to_out(c) for c in db.scalars(select(DataConnection).order_by(func.lower(DataConnection.name))).all()]


@router.post("", response_model=ConnectionOut, status_code=201)
def create_connection(body: ConnectionIn, db: Session = Depends(get_db), user: User = Depends(require_manager)):
    host = check_details(body.db_type, body.host, body.database)
    name = body.name.strip()
    check_name_free(db, name)
    c = DataConnection(name=name, db_type=body.db_type, host=host, port=body.port,
                       database=body.database.strip(), username=body.username.strip(),
                       schemas=[s.strip() for s in body.schemas if s.strip()], created_by=user.id)
    try:
        c.password_encrypted = crypto.encrypt(body.password or "")
        save_options(c, body.options.model_dump(), body.client_key)
    except crypto.ConnectionsKeyError as err:
        raise key_error(err)
    db.add(c)
    db.commit()
    return to_out(c)


@router.put("/{connection_id}", response_model=ConnectionOut, dependencies=[Depends(require_manager)])
def update_connection(connection_id: int, body: ConnectionUpdate, db: Session = Depends(get_db)):
    c = get_connection(db, connection_id)
    changes = body.model_dump(exclude_unset=True)
    if "name" in changes:
        check_name_free(db, changes["name"].strip(), except_id=c.id)
        c.name = changes["name"].strip()
    for field in ("db_type", "host", "port", "database", "username"):
        if field in changes:
            value = changes[field]
            setattr(c, field, value.strip() if isinstance(value, str) else value)
    c.host = check_details(c.db_type, c.host, c.database)
    try:
        if changes.get("password") is not None:
            c.password_encrypted = crypto.encrypt(changes["password"])
        if changes.get("options") is not None or changes.get("client_key") is not None:
            save_options(c, changes.get("options") or dict(c.options or {}), changes.get("client_key"))
    except crypto.ConnectionsKeyError as err:
        raise key_error(err)
    if changes.get("schemas") is not None:
        c.schemas = [s.strip() for s in changes["schemas"] if s.strip()]
    if changes.get("allowed_tables") is not None:
        c.allowed_tables = sorted({t.strip() for t in changes["allowed_tables"] if t.strip()})
    changed = set(changes) - ({"password"} if changes.get("password") is None else set())
    if CONNECT_FIELDS & changed or changes.get("client_key") is not None:
        c.status, c.last_error = "untested", ""
        dispose_engine(c.id)
        openpages.forget_client(c.id)
    db.commit()
    return to_out(c)


@router.delete("/{connection_id}", status_code=204, dependencies=[Depends(require_manager)])
def delete_connection(connection_id: int, db: Session = Depends(get_db)):
    c = get_connection(db, connection_id)
    dispose_engine(c.id)
    openpages.forget_client(c.id)
    db.delete(c)
    db.commit()


@router.post("/test", response_model=ConnectionTestOut, dependencies=[Depends(require_manager)])
def test_draft(body: ConnectionDraft, db: Session = Depends(get_db)):
    """Tests the details on the form before they are saved. Nothing is stored."""
    host = check_details(body.db_type, body.host, body.database)
    if body.db_type == "openpages":
        return _test_openpages_draft(db, body, host)
    password = body.password
    if password is None and body.id is not None:
        try:
            password = crypto.decrypt(get_connection(db, body.id).password_encrypted)
        except crypto.ConnectionsKeyError as err:
            raise key_error(err)
    spec = ConnSpec(db_type=body.db_type, host=body.host.strip(), port=body.port, database=body.database.strip(),
                    username=body.username.strip(), password=password or "", options=body.options.model_dump())
    try:
        engine = make_engine(spec, pooled=False)
        try:
            result = run_test(engine, spec, body.schemas)
        finally:
            engine.dispose()
    except Exception as err:  # any driver or network error is a failed test, not a server error
        return ConnectionTestOut(ok=False, message=friendly_error(err))
    return ConnectionTestOut(ok=True, message=_ok_message(result), **result)


@router.post("/{connection_id}/test", response_model=ConnectionTestOut, dependencies=[Depends(require_manager)])
def test_saved(connection_id: int, db: Session = Depends(get_db)):
    """Tests a saved connection and records the result on it."""
    c = get_connection(db, connection_id)
    try:
        spec = spec_of(c)
    except crypto.ConnectionsKeyError as err:
        raise key_error(err)
    c.last_tested_at = datetime.now(timezone.utc)
    try:
        if c.db_type == "openpages":
            result = openpages.run_test(openpages.get_client(c.id, c.updated_at.isoformat(), openpages_spec(c)))
        else:
            result = run_test(get_engine(c.id, c.updated_at.isoformat(), spec), spec, c.schemas or [])
    except Exception as err:
        c.status, c.last_error = "error", friendly_error(err)
        db.commit()
        return ConnectionTestOut(ok=False, message=c.last_error)
    c.status, c.last_error = "ok", ""
    db.commit()
    return ConnectionTestOut(ok=True, message=_ok_message(result), **result)


@router.get("/{connection_id}/tables", response_model=list[SchemaTables], dependencies=[Depends(require_manager)])
def list_tables(connection_id: int, db: Session = Depends(get_db)):
    """The tables and views the connection's account can see, for choosing which ones users may query."""
    c = get_connection(db, connection_id)
    try:
        if c.db_type == "openpages":
            return openpages.run_test(openpages.get_client(c.id, c.updated_at.isoformat(), openpages_spec(c)))["schemas"]
        spec = spec_of(c)
        return read_tables(get_engine(c.id, c.updated_at.isoformat(), spec), spec, c.schemas or [])
    except crypto.ConnectionsKeyError as err:
        raise key_error(err)
    except Exception as err:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"Couldn't read the tables: {friendly_error(err)}")


def _test_openpages_draft(db: Session, body: ConnectionDraft, host: str) -> ConnectionTestOut:
    saved = get_connection(db, body.id) if body.id is not None else DataConnection(password_encrypted="", options={})
    draft = DataConnection(host=host, username=body.username.strip(), password_encrypted=saved.password_encrypted,
                           options={**body.options.model_dump(),
                                    "client_key_encrypted": (saved.options or {}).get("client_key_encrypted", "")})
    try:
        spec = openpages_spec(draft, password=body.password, client_key=body.client_key)
        result = openpages.run_test(openpages.OpenPagesClient(spec))
    except crypto.ConnectionsKeyError as err:
        raise key_error(err)
    except openpages.OpenPagesError as err:
        return ConnectionTestOut(ok=False, message=str(err))
    return ConnectionTestOut(ok=True, message=_ok_message(result), **result)


def _ok_message(result: dict) -> str:
    n = result["table_count"]
    version = f" (version {result['server_version']})" if result["server_version"] else ""
    if result["schemas"] and result["schemas"][0]["schema"] == openpages.SCHEMA:
        return f"Signed in to OpenPages in {result['elapsed_ms']} ms. Found {n} object type{'' if n == 1 else 's'}."
    found = "1 table or view" if n == 1 else f"{n} tables and views"
    return f"Connected in {result['elapsed_ms']} ms{version}. Found {found}."
