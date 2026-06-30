"""Öffentliche Lese-Endpunkte für Events/Wettbewerbe (für die SPA)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_session
from ..models import Competition, Event, Registration

router = APIRouter(tags=["events"])


@router.get("/teams")
async def list_teams(session: AsyncSession = Depends(get_session)) -> list[str]:
    """Bereits vergebene Teamnamen – für die Autovervollständigung im Team-Feld."""
    return list(
        (
            await session.execute(
                select(Registration.team)
                .where(Registration.team.isnot(None))
                .distinct()
                .order_by(Registration.team)
            )
        ).scalars().all()
    )


@router.get("/events")
async def list_events(session: AsyncSession = Depends(get_session)) -> list[dict]:
    rows = (
        await session.execute(select(Event).order_by(Event.year.desc()))
    ).scalars().all()
    return [
        {
            "id": str(e.id),
            "name": e.name,
            "year": e.year,
            "event_date": e.event_date.isoformat(),
            "registration_deadline": e.registration_deadline.isoformat()
            if e.registration_deadline
            else None,
        }
        for e in rows
    ]


@router.get("/events/{event_id}/competitions")
async def list_competitions(
    event_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> list[dict]:
    event = await session.get(Event, event_id)
    if event is None:
        raise HTTPException(404, "Event nicht gefunden")
    rows = (
        await session.execute(
            select(Competition)
            .where(Competition.event_id == event_id)
            .order_by(Competition.lap_count)
        )
    ).scalars().all()
    return [
        {
            "id": str(c.id),
            "lap_count": c.lap_count,
            "title_i18n": c.title_i18n,
            "price_cents": c.price_cents,
            "currency": c.currency,
        }
        for c in rows
    ]
