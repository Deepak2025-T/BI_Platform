import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .db import init_db
from .routers import core, etl, reports

logging.basicConfig(level=logging.INFO)



@asynccontextmanager
async def lifespan(_app):
    init_db()
    yield


app = FastAPI(title="DTE — AI ETL + BI Report Platform", version="0.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.include_router(core.router)
app.include_router(reports.router)
app.include_router(etl.router)


@app.get("/api/health")
def health():
    return {"ok": True}
