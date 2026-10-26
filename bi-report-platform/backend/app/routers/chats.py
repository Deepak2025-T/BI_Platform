"""
Saved chat conversations. Each person sees only their own chats.

Every question and its answer (or error) is stored, so a chat can be reopened and continued later.
Follow-up questions use the saved turns as context, read from the database, not sent by the browser.
"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..ai.assistant import chat
from ..database import get_db
from ..deps import get_current_user
from ..models import ChatConversation, ChatMessage, User, now_utc
from .assistant import _ai_call, _model, _source

router = APIRouter(prefix="/api/chats", tags=["chat history"])

NEW_TITLE = "New chat"
HISTORY_TURNS = 6  # earlier answered turns given to the model as context
LIST_LIMIT = 100


class ChatCreate(BaseModel):
    source_id: int | None = None
    model_id: int | None = None
    title: str = Field(default=NEW_TITLE, min_length=1, max_length=120)


class ChatUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=120)
    model_id: int | None = None


class MessageIn(BaseModel):
    question: str = Field(min_length=2, max_length=2000)
    # The model for this question; leave out to use the chat's model.
    model_id: int | None = None


class MessageOut(BaseModel):
    id: int
    question: str
    status: str
    result: dict | None
    error: str
    model_name: str
    created_at: datetime


class ChatSummary(BaseModel):
    id: int
    title: str
    source_id: int | None
    source_name: str
    model_id: int | None
    message_count: int
    created_at: datetime
    updated_at: datetime


class ChatOut(ChatSummary):
    messages: list[MessageOut]


def _own(db: Session, chat_id: int, user: User) -> ChatConversation:
    c = db.get(ChatConversation, chat_id)
    if c is None or c.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Chat not found")
    return c


def _message_out(m: ChatMessage) -> MessageOut:
    return MessageOut(id=m.id, question=m.question, status=m.status, result=m.result, error=m.error,
                      model_name=m.model_name, created_at=m.created_at)


def _out(c: ChatConversation) -> ChatOut:
    return ChatOut(id=c.id, title=c.title, source_id=c.source_id, source_name=c.source_name, model_id=c.model_id,
                   message_count=len(c.messages), created_at=c.created_at, updated_at=c.updated_at,
                   messages=[_message_out(m) for m in c.messages])


@router.get("", response_model=list[ChatSummary])
def list_chats(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    counts = (select(ChatMessage.conversation_id, func.count(ChatMessage.id).label("n"))
              .group_by(ChatMessage.conversation_id).subquery())
    rows = db.execute(select(ChatConversation, func.coalesce(counts.c.n, 0))
                      .outerjoin(counts, counts.c.conversation_id == ChatConversation.id)
                      .where(ChatConversation.user_id == user.id)
                      .order_by(ChatConversation.updated_at.desc()).limit(LIST_LIMIT)).all()
    return [ChatSummary(id=c.id, title=c.title, source_id=c.source_id, source_name=c.source_name, model_id=c.model_id,
                        message_count=n, created_at=c.created_at, updated_at=c.updated_at) for c, n in rows]


@router.post("", response_model=ChatOut, status_code=201)
def start_chat(body: ChatCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    source = _source(db, body.source_id)  # checks the database can be used
    c = ChatConversation(user_id=user.id, title=body.title.strip(), source_id=source.id, source_name=source.name,
                         model_id=body.model_id)
    db.add(c)
    db.commit()
    return _out(c)


@router.get("/{chat_id}", response_model=ChatOut)
def get_chat(chat_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return _out(_own(db, chat_id, user))


@router.patch("/{chat_id}", response_model=ChatSummary)
def update_chat(chat_id: int, body: ChatUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    c = _own(db, chat_id, user)
    if body.title is not None:
        c.title = body.title.strip()
    if "model_id" in body.model_fields_set:
        c.model_id = body.model_id
    db.commit()
    out = _out(c)
    return ChatSummary(**out.model_dump(exclude={"messages"}))


@router.delete("/{chat_id}", status_code=204)
def delete_chat(chat_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    db.delete(_own(db, chat_id, user))
    db.commit()


@router.post("/{chat_id}/messages", response_model=MessageOut, status_code=201)
def send_message(chat_id: int, body: MessageIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Asks the AI model and saves the turn. A failed answer is saved too, with its error, so the
    chat shows exactly what happened; the response is then status "error" rather than an HTTP error."""
    c = _own(db, chat_id, user)
    model_id = body.model_id or c.model_id
    history = [{"question": m.question, "reply": (m.result or {}).get("reply", ""), "sql": (m.result or {}).get("sql", "")}
               for m in c.messages if m.status == "ok"][-HISTORY_TURNS:]
    message = ChatMessage(conversation_id=c.id, question=body.question.strip(), status="ok", error="")
    try:
        if model_id is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Pick an AI model for this chat.")
        model, spec = _model(db, model_id)
        message.model_name = model.name
        source = _source(db, c.source_id)
        result = _ai_call(chat, spec, source, message.question, history)
        message.result = {**result, "model": model.name, "source": source.name}
        c.model_id = model.id
    except HTTPException as err:
        message.status, message.error = "error", str(err.detail)[:1000]
    if c.title == NEW_TITLE and not c.messages:
        c.title = message.question[:80]
    c.updated_at = now_utc()  # moves the chat to the top of the list
    db.add(message)
    db.commit()
    return _message_out(message)
