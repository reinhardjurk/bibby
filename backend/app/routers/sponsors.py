"""Öffentliche Sponsoren-Endpunkte (Liste + Bildauslieferung).

Bewusst getrennt: die Liste enthält NUR Metadaten (kein Bild-Blob), damit der
Seitenaufbau kaum belastet wird. Die Bilder werden einzeln und lazy geladen und
sind aggressiv cachebar.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .. import services
from ..db import get_session
from ..models import Sponsor

router = APIRouter(tags=["sponsors"])


@router.get("/sponsors")
async def list_sponsors(session: AsyncSession = Depends(get_session)) -> dict:
    """Klassen-Konfiguration + Logo-Metadaten (ohne Bilddaten)."""
    rows = (
        await session.execute(
            select(Sponsor.id, Sponsor.tier, Sponsor.name, Sponsor.url).order_by(
                Sponsor.tier, Sponsor.created_at
            )
        )
    ).all()
    return {
        "tiers": await services.get_sponsor_tiers(session),
        "display": await services.get_sponsor_display(session),
        "marquee_seconds": await services.get_marquee_seconds(session),
        "items": [
            {"id": str(r.id), "tier": r.tier, "name": r.name, "url": r.url} for r in rows
        ],
    }


@router.get("/sponsors/{sponsor_id}/image")
async def sponsor_image(
    sponsor_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> Response:
    sponsor = await session.get(Sponsor, sponsor_id)
    if sponsor is None:
        raise HTTPException(404, "Sponsor nicht gefunden")
    return Response(
        content=sponsor.image,
        media_type=sponsor.image_mime,
        # Inhalt je ID unveränderlich -> lange cachen, entlastet den Container.
        headers={"Cache-Control": "public, max-age=604800, immutable"},
    )
