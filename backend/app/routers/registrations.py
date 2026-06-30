"""Anmeldung (Feature 1) inkl. Zahlungsweg (SEPA-Mandat oder Barzahlung)."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from .. import crypto, services
from ..db import get_session
from ..models import Competition, Event, Payment, Registration
from ..schemas import RegistrationCreate, RegistrationOut
from ..security import generate_token, hash_token

router = APIRouter(tags=["registration"])


@router.post("/registrations", response_model=RegistrationOut, status_code=201)
async def create_registration(
    body: RegistrationCreate, session: AsyncSession = Depends(get_session)
) -> RegistrationOut:
    if not body.consent_data:
        raise HTTPException(422, "Einwilligung zur Datenverarbeitung erforderlich")

    competition = await session.get(Competition, body.competition_id)
    if competition is None or competition.event_id != body.event_id:
        raise HTTPException(404, "Wettbewerb nicht gefunden")

    # Zahlungsweg validieren
    iban: str | None = None
    if body.payment_method == "sepa_debit":
        if not (body.iban and body.account_holder and body.mandate_consent):
            raise HTTPException(
                422, "IBAN, Kontoinhaber und Mandatserteilung sind für SEPA erforderlich"
            )
        try:
            iban = services.validate_iban(body.iban)
        except ValueError as exc:
            raise HTTPException(422, str(exc))

    participant = await services.get_or_create_participant(
        session,
        first_name=body.first_name,
        last_name=body.last_name,
        birth_date=body.birth_date,
        gender=body.gender,
    )

    raw_token = generate_token()
    registration = Registration(
        event_id=body.event_id,
        competition_id=body.competition_id,
        participant_id=participant.id,
        email=body.email,
        language=body.language,
        team=(body.team or "").strip() or None,
        manage_token_hash=hash_token(raw_token),
        consent_data=body.consent_data,
        consent_publish=body.consent_publish,
    )
    session.add(registration)
    try:
        await session.flush()
    except Exception:  # UNIQUE(event_id, participant_id)
        await session.rollback()
        raise HTTPException(409, "Diese Person ist für dieses Event bereits angemeldet")

    # Startnummer fortlaufend vergeben
    bib_number = await services.assign_next_bib(session, registration.event_id, registration.id)

    # Zahlung anlegen
    event = await session.get(Event, body.event_id)
    mandate_reference: str | None = None
    payment = Payment(
        registration_id=registration.id,
        method=body.payment_method,
        amount_cents=competition.price_cents,
        currency=competition.currency,
        status="pending",
    )
    if body.payment_method == "sepa_debit":
        mandate_reference = services.generate_mandate_reference(event.year)
        payment.iban_encrypted = crypto.encrypt(iban)
        payment.iban_masked = crypto.mask_iban(iban)
        payment.account_holder = body.account_holder
        payment.mandate_reference = mandate_reference
        payment.mandate_granted_at = datetime.now(timezone.utc)
    session.add(payment)

    await services.send_confirmation_email(registration, raw_token)
    await session.commit()

    return RegistrationOut(
        id=registration.id,
        status=registration.status,
        competition_id=registration.competition_id,
        bib_number=bib_number,
        manage_token=raw_token,
        mandate_reference=mandate_reference,
    )
