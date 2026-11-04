from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..ai.interpreter import interpret_with_model
from ..ai.providers import AIError, ModelSpec
from ..connections import crypto
from ..database import get_db
from ..deps import get_current_user
from ..models import AIModel, User
from ..query_engine import GenerationFailed, interpret_prompt, run_query
from ..schemas import GenerateIn, QueryParams

router = APIRouter(prefix="/api/query", tags=["query"])


@router.post("/generate")
def generate(body: GenerateIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Question -> understanding + SQL + result, using the chosen AI model or the built-in engine."""
    model = _chosen_model(db, body.model_id)
    try:
        params, notes = (body.params, []) if body.params else _understand(body.prompt, model)
    except GenerationFailed as e:
        raise HTTPException(422, {"reason": e.reason, "attempts": e.attempts, "last_sql": e.last_sql,
                                  "can_edit_sql": user.role == "manager"})
    result = run_query(db, params)
    result["attempts"] = notes + [{"ok": True, "message": "The query only reads data and ran successfully."}]
    result["model"] = model.name if model and notes and notes[0]["ok"] else None
    result["needs_confirmation"] = None if body.params else {
        "kind": "date_col",
        "message": f"Two date columns could fit. I used {params.date_col}. sale_date is when the sale happened; "
                   "invoice_date is when the customer was billed.",
        "options": ["sale_date", "invoice_date"],
    }
    return result


def _chosen_model(db: Session, model_id: int | None) -> AIModel | None:
    if model_id is None:
        return None
    model = db.get(AIModel, model_id)
    if model is None or not model.is_active:
        raise HTTPException(400, "That AI model has been turned off or removed. Pick another one.")
    return model


def _understand(prompt: str, model: AIModel | None) -> tuple[QueryParams, list[dict]]:
    """Reads the question with the AI model, falling back to the built-in engine if the model can't be used."""
    builtin = {"ok": True, "message": "Read with the built-in keyword engine (no AI model)."}
    if model is None:
        return interpret_prompt(prompt), [builtin]
    try:
        spec = ModelSpec(provider=model.provider, model=model.model, base_url=model.base_url,
                         api_key=crypto.decrypt(model.api_key_encrypted))
        params, note = interpret_with_model(spec, model.name, prompt)
        return params, [note]
    except (AIError, crypto.ConnectionsKeyError) as err:
        fallback = {"ok": False, "message": f"{model.name} couldn't be used ({err}). "
                                            "Used the built-in keyword engine instead."}
        return interpret_prompt(prompt), [fallback]


@router.post("/run")
def run(params: QueryParams, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    """Re-runs a saved query with new filter values. No AI involved."""
    return run_query(db, params)
