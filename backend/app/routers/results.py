"""Ergebnislisten (Feature 4)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from .. import services
from ..db import get_session
from ..models import Competition
from ..schemas import ResultList

router = APIRouter(tags=["results"])


@router.get("/events/{event_id}/results", response_model=ResultList)
async def results(
    event_id: uuid.UUID,
    competition_id: uuid.UUID = Query(...),
    session: AsyncSession = Depends(get_session),
) -> ResultList:
    """Öffentliche Ergebnisliste eines Wettbewerbs, inkl. Splits, Altersklasse
    und jahresübergreifendem Teilnahmezähler."""
    competition = await session.get(Competition, competition_id)
    if competition is None or competition.event_id != event_id:
        raise HTTPException(404, "Wettbewerb nicht gefunden")

    rows = await services.build_results(session, competition)
    return ResultList(
        event_id=event_id,
        competition_id=competition_id,
        lap_count=competition.lap_count,
        rows=rows,
    )
