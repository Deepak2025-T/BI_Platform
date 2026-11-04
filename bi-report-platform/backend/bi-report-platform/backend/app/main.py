import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .database import SessionLocal, schema_missing_message
from .refresh import scheduler
from .routers import (admin, ai_models, assistant, auth, categories, chats, connections, query, report_tools, reports,
                      schedules, templates, users)

for warning in settings.setup_warnings():
    logging.getLogger("uvicorn.error").warning("Setup: %s", warning)


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Refreshes reports on their schedules while the API runs (refresh.py). Set SCHEDULER_ENABLED=false
    to turn it off, for example on extra API processes when one is enough."""
    if settings.scheduler_enabled:
        scheduler.start()
    yield
    scheduler.stop()


app = FastAPI(title="BI Report Platform API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Tables come from Alembic migrations (alembic upgrade head), not from the app.
if (_problem := schema_missing_message()):
    raise RuntimeError(_problem)
with SessionLocal() as _db:
    templates.ensure_builtin_templates(_db)

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(query.router)
app.include_router(reports.router)
app.include_router(templates.router)
app.include_router(categories.router)
app.include_router(connections.router)
app.include_router(ai_models.router)
app.include_router(assistant.router)
app.include_router(chats.router)
app.include_router(schedules.router)
app.include_router(report_tools.router)
app.include_router(admin.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}
