"""Öffentliche Lese-Endpunkte für Events/Wettbewerbe (für die SPA)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..db import get_session
from ..models import Competition, Event, Registration

router = APIRouter(tags=["events"])


def event_tshirt_options(event: Event) -> list[str]:
    return event.tshirt_options or settings.default_tshirt_options


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
    # Bewusst nur Skalar-Spalten (nicht das ganze Event-Objekt), damit der
    # Urkunden-Hintergrund (BYTEA) NICHT bei jedem /events-Aufruf geladen wird –
    # nur ein Flag, ob einer hinterlegt ist.
    rows = (
        await session.execute(
            select(
                Event.id,
                Event.name,
                Event.year,
                Event.event_date,
                Event.registration_deadline,
                Event.tshirt_options,
                Event.junior_cutoff_date,
                Event.tshirt_included,
                Event.certificate_bg.isnot(None),
                Event.certificate_offset,
            ).order_by(Event.year.desc())
        )
    ).all()
    return [
        {
            "id": str(r.id),
            "name": r.name,
            "year": r.year,
            "event_date": r.event_date.isoformat(),
            "registration_deadline": r.registration_deadline.isoformat()
            if r.registration_deadline
            else None,
            "tshirt_options": r.tshirt_options or settings.default_tshirt_options,
            "junior_cutoff_date": r.junior_cutoff_date.isoformat() if r.junior_cutoff_date else None,
            "tshirt_included": r.tshirt_included,
            "has_certificate_background": r[8],
            "certificate_offset": r.certificate_offset,
        }
        for r in rows
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
            "price_junior_cents": c.price_junior_cents,
            "currency": c.currency,
            "start_time": c.start_time.isoformat() if c.start_time else None,
        }
        for c in rows
    ]
