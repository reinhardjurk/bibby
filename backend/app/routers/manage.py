"""Selbstverwaltung der Anmeldung per Magic-Link (Feature 2)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .. import services
from ..db import get_session
from ..models import Competition, Event, Participant, Payment, Registration
from ..schemas import ManageView, RegistrationOut, RegistrationUpdate
from ..security import hash_token

router = APIRouter(prefix="/manage", tags=["manage"])


async def _resolve(token: str, session: AsyncSession) -> Registration:
    reg = (
        await session.execute(
            select(Registration).where(Registration.manage_token_hash == hash_token(token))
        )
    ).scalar_one_or_none()
    if reg is None:
        raise HTTPException(404, "Ungültiger Verwaltungslink")
    return reg


@router.get("", response_model=ManageView)
async def view(token: str = Query(...), session: AsyncSession = Depends(get_session)) -> ManageView:
    reg = await _resolve(token, session)
    participant = await session.get(Participant, reg.participant_id)
    competition = await session.get(Competition, reg.competition_id)
    payment = (
        await session.execute(
            select(Payment).where(Payment.registration_id == reg.id).order_by(Payment.created_at.desc())
        )
    ).scalars().first()

    return ManageView(
        registration=RegistrationOut(
            id=reg.id,
            status=reg.status,
            competition_id=reg.competition_id,
            bib_number=reg.bib.bib_number if reg.bib else None,
        ),
        first_name=participant.first_name,
        last_name=participant.last_name,
        email=reg.email,
        competition_lap_count=competition.lap_count,
        payment_method=payment.method if payment else None,
        payment_status=payment.status if payment else None,
        payment_iban_masked=payment.iban_masked if payment else None,
        mandate_reference=payment.mandate_reference if payment else None,
    )


@router.patch("", response_model=RegistrationOut)
async def update(
    body: RegistrationUpdate,
    token: str = Query(...),
    session: AsyncSession = Depends(get_session),
) -> RegistrationOut:
    reg = await _resolve(token, session)
    if body.competition_id is not None:
        comp = await session.get(Competition, body.competition_id)
        if comp is None or comp.event_id != reg.event_id:
            raise HTTPException(422, "Wettbewerb gehört nicht zu diesem Event")
        reg.competition_id = body.competition_id
    if body.email is not None:
        reg.email = body.email
    if body.language is not None:
        reg.language = body.language
    if body.consent_publish is not None:
        reg.consent_publish = body.consent_publish
    await session.commit()
    return RegistrationOut(
        id=reg.id,
        status=reg.status,
        competition_id=reg.competition_id,
        bib_number=reg.bib.bib_number if reg.bib else None,
    )


@router.get("/bib.pdf")
async def bib_pdf(token: str = Query(...), session: AsyncSession = Depends(get_session)) -> Response:
    """Startnummer als PDF zum Ausdrucken."""
    reg = await _resolve(token, session)
    if reg.bib is None:
        raise HTTPException(409, "Noch keine Startnummer vergeben")
    participant = await session.get(Participant, reg.participant_id)
    competition = await session.get(Competition, reg.competition_id)
    event = await session.get(Event, reg.event_id)

    pdf = services.render_bib_pdf(
        bib_number=reg.bib.bib_number,
        first_name=participant.first_name,
        last_name=participant.last_name,
        event_name=event.name,
        year=event.year,
        competition_title=services.competition_label(competition, reg.language),
    )
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="startnummer-{reg.bib.bib_number}.pdf"'},
    )
