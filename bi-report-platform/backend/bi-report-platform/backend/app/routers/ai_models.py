from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from ..ai.providers import CLAUDE_MODELS, PROVIDERS, AIError, ModelSpec, discover, ping
from ..connections import crypto
from ..database import get_db
from ..deps import get_current_user, require_manager
from ..models import AIModel, User
from ..schemas import (AIDiscoverIn, AIModelDraft, AIModelIn, AIModelOut, AIModelPublic, AIModelTestOut,
                       AIModelUpdate, AIProviderInfo)

router = APIRouter(prefix="/api/ai-models", tags=["ai models"])

# Changing any of these means the old test result no longer applies.
CONNECT_FIELDS = {"provider", "model", "base_url", "api_key"}


def to_out(m: AIModel) -> AIModelOut:
    return AIModelOut(id=m.id, name=m.name, provider=m.provider, provider_label=PROVIDERS[m.provider]["label"],
                      model=m.model, base_url=m.base_url, has_api_key=bool(m.api_key_encrypted),
                      is_active=m.is_active, is_default=m.is_default, status=m.status,
                      last_tested_at=m.last_tested_at, last_error=m.last_error,
                      created_at=m.created_at, updated_at=m.updated_at)


def bad_request(message: str) -> HTTPException:
    return HTTPException(status.HTTP_400_BAD_REQUEST, message)


def get_model(db: Session, model_id: int) -> AIModel:
    m = db.get(AIModel, model_id)
    if m is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "AI model not found")
    return m


def spec_of(m: AIModel) -> ModelSpec:
    """Raises crypto.ConnectionsKeyError if the saved key can't be decrypted."""
    return ModelSpec(provider=m.provider, model=m.model, base_url=m.base_url,
                     api_key=crypto.decrypt(m.api_key_encrypted))


def check_details(provider: str, base_url: str, has_key: bool):
    info = PROVIDERS[provider]
    if info["needs_base_url"] and not base_url.strip():
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Enter the server address")
    if info["needs_key"] and not has_key:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Enter the API key")


def check_name_free(db: Session, name: str, except_id: int | None = None):
    stmt = select(AIModel.id).where(func.lower(AIModel.name) == name.lower())
    if except_id is not None:
        stmt = stmt.where(AIModel.id != except_id)
    if db.scalar(stmt) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, f'A model called "{name}" already exists')


def make_only_default(db: Session, m: AIModel):
    db.execute(update(AIModel).where(AIModel.id != m.id).values(is_default=False))
    m.is_default = True


def saved_key(db: Session, model_id: int | None, given: str | None) -> str:
    """The key on the form, or the saved one when the form leaves it blank."""
    if given is not None:
        return given
    if model_id is None:
        return ""
    try:
        return crypto.decrypt(get_model(db, model_id).api_key_encrypted)
    except crypto.ConnectionsKeyError as err:
        raise bad_request(str(err))


@router.get("/providers", response_model=list[AIProviderInfo], dependencies=[Depends(require_manager)])
def providers():
    return [AIProviderInfo(id=k, label=v["label"], needs_base_url=v["needs_base_url"], needs_key=v["needs_key"],
                           default_base_url=v["default_base_url"],
                           suggested_models=CLAUDE_MODELS if k == "anthropic" else [])
            for k, v in PROVIDERS.items()]


@router.get("/available", response_model=list[AIModelPublic])
def available_models(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    """Active models for the picker in the Ask box. Names only: no addresses or keys."""
    rows = db.scalars(select(AIModel).where(AIModel.is_active.is_(True))
                      .order_by(AIModel.is_default.desc(), func.lower(AIModel.name))).all()
    return [AIModelPublic(id=m.id, name=m.name, provider=m.provider, provider_label=PROVIDERS[m.provider]["label"],
                          is_default=m.is_default) for m in rows]


@router.get("", response_model=list[AIModelOut], dependencies=[Depends(require_manager)])
def list_models(db: Session = Depends(get_db)):
    return [to_out(m) for m in db.scalars(select(AIModel).order_by(func.lower(AIModel.name))).all()]


@router.post("", response_model=AIModelOut, status_code=201)
def create_model(body: AIModelIn, db: Session = Depends(get_db), user: User = Depends(require_manager)):
    check_details(body.provider, body.base_url, bool(body.api_key))
    name = body.name.strip()
    check_name_free(db, name)
    try:
        key = crypto.encrypt(body.api_key or "")
    except crypto.ConnectionsKeyError as err:
        raise bad_request(str(err))
    m = AIModel(name=name, provider=body.provider, model=body.model.strip(), base_url=body.base_url.strip(),
                api_key_encrypted=key, is_active=body.is_active, created_by=user.id)
    db.add(m)
    db.flush()
    # The first active model becomes the default, so people get it without choosing.
    first = db.scalar(select(func.count(AIModel.id)).where(AIModel.is_default.is_(True))) == 0
    if m.is_active and (body.is_default or first):
        make_only_default(db, m)
    db.commit()
    return to_out(m)


@router.put("/{model_id}", response_model=AIModelOut, dependencies=[Depends(require_manager)])
def update_model(model_id: int, body: AIModelUpdate, db: Session = Depends(get_db)):
    m = get_model(db, model_id)
    changes = body.model_dump(exclude_unset=True)
    if changes.get("name") is not None:
        check_name_free(db, changes["name"].strip(), except_id=m.id)
        m.name = changes["name"].strip()
    for field in ("provider", "model", "base_url"):
        if changes.get(field) is not None:
            setattr(m, field, changes[field].strip())
    if changes.get("api_key") is not None:
        try:
            m.api_key_encrypted = crypto.encrypt(changes["api_key"])
        except crypto.ConnectionsKeyError as err:
            raise bad_request(str(err))
    check_details(m.provider, m.base_url, bool(m.api_key_encrypted))
    if changes.get("is_active") is not None:
        m.is_active = changes["is_active"]
        if not m.is_active:
            m.is_default = False  # a turned-off model can't be preselected
    if changes.get("is_default"):
        if not m.is_active:
            raise bad_request("Turn the model on before making it the default.")
        make_only_default(db, m)
    elif changes.get("is_default") is False:
        m.is_default = False
    if CONNECT_FIELDS & {k for k, v in changes.items() if v is not None}:
        m.status, m.last_error = "untested", ""
    db.commit()
    return to_out(m)


@router.delete("/{model_id}", status_code=204, dependencies=[Depends(require_manager)])
def delete_model(model_id: int, db: Session = Depends(get_db)):
    db.delete(get_model(db, model_id))
    db.commit()


@router.post("/test", response_model=AIModelTestOut, dependencies=[Depends(require_manager)])
def test_draft(body: AIModelDraft, db: Session = Depends(get_db)):
    """Sends a tiny request with the details on the form. Nothing is stored."""
    key = saved_key(db, body.id, body.api_key)
    check_details(body.provider, body.base_url, bool(key))
    return _run_test(ModelSpec(provider=body.provider, model=body.model.strip(), base_url=body.base_url, api_key=key))


@router.post("/{model_id}/test", response_model=AIModelTestOut, dependencies=[Depends(require_manager)])
def test_saved(model_id: int, db: Session = Depends(get_db)):
    """Tests a saved model and records the result on it."""
    m = get_model(db, model_id)
    try:
        spec = spec_of(m)
    except crypto.ConnectionsKeyError as err:
        raise bad_request(str(err))
    result = _run_test(spec)
    m.last_tested_at = datetime.now(timezone.utc)
    m.status, m.last_error = ("ok", "") if result.ok else ("error", result.message[:500])
    db.commit()
    return result


@router.post("/discover", response_model=list[str], dependencies=[Depends(require_manager)])
def discover_models(body: AIDiscoverIn, db: Session = Depends(get_db)):
    """The model ids the server offers, e.g. the models pulled into Ollama."""
    try:
        return discover(body.provider, body.base_url, saved_key(db, body.id, body.api_key))
    except AIError as err:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(err))


def _run_test(spec: ModelSpec) -> AIModelTestOut:
    try:
        ms, reply = ping(spec)
    except AIError as err:
        return AIModelTestOut(ok=False, message=str(err))
    return AIModelTestOut(ok=True, elapsed_ms=ms, message=f'Answered in {ms} ms ("{reply}").')
