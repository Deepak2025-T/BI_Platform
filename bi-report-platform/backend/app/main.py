import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .config import settings
from .database import SessionLocal, schema_missing_message
from .refresh import scheduler
from .routers import (admin, ai_models, assistant, auth, categories, chats, connections, data_models, query,
                      report_tools, reports, palettes, schedules, shares, templates, uploads, users, visuals)

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

@app.exception_handler(Exception)
async def unhandled(request: Request, err: Exception):
    """Anything that got past a route, said in a way the page can show.

    FastAPI's own answer to an unhandled error is the plain text "Internal Server Error", which
    carries no "detail" - so the browser falls back to "Something went wrong. Try again.", and the
    person is left with nothing to act on and nothing to tell anyone. The traceback is logged
    where it belongs, and what comes back names the kind of failure and where it happened.
    """
    logging.getLogger("uvicorn.error").exception("unhandled error on %s %s",
                                                 request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail":
        f"The server hit an error it did not expect: {type(err).__name__}: {str(err)[:300]} "
        f"(on {request.method} {request.url.path}). The full trace is in the server log."})


# Tables come from Alembic migrations (alembic upgrade head), not from the app.
if (_problem := schema_missing_message()):
    raise RuntimeError(_problem)
with SessionLocal() as _db:
    templates.ensure_builtin_templates(_db)

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(query.router)
app.include_router(reports.router)
app.include_router(shares.router)
app.include_router(templates.router)
app.include_router(categories.router)
app.include_router(palettes.router)
app.include_router(connections.router)
app.include_router(data_models.router)
app.include_router(ai_models.router)
app.include_router(assistant.router)
app.include_router(chats.router)
app.include_router(schedules.router)
app.include_router(report_tools.router)
app.include_router(visuals.router)
app.include_router(uploads.router)
app.include_router(admin.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}


# ---------- The built frontend, when one has been built ----------
#
# With a web server in front of this (nginx serving frontend/dist), none of the below is reached.
# With nothing in front, the API serves the app itself: one process on one port, and the browser
# calls /api on the origin it was loaded from - so there is no proxy to configure and no CORS to
# get wrong. Useful on a server without nginx, and for a quick look at a real build.
#
# This is registered last on purpose. Routes match in the order they were added, so every /api
# route above is matched before the catch-all below ever sees the request.

FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend" / "dist"


def _serves_frontend() -> bool:
    return (FRONTEND_DIR / "index.html").is_file()


if _serves_frontend():
    if (FRONTEND_DIR / "assets").is_dir():
        # Content-hashed filenames, so the browser may keep them.
        app.mount("/assets", StaticFiles(directory=FRONTEND_DIR / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        """Anything that is not the API is the single-page app.

        A file that exists is served as itself (the logo, the icon); anything else is index.html,
        because /reports/114 is a route inside the app and only the browser knows that. index.html
        itself is never cached, or a browser would go on loading yesterday's bundle after a deploy.
        """
        if path.startswith("api/"):
            # A mistyped API path is a 404, not a page: answering with HTML would have the client
            # trying to read a document as JSON.
            raise HTTPException(status.HTTP_404_NOT_FOUND, "No such endpoint.")
        candidate = (FRONTEND_DIR / path).resolve()
        if path and candidate.is_relative_to(FRONTEND_DIR) and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(FRONTEND_DIR / "index.html", headers={"Cache-Control": "no-cache"})
