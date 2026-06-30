"""Zeiterfassung (Feature 3): idempotente Ingestion + Korrektur."""

from __future__ import annotations

import uuid
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from .. import services
from ..db import get_session
from ..models import DeviceToken, TimingRecord
from ..schemas import TimingBatch, TimingBatchResult, TimingCorrection
from ..security import require_device_token, require_roles

router = APIRouter(tags=["timing"])


@router.post("/events/{event_id}/timings", response_model=TimingBatchResult)
async def ingest(
    event_id: uuid.UUID,
    batch: TimingBatch,
    device: DeviceToken = Depends(require_device_token),
    session: AsyncSession = Depends(get_session),
) -> TimingBatchResult:
    """Nimmt Linien-Überquerungen entgegen (Web-Maske oder CV-App).

    Idempotent über (event_id, dedup_key): wiederholte Pings (Offline-Puffer)
    werden ignoriert. Der Geräte-Offset wird auf die Gerätezeit angewandt.
    Anschließend werden die Runden der betroffenen Startnummern neu berechnet.
    """
    if device.event_id != event_id:
        raise HTTPException(403, "Geräte-Token gehört zu einem anderen Event")

    offset = timedelta(seconds=device.time_offset_seconds)
    accepted = 0
    affected_bibs: set[int] = set()

    for ping in batch.pings:
        stmt = (
            insert(TimingRecord)
            .values(
                event_id=event_id,
                bib_number=ping.bib_number,
                absolute_time=ping.absolute_time + offset,
                source_token_id=device.id,
                dedup_key=ping.dedup_key,
                status="valid",
                raw_payload=ping.raw_payload,
            )
            .on_conflict_do_nothing(index_elements=["event_id", "dedup_key"])
        )
        result = await session.execute(stmt)
        if result.rowcount:
            accepted += 1
            affected_bibs.add(ping.bib_number)

    for bib in affected_bibs:
        await services.recompute_laps(session, event_id, bib)

    await session.commit()
    return TimingBatchResult(accepted=accepted, duplicates=len(batch.pings) - accepted)


@router.patch("/timings/{record_id}")
async def correct(
    record_id: uuid.UUID,
    body: TimingCorrection,
    _user=Depends(require_roles("timing")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Manuelle Korrektur einer Überquerung (Rolle `timing`)."""
    rec = await session.get(TimingRecord, record_id)
    if rec is None:
        raise HTTPException(404, "Datensatz nicht gefunden")
    if body.bib_number is not None:
        rec.bib_number = body.bib_number
    if body.absolute_time is not None:
        rec.absolute_time = body.absolute_time
    rec.status = body.status
    await services.recompute_laps(session, rec.event_id, rec.bib_number)
    await session.commit()
    return {"ok": True}


@router.get("/events/{event_id}/timings/{bib_number}")
async def list_for_bib(
    event_id: uuid.UUID,
    bib_number: int,
    _user=Depends(require_roles("timing", "race_office", "viewer")),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    """Alle Überquerungen einer Startnummer (für die Korrekturansicht)."""
    rows = (
        await session.execute(
            select(TimingRecord)
            .where(TimingRecord.event_id == event_id, TimingRecord.bib_number == bib_number)
            .order_by(TimingRecord.absolute_time)
        )
    ).scalars().all()
    return [
        {
            "id": str(r.id),
            "absolute_time": r.absolute_time.isoformat(),
            "lap_index": r.lap_index,
            "status": r.status,
        }
        for r in rows
    ]
