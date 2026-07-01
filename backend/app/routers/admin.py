"""Admin-SPA: Login (Magic-Link), RBAC-geschützte Verwaltung."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from .. import services
from ..db import get_session
from ..models import (
    AppUser,
    AuthToken,
    BibAssignment,
    Competition,
    DeviceToken,
    Participant,
    Payment,
    Registration,
    UserRole,
)
from ..schemas import (
    BibReassign,
    DeviceTokenCreate,
    DeviceTokenOut,
    LoginRequest,
    ParticipantMerge,
    ResultList,
    SessionToken,
)
from ..passwords import verify_password
from ..security import generate_token, hash_token, require_roles, user_roles

router = APIRouter(prefix="/admin", tags=["admin"])

SESSION_TTL = timedelta(hours=12)


@router.post("/auth/login", response_model=SessionToken)
async def login(body: LoginRequest, session: AsyncSession = Depends(get_session)) -> SessionToken:
    """Passwortbasierter Login. Bei Erfolg wird ein Session-Token ausgegeben."""
    user = (
        await session.execute(select(AppUser).where(AppUser.email == body.email))
    ).scalar_one_or_none()
    # Generische Fehlermeldung, kein User-Enumeration-Leak.
    if (
        user is None
        or not user.active
        or user.password_hash is None
        or not verify_password(body.password, user.password_hash)
    ):
        raise HTTPException(401, "E-Mail oder Passwort falsch")

    expires_at = datetime.now(timezone.utc) + SESSION_TTL
    raw = generate_token()
    session.add(AuthToken(user_id=user.id, token_hash=hash_token(raw), expires_at=expires_at))
    await session.commit()
    roles = await user_roles(session, user.id)
    return SessionToken(token=raw, expires_at=expires_at, roles=sorted(roles))


@router.get("/me", response_model=SessionToken)
async def me(
    user: AppUser = Depends(require_roles("admin", "race_office", "timing", "viewer")),
    session: AsyncSession = Depends(get_session),
) -> SessionToken:
    roles = await user_roles(session, user.id)
    return SessionToken(token="(current)", expires_at=datetime.now(timezone.utc), roles=sorted(roles))


# --- Anmeldungen auflisten ------------------------------------------------
@router.get("/registrations")
async def list_registrations(
    event_id: uuid.UUID,
    _user=Depends(require_roles("admin", "race_office", "timing", "viewer")),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    rows = (
        await session.execute(
            select(Registration, Participant, Competition, BibAssignment, Payment)
            .join(Participant, Participant.id == Registration.participant_id)
            .join(Competition, Competition.id == Registration.competition_id)
            .outerjoin(BibAssignment, BibAssignment.registration_id == Registration.id)
            .outerjoin(Payment, Payment.registration_id == Registration.id)
            .where(Registration.event_id == event_id)
            .order_by(BibAssignment.bib_number)
        )
    ).all()
    return [
        {
            "id": str(reg.id),
            "first_name": part.first_name,
            "last_name": part.last_name,
            "email": reg.email,
            "status": reg.status,
            "bib_number": bib.bib_number if bib else None,
            "competition_id": str(comp.id),
            "lap_count": comp.lap_count,
            "payment_method": pay.method if pay else None,
            "payment_status": pay.status if pay else None,
        }
        for reg, part, comp, bib, pay in rows
    ]


# --- Interne Ergebnisliste (inkl. nicht-veröffentlichter Läufer) ----------
@router.get("/events/{event_id}/results", response_model=ResultList)
async def internal_results(
    event_id: uuid.UUID,
    competition_id: uuid.UUID,
    _user=Depends(require_roles("admin", "race_office", "timing", "viewer")),
    session: AsyncSession = Depends(get_session),
) -> ResultList:
    """Vollständige Wertung – im Gegensatz zur öffentlichen Liste auch Läufer
    ohne Veröffentlichungs-Einwilligung (mit `published=false` markiert)."""
    competition = await session.get(Competition, competition_id)
    if competition is None or competition.event_id != event_id:
        raise HTTPException(404, "Wettbewerb nicht gefunden")
    rows = await services.build_results(session, competition, only_published=False)
    return ResultList(
        event_id=event_id,
        competition_id=competition_id,
        lap_count=competition.lap_count,
        rows=rows,
    )


# --- Startnummern ---------------------------------------------------------
@router.post("/registrations/{registration_id}/bib")
async def assign_bib(
    registration_id: uuid.UUID,
    bib_number: int,
    _user=Depends(require_roles("race_office")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    reg = await session.get(Registration, registration_id)
    if reg is None:
        raise HTTPException(404, "Anmeldung nicht gefunden")
    existing = (
        await session.execute(
            select(BibAssignment).where(BibAssignment.registration_id == registration_id)
        )
    ).scalar_one_or_none()
    if existing:
        existing.bib_number = bib_number
    else:
        session.add(
            BibAssignment(event_id=reg.event_id, bib_number=bib_number, registration_id=reg.id)
        )
    try:
        await session.commit()
    except Exception:
        await session.rollback()
        raise HTTPException(409, "Startnummer im Event bereits vergeben")
    return {"ok": True}


@router.post("/registrations/{registration_id}/reassign")
async def reassign_competition(
    registration_id: uuid.UUID,
    body: BibReassign,
    _user=Depends(require_roles("race_office")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Hängt die Startnummer auf eine andere Strecke (Rundenzahl) um.

    Da Timing auf bib_number läuft, bleiben alle Erfassungen erhalten; nur die
    Auswertung (Zielrunde) verschiebt sich entsprechend der neuen Rundenzahl.
    """
    reg = await session.get(Registration, registration_id)
    if reg is None:
        raise HTTPException(404, "Anmeldung nicht gefunden")
    reg.competition_id = body.competition_id
    await session.commit()
    return {"ok": True}


# --- Zahlung ---------------------------------------------------------------
@router.post("/registrations/{registration_id}/payment/mark-paid")
async def mark_paid(
    registration_id: uuid.UUID,
    _user=Depends(require_roles("race_office")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Markiert die Zahlung als bezahlt (Barzahlung bei Abholung bzw. nach
    erfolgtem Lastschrifteinzug)."""
    payment = (
        await session.execute(
            select(Payment)
            .where(Payment.registration_id == registration_id)
            .order_by(Payment.created_at.desc())
        )
    ).scalars().first()
    if payment is None:
        raise HTTPException(404, "Keine Zahlung gefunden")
    payment.status = "paid"
    await session.commit()
    return {"ok": True}


# --- Teilnehmer mergen ----------------------------------------------------
@router.post("/participants/merge")
async def merge_participants(
    body: ParticipantMerge,
    _user=Depends(require_roles("race_office")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Führt zwei Teilnehmer-Datensätze zusammen (Fehl-Match bei Name+Geburtsdatum).

    Alle Anmeldungen der Quelle werden auf das Ziel umgehängt, die Quelle gelöscht.
    """
    if body.source_participant_id == body.target_participant_id:
        raise HTTPException(422, "Quelle und Ziel sind identisch")
    target = await session.get(Participant, body.target_participant_id)
    if target is None:
        raise HTTPException(404, "Ziel-Teilnehmer nicht gefunden")
    await session.execute(
        update(Registration)
        .where(Registration.participant_id == body.source_participant_id)
        .values(participant_id=body.target_participant_id)
    )
    await session.execute(delete(Participant).where(Participant.id == body.source_participant_id))
    await session.commit()
    return {"ok": True}


# --- Geräte-Tokens für die Zeitnahme -------------------------------------
@router.get("/events/{event_id}/device-tokens", response_model=list[DeviceTokenOut])
async def list_device_tokens(
    event_id: uuid.UUID,
    _user=Depends(require_roles("timing")),
    session: AsyncSession = Depends(get_session),
) -> list[DeviceTokenOut]:
    rows = (
        await session.execute(
            select(DeviceToken)
            .where(DeviceToken.event_id == event_id)
            .order_by(DeviceToken.label)
        )
    ).scalars().all()
    return [
        DeviceTokenOut(
            id=t.id,
            label=t.label,
            token=None,  # Klartext gibt es nur bei der Erstellung
            time_offset_seconds=t.time_offset_seconds,
            active=t.active,
        )
        for t in rows
    ]


@router.post("/events/{event_id}/device-tokens", response_model=DeviceTokenOut)
async def create_device_token(
    event_id: uuid.UUID,
    body: DeviceTokenCreate,
    _user=Depends(require_roles("timing")),
    session: AsyncSession = Depends(get_session),
) -> DeviceTokenOut:
    raw = generate_token()
    token = DeviceToken(
        event_id=event_id,
        label=body.label,
        token_hash=hash_token(raw),
        time_offset_seconds=body.time_offset_seconds,
    )
    session.add(token)
    await session.commit()
    return DeviceTokenOut(
        id=token.id,
        label=token.label,
        token=raw,  # Klartext nur jetzt
        time_offset_seconds=token.time_offset_seconds,
        active=token.active,
    )


@router.delete("/device-tokens/{token_id}")
async def revoke_device_token(
    token_id: uuid.UUID,
    _user=Depends(require_roles("timing")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    token = await session.get(DeviceToken, token_id)
    if token is None:
        raise HTTPException(404, "Token nicht gefunden")
    token.active = False
    await session.commit()
    return {"ok": True}
