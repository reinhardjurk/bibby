"""Bibby API — FastAPI-App (Deployment als Scaleway Serverless Container)."""

import logging

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from .config import settings
from .db import get_session
from .routers import admin, events, manage, registrations, results, sponsors, timing

logger = logging.getLogger("bibby")

app = FastAPI(title="Bibby API", version="0.1.0")


# Fehler-Fangnetz: fängt unbehandelte Exceptions als 500-Response ab. Wichtig ist
# die Reihenfolge – dieses Middleware wird VOR CORS registriert und liegt dadurch
# INNERHALB der CORS-Middleware. Nur so bekommt auch eine 500-Antwort die
# CORS-Header; sonst blockt der Browser sie und meldet nur "load failed", statt
# den echten Fehler anzuzeigen.
@app.middleware("http")
async def catch_unhandled_errors(request: Request, call_next):
    try:
        return await call_next(request)
    except Exception:  # noqa: BLE001 – bewusst alles abfangen und als 500 melden
        logger.exception("Unbehandelter Fehler bei %s %s", request.method, request.url.path)
        return JSONResponse(status_code=500, content={"detail": "Internal Server Error"})


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
app.include_router(sponsors.router)
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
