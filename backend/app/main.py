"""Bibby API — FastAPI-App (Deployment als Scaleway Serverless Container)."""

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from .config import settings
from .db import get_session
from .routers import admin, events, manage, registrations, results, timing

app = FastAPI(title="Bibby API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(events.router)
app.include_router(registrations.router)
app.include_router(manage.router)
app.include_router(timing.router)
app.include_router(results.router)
app.include_router(admin.router)


@app.get("/health", tags=["meta"])
async def health() -> dict:
    return {"status": "ok"}


@app.get("/version", tags=["meta"])
async def version(session: AsyncSession = Depends(get_session)) -> dict:
    """Backend-Build + aktuelle DB-Schema-Revision (aus alembic_version)."""
    try:
        db_schema = (
            await session.execute(text("SELECT version_num FROM alembic_version"))
        ).scalar_one_or_none()
    except Exception:  # noqa: BLE001 – Tabelle fehlt lokal ggf. -> einfach None
        db_schema = None
    return {"backend": settings.build, "db_schema": db_schema}
