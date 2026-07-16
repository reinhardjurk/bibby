"""Selbstverwaltung der Anmeldung per Magic-Link (Feature 2)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .. import services
from ..db import get_session
from ..models import Competition, Event, Participant, Payment, Registration
from ..routers.events import event_tshirt_options
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
    event = await session.get(Event, reg.event_id)
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
        event_id=reg.event_id,
        competition_lap_count=competition.lap_count,
        team=reg.team,
        suggested_team=await services.latest_team(session, reg.participant_id),
        tshirt=reg.tshirt,
        tshirt_options=event_tshirt_options(event),
        finish_seconds=reg.finish_seconds,
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
    if body.team is not None:
        reg.team = body.team.strip() or None  # leerer String = Team entfernen
    if body.tshirt is not None:
        reg.tshirt = body.tshirt or None
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
        background=event.bib_bg,
        background_mime=event.bib_bg_mime,
    )
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="startnummer-{reg.bib.bib_number}.pdf"'},
    )


@router.get("/certificate.pdf")
async def certificate_pdf(
    token: str = Query(...), session: AsyncSession = Depends(get_session)
) -> Response:
    """Teilnehmer-Urkunde mit Name und Zeit (auf der Event-Hintergrundvorlage)."""
    reg = await _resolve(token, session)
    if reg.finish_seconds is None:
        raise HTTPException(409, "Noch keine Laufzeit vorhanden")
    participant = await session.get(Participant, reg.participant_id)
    event = await session.get(Event, reg.event_id)
    competition = await session.get(Competition, reg.competition_id)

    # Vier Platzierungen für die Urkunde (gesamt/AK je insgesamt/Geschlecht).
    extra_lines: list[str] = []
    bib_text: str | None = None
    if reg.bib is not None:
        placement = await services.result_placement(session, competition, reg.bib.bib_number)
        extra_lines = services.certificate_lines(
            placement, reg.language, gender_scoring=competition.gender_scoring
        )
        bib_text = services.certificate_bib_text(reg.bib.bib_number, reg.language)

    pdf = services.render_certificate_pdf(
        first_name=participant.first_name,
        last_name=participant.last_name,
        time_text=services.format_duration(reg.finish_seconds),
        bib_text=bib_text,
        team=reg.team,
        extra_lines=extra_lines,
        background=event.certificate_bg,
        background_mime=event.certificate_bg_mime,
        offset_lines=event.certificate_offset,
    )
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="urkunde-{event.year}.pdf"'},
    )
