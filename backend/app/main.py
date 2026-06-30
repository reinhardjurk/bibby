"""Bibby API — FastAPI-App (Deployment als Scaleway Serverless Container)."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
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
