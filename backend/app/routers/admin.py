"""Admin-SPA: Login (Magic-Link), RBAC-geschützte Verwaltung."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.exc import IntegrityError
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
    AdminRegistrationDetail,
    AdminRegistrationUpdate,
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


# --- Anmeldungen auflisten (paginiert + Suche) ----------------------------
@router.get("/registrations")
async def list_registrations(
    event_id: uuid.UUID,
    q: str | None = None,
    limit: int = 50,
    offset: int = 0,
    _user=Depends(require_roles("admin", "race_office", "timing", "viewer")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    limit = max(1, min(limit, 200))  # Deckel gegen zu große Seiten

    conds = [Registration.event_id == event_id]
    # Suche nach Name (Teilstring) oder Startnummer.
    if q and q.strip():
        term = q.strip().lower()
        like = f"%{term}%"
        oc = [
            func.lower(Participant.first_name).like(like),
            func.lower(Participant.last_name).like(like),
        ]
        if term.isdigit():
            oc.append(BibAssignment.bib_number == int(term))
        conds.append(or_(*oc))

    # Gesamtzahl (für die Seitennavigation). Bib/Participant sind 1:1, keine
    # Zeilenvervielfachung -> Count bleibt korrekt.
    total = (
        await session.execute(
            select(func.count())
            .select_from(Registration)
            .join(Participant, Participant.id == Registration.participant_id)
            .outerjoin(BibAssignment, BibAssignment.registration_id == Registration.id)
            .where(*conds)
        )
    ).scalar_one()

    # Eine Seite. Payment bewusst NICHT gejoint (könnte Zeilen vervielfachen und
    # damit limit/offset verfälschen); wird separat je Seite nachgeladen.
    rows = (
        await session.execute(
            select(Registration, Participant, Competition, BibAssignment)
            .join(Participant, Participant.id == Registration.participant_id)
            .join(Competition, Competition.id == Registration.competition_id)
            .outerjoin(BibAssignment, BibAssignment.registration_id == Registration.id)
            .where(*conds)
            .order_by(BibAssignment.bib_number)
            .limit(limit)
            .offset(offset)
        )
    ).all()

    reg_ids = [reg.id for reg, _p, _c, _b in rows]
    payments: dict = {}
    if reg_ids:
        for p in (
            await session.execute(
                select(Payment)
                .where(Payment.registration_id.in_(reg_ids))
                .order_by(Payment.created_at.desc())
            )
        ).scalars().all():
            payments.setdefault(p.registration_id, p)  # erster = neuester

    items = [
        {
            "id": str(reg.id),
            "first_name": part.first_name,
            "last_name": part.last_name,
            "email": reg.email,
            "status": reg.status,
            "bib_number": bib.bib_number if bib else None,
            "competition_id": str(comp.id),
            "lap_count": comp.lap_count,
            "payment_method": payments[reg.id].method if reg.id in payments else None,
            "payment_status": payments[reg.id].status if reg.id in payments else None,
        }
        for reg, part, comp, bib in rows
    ]
    return {"total": total, "items": items}


async def _registration_detail(
    session: AsyncSession, registration_id: uuid.UUID
) -> AdminRegistrationDetail | None:
    reg = await session.get(Registration, registration_id)
    if reg is None:
        return None
    participant = await session.get(Participant, reg.participant_id)
    competition = await session.get(Competition, reg.competition_id)
    bib = (
        await session.execute(
            select(BibAssignment).where(BibAssignment.registration_id == reg.id)
        )
    ).scalar_one_or_none()
    payment = (
        await session.execute(
            select(Payment)
            .where(Payment.registration_id == reg.id)
            .order_by(Payment.created_at.desc())
        )
    ).scalars().first()
    return AdminRegistrationDetail(
        id=reg.id,
        first_name=participant.first_name,
        last_name=participant.last_name,
        birth_date=participant.birth_date,
        gender=participant.gender,
        email=reg.email,
        language=reg.language,
        team=reg.team,
        consent_data=reg.consent_data,
        consent_publish=reg.consent_publish,
        status=reg.status,
        bib_number=bib.bib_number if bib else None,
        event_id=reg.event_id,
        competition_id=reg.competition_id,
        lap_count=competition.lap_count,
        payment_method=payment.method if payment else None,
        payment_status=payment.status if payment else None,
        payment_iban_masked=payment.iban_masked if payment else None,
    )


@router.get("/registrations/{registration_id}", response_model=AdminRegistrationDetail)
async def registration_detail(
    registration_id: uuid.UUID,
    _user=Depends(require_roles("admin", "race_office", "timing", "viewer")),
    session: AsyncSession = Depends(get_session),
) -> AdminRegistrationDetail:
    detail = await _registration_detail(session, registration_id)
    if detail is None:
        raise HTTPException(404, "Anmeldung nicht gefunden")
    return detail


@router.patch("/registrations/{registration_id}", response_model=AdminRegistrationDetail)
async def update_registration(
    registration_id: uuid.UUID,
    body: AdminRegistrationUpdate,
    _user=Depends(require_roles("race_office")),
    session: AsyncSession = Depends(get_session),
) -> AdminRegistrationDetail:
    """Voll-Bearbeitung einer Anmeldung durch das Race-Office."""
    reg = await session.get(Registration, registration_id)
    if reg is None:
        raise HTTPException(404, "Anmeldung nicht gefunden")
    participant = await session.get(Participant, reg.participant_id)

    # Teilnehmer-Identität – wirkt auf alle Anmeldungen dieser Person (Korrektur).
    ident_changed = False
    if body.first_name is not None:
        participant.first_name = body.first_name.strip()
        ident_changed = True
    if body.last_name is not None:
        participant.last_name = body.last_name.strip()
        ident_changed = True
    if body.birth_date is not None:
        participant.birth_date = body.birth_date
        ident_changed = True
    if body.gender is not None:
        if body.gender not in ("f", "m", "x"):
            raise HTTPException(422, "Ungültiges Geschlecht")
        participant.gender = body.gender
    if ident_changed:
        participant.match_key = services.build_match_key(
            participant.last_name, participant.first_name, participant.birth_date
        )

    # Anmeldung
    if body.email is not None:
        reg.email = body.email
    if body.language is not None:
        reg.language = body.language
    if body.team is not None:
        reg.team = body.team.strip() or None
    if body.consent_data is not None:
        reg.consent_data = body.consent_data
    if body.consent_publish is not None:
        reg.consent_publish = body.consent_publish
    if body.status is not None:
        if body.status not in ("confirmed", "cancelled"):
            raise HTTPException(422, "Ungültiger Status")
        reg.status = body.status
    if body.competition_id is not None:
        comp = await session.get(Competition, body.competition_id)
        if comp is None or comp.event_id != reg.event_id:
            raise HTTPException(422, "Wettbewerb gehört nicht zu diesem Event")
        reg.competition_id = body.competition_id

    # Startnummer
    if body.bib_number is not None:
        bib = (
            await session.execute(
                select(BibAssignment).where(BibAssignment.registration_id == reg.id)
            )
        ).scalar_one_or_none()
        if bib:
            bib.bib_number = body.bib_number
        else:
            session.add(
                BibAssignment(
                    event_id=reg.event_id, bib_number=body.bib_number, registration_id=reg.id
                )
            )

    # Zahlung
    if body.payment_method is not None or body.payment_status is not None:
        payment = (
            await session.execute(
                select(Payment)
                .where(Payment.registration_id == reg.id)
                .order_by(Payment.created_at.desc())
            )
        ).scalars().first()
        if payment is None:
            raise HTTPException(404, "Keine Zahlung vorhanden")
        if body.payment_method is not None:
            if body.payment_method not in ("sepa_debit", "on_site"):
                raise HTTPException(422, "Ungültige Zahlungsart")
            payment.method = body.payment_method
        if body.payment_status is not None:
            if body.payment_status not in ("pending", "paid", "cancelled"):
                raise HTTPException(422, "Ungültiger Zahlungsstatus")
            payment.status = body.payment_status

    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            409, "Konflikt: Name/Geburtsdatum oder Startnummer bereits vergeben"
        )

    detail = await _registration_detail(session, registration_id)
    assert detail is not None
    return detail


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
