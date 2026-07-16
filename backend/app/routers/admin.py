"""Admin-SPA: Login (Magic-Link), RBAC-geschützte Verwaltung."""

from __future__ import annotations

import csv
import io
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile
from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from .. import crypto, services
from ..config import settings
from ..db import get_session
from ..models import (
    AppUser,
    AuthToken,
    BibAssignment,
    Competition,
    DeviceToken,
    Event,
    Participant,
    Payment,
    Registration,
    Sponsor,
    UserRole,
)
from ..routers.events import event_tshirt_options
from ..schemas import (
    AdminRegistrationDetail,
    AdminRegistrationUpdate,
    BibReassign,
    CompetitionUpdate,
    DeviceTokenCreate,
    EventCreate,
    EventUpdate,
    DeviceTokenOut,
    LoginRequest,
    MailModeUpdate,
    MailSettings,
    ParticipantMerge,
    ResultList,
    SessionToken,
    SponsorDisplayUpdate,
    SponsorTiersUpdate,
    SponsorUpdate,
)
from ..passwords import verify_password
from ..security import (
    generate_device_code,
    generate_token,
    hash_token,
    require_roles,
    user_roles,
)

router = APIRouter(prefix="/admin", tags=["admin"])

SESSION_TTL = timedelta(hours=72)


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


# --- Mail-Testmodus (Laufzeit-Schalter, kein Redeploy) --------------------
@router.get("/mail-settings", response_model=MailSettings)
async def get_mail_settings(
    _user=Depends(require_roles("admin", "race_office", "timing", "viewer")),
    session: AsyncSession = Depends(get_session),
) -> MailSettings:
    stored = await services.get_app_setting(session, services.MAIL_TEST_MODE_KEY)
    return MailSettings(
        test_mode=await services.get_mail_test_mode(session),
        test_recipient=settings.mail_test_recipient,
        overridden=stored is not None,
    )


@router.patch("/mail-settings", response_model=MailSettings)
async def update_mail_settings(
    body: MailModeUpdate,
    _user=Depends(require_roles("admin")),  # heikel: nur Admin darf Live schalten
    session: AsyncSession = Depends(get_session),
) -> MailSettings:
    await services.set_app_setting(
        session, services.MAIL_TEST_MODE_KEY, "true" if body.test_mode else "false"
    )
    await session.commit()
    return MailSettings(
        test_mode=body.test_mode,
        test_recipient=settings.mail_test_recipient,
        overridden=True,
    )


# --- Urkunden-Hintergrund hochladen ---------------------------------------
@router.post("/events/{event_id}/certificate-background")
async def upload_certificate_background(
    event_id: uuid.UUID,
    file: UploadFile = File(...),
    _user=Depends(require_roles("race_office")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Hintergrundvorlage (Bild) für die Teilnehmer-Urkunde speichern."""
    event = await session.get(Event, event_id)
    if event is None:
        raise HTTPException(404, "Event nicht gefunden")
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(422, "Bitte ein Bild hochladen (PNG oder JPG).")
    data = await file.read()
    if len(data) > 8_000_000:
        raise HTTPException(413, "Datei zu groß (max. 8 MB).")
    event.certificate_bg = data
    event.certificate_bg_mime = file.content_type
    await session.commit()
    return {"ok": True, "size": len(data)}


# --- Sponsoren (5 Klassen) ------------------------------------------------
@router.post("/sponsors")
async def upload_sponsor(
    tier: int = Form(...),
    name: str = Form(""),
    url: str = Form(""),
    file: UploadFile = File(...),
    _user=Depends(require_roles("race_office")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Logo in die Klasse `tier` (1..5) hochladen (optional mit Ziel-URL)."""
    if tier < 1 or tier > 5:
        raise HTTPException(422, "Klasse muss zwischen 1 und 5 liegen")
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(422, "Bitte ein Bild hochladen (PNG, JPG oder SVG).")
    data = await file.read()
    if len(data) > 2_000_000:
        raise HTTPException(413, "Datei zu groß (max. 2 MB).")
    data, mime = services.normalize_logo(data, file.content_type)
    sponsor = Sponsor(
        tier=tier,
        name=name.strip() or None,
        url=services.normalize_url(url),
        image=data,
        image_mime=mime,
    )
    session.add(sponsor)
    await session.commit()
    return {"id": str(sponsor.id), "tier": tier, "size": len(data)}


@router.patch("/sponsors/{sponsor_id}")
async def update_sponsor(
    sponsor_id: uuid.UUID,
    body: SponsorUpdate,
    _user=Depends(require_roles("race_office")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Name und/oder Ziel-URL eines bestehenden Logos ändern."""
    sponsor = await session.get(Sponsor, sponsor_id)
    if sponsor is None:
        raise HTTPException(404, "Sponsor nicht gefunden")
    if body.name is not None:
        sponsor.name = body.name.strip() or None
    if body.url is not None:
        sponsor.url = services.normalize_url(body.url)
    await session.commit()
    return {"ok": True}


@router.delete("/sponsors/{sponsor_id}")
async def delete_sponsor(
    sponsor_id: uuid.UUID,
    _user=Depends(require_roles("race_office")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    sponsor = await session.get(Sponsor, sponsor_id)
    if sponsor is None:
        raise HTTPException(404, "Sponsor nicht gefunden")
    await session.delete(sponsor)
    await session.commit()
    return {"ok": True}


@router.patch("/sponsor-tiers")
async def update_sponsor_tiers(
    body: SponsorTiersUpdate,
    _user=Depends(require_roles("race_office")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Gewicht (Zeitanteil) und Anzeigehöhe je Klasse setzen."""
    await services.set_sponsor_tiers(
        session, {k: v.model_dump() for k, v in body.tiers.items()}
    )
    await session.commit()
    return await services.get_sponsor_tiers(session)


@router.patch("/sponsor-display")
async def update_sponsor_display(
    body: SponsorDisplayUpdate,
    _user=Depends(require_roles("race_office")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Anzeigemodus der Sponsorenleiste: 'rotate' (ein Logo rotierend) oder
    'marquee' (Laufband)."""
    if body.mode not in ("rotate", "marquee"):
        raise HTTPException(422, "mode muss 'rotate' oder 'marquee' sein")
    await services.set_sponsor_display(session, body.mode)
    await session.commit()
    return {"display": body.mode}


# --- Ergebnisdruck: Urkunden ----------------------------------------------
_RESULT_ROLES = ("admin", "race_office", "timing", "viewer")


def _ak_sort_key(code: str | None) -> tuple:
    c = code or ""
    digits = "".join(ch for ch in c if ch.isdigit())
    return (int(digits) if digits else 999, 0 if c.startswith("U") else 1, c)


@router.get("/events/{event_id}/competitions/{competition_id}/certificate-groups")
async def certificate_groups(
    event_id: uuid.UUID,
    competition_id: uuid.UUID,
    _user=Depends(require_roles(*_RESULT_ROLES)),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    """Wertungsgruppen der Strecke: je nach Konfiguration nach Altersklasse
    (Schema der Strecke) und/oder Geschlecht, mit Finisher-Anzahl."""
    comp = await session.get(Competition, competition_id)
    if comp is None or comp.event_id != event_id:
        raise HTTPException(404, "Strecke gehört nicht zu diesem Event")
    rows = await services.build_results(session, comp, only_published=False)
    groups: dict[tuple[str | None, str | None], int] = {}
    for r in rows:
        if r.finish_seconds is None:
            continue
        key = (r.category_code, r.gender if comp.gender_scoring else None)
        groups[key] = groups.get(key, 0) + 1
    return [
        {"age_class": ak, "gender": g, "count": groups[(ak, g)]}
        for (ak, g) in sorted(groups, key=lambda k: (_ak_sort_key(k[0]), k[1] or ""))
    ]


async def _certificate_response(
    certs: list[dict], event: Event, filename: str, *, with_background: bool = True
) -> Response:
    """with_background=False -> nur Text auf weißem A4 (z. B. für vorgedrucktes
    Urkundenpapier)."""
    pdf = services.render_certificates_pdf(
        certs,
        background=event.certificate_bg if with_background else None,
        background_mime=event.certificate_bg_mime if with_background else None,
        offset_lines=event.certificate_offset,
    )
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )


@router.get("/events/{event_id}/competitions/{competition_id}/certificates")
async def certificate_bundle(
    event_id: uuid.UUID,
    competition_id: uuid.UUID,
    age_class: str = "",
    gender: str = "",
    lang: str = "de",
    background: bool = True,
    _user=Depends(require_roles(*_RESULT_ROLES)),
    session: AsyncSession = Depends(get_session),
) -> Response:
    """Sammel-PDF der Urkunden einer Wertungsgruppe (Altersklasse × Geschlecht,
    je nach Strecken-Konfiguration)."""
    comp = await session.get(Competition, competition_id)
    if comp is None or comp.event_id != event_id:
        raise HTTPException(404, "Strecke gehört nicht zu diesem Event")
    event = await session.get(Event, event_id)
    target = age_class or None
    target_gender = gender or None
    rows = await services.build_results(session, comp, only_published=False)
    certs = [
        {
            "first_name": r.first_name,
            "last_name": r.last_name,
            "time_text": services.format_duration(r.finish_seconds),
            "bib_text": services.certificate_bib_text(r.bib_number, lang),
            "team": r.team,
            "extra_lines": services.certificate_lines(
                services.placement_from_rows(rows, r.bib_number),
                lang,
                gender_scoring=comp.gender_scoring,
            ),
        }
        for r in rows
        if r.finish_seconds is not None
        and r.category_code == target
        and (target_gender is None or r.gender == target_gender)
    ]
    if not certs:
        raise HTTPException(404, "Keine Urkunden für diese Kombination")
    label = (comp.title_i18n or {}).get(lang) or (comp.title_i18n or {}).get("de") or "lauf"
    suffix = f"{target or 'ak'}{'-' + target_gender if target_gender else ''}"
    return await _certificate_response(
        certs, event, f"urkunden-{label}-{suffix}.pdf", with_background=background
    )


@router.get("/events/{event_id}/competitions/{competition_id}/certificates-all")
async def certificate_all(
    event_id: uuid.UUID,
    competition_id: uuid.UUID,
    lang: str = "de",
    background: bool = True,
    _user=Depends(require_roles(*_RESULT_ROLES)),
    session: AsyncSession = Depends(get_session),
) -> Response:
    """Alle Urkunden des Laufs in einem PDF, sortiert nach Altersklasse
    (aufsteigend) und Geschlecht (innerhalb der Gruppe nach Zeit)."""
    comp = await session.get(Competition, competition_id)
    if comp is None or comp.event_id != event_id:
        raise HTTPException(404, "Strecke gehört nicht zu diesem Event")
    event = await session.get(Event, event_id)
    rows = await services.build_results(session, comp, only_published=False)
    finishers = [r for r in rows if r.finish_seconds is not None]
    # Sortierung: Altersklasse aufsteigend, dann (nur bei Geschlechtswertung) nach
    # Geschlecht, und innerhalb der Gruppe die schlechteste Platzierung zuerst
    # (langsamste Zeit oben, Sieger zuletzt – Siegerehrungs-Reihenfolge).
    finishers.sort(
        key=lambda r: (
            _ak_sort_key(r.category_code),
            (r.gender or "") if comp.gender_scoring else "",
            -(r.finish_seconds or 0.0),
        )
    )
    if not finishers:
        raise HTTPException(404, "Keine Urkunden (keine Zeiten vorhanden)")
    certs = [
        {
            "first_name": r.first_name,
            "last_name": r.last_name,
            "time_text": services.format_duration(r.finish_seconds),
            "bib_text": services.certificate_bib_text(r.bib_number, lang),
            "team": r.team,
            "extra_lines": services.certificate_lines(
                services.placement_from_rows(rows, r.bib_number),
                lang,
                gender_scoring=comp.gender_scoring,
            ),
        }
        for r in finishers
    ]
    label = (comp.title_i18n or {}).get(lang) or (comp.title_i18n or {}).get("de") or "lauf"
    return await _certificate_response(
        certs, event, f"urkunden-{label}-alle.pdf", with_background=background
    )


@router.get("/events/{event_id}/certificate")
async def certificate_by_bib(
    event_id: uuid.UUID,
    bib: int,
    lang: str = "de",
    background: bool = True,
    _user=Depends(require_roles(*_RESULT_ROLES)),
    session: AsyncSession = Depends(get_session),
) -> Response:
    """Einzelne Urkunde für eine eingegebene Startnummer."""
    ba = (
        await session.execute(
            select(BibAssignment).where(
                BibAssignment.event_id == event_id, BibAssignment.bib_number == bib
            )
        )
    ).scalar_one_or_none()
    if ba is None:
        raise HTTPException(404, "Startnummer nicht gefunden")
    reg = await session.get(Registration, ba.registration_id)
    comp = await session.get(Competition, reg.competition_id)
    event = await session.get(Event, event_id)
    rows = await services.build_results(session, comp, only_published=False)
    me = next((r for r in rows if r.bib_number == bib), None)
    if me is None or me.finish_seconds is None:
        raise HTTPException(409, "Für diese Startnummer liegt noch keine Zeit vor")
    cert = {
        "first_name": me.first_name,
        "last_name": me.last_name,
        "time_text": services.format_duration(me.finish_seconds),
        "bib_text": services.certificate_bib_text(bib, lang),
        "team": me.team,
        "extra_lines": services.certificate_lines(
            services.placement_from_rows(rows, bib), lang, gender_scoring=comp.gender_scoring
        ),
    }
    return await _certificate_response(
        [cert], event, f"urkunde-{bib}.pdf", with_background=background
    )


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
            "competition_title": comp.title_i18n,
            "lap_count": comp.lap_count,
            "payment_method": payments[reg.id].method if reg.id in payments else None,
            "payment_status": payments[reg.id].status if reg.id in payments else None,
            "finish_seconds": reg.finish_seconds,
        }
        for reg, part, comp, bib in rows
    ]
    return {"total": total, "items": items}


@router.post("/events/{event_id}/recompute-times")
async def recompute_times(
    event_id: uuid.UUID,
    _user=Depends(require_roles("race_office")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Berechnet alle persönlichen Laufzeiten (Erfassungszeit − Startzeit) neu."""
    updated = await services.recompute_event_times(session, event_id)
    return {"updated": updated}


async def _registration_detail(
    session: AsyncSession, registration_id: uuid.UUID
) -> AdminRegistrationDetail | None:
    reg = await session.get(Registration, registration_id)
    if reg is None:
        return None
    participant = await session.get(Participant, reg.participant_id)
    competition = await session.get(Competition, reg.competition_id)
    event = await session.get(Event, reg.event_id)
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
        tshirt=reg.tshirt,
        tshirt_options=event_tshirt_options(event),
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
    if body.tshirt is not None:
        reg.tshirt = body.tshirt or None
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


@router.post("/events/{event_id}/sepa-export")
async def sepa_export(
    event_id: uuid.UUID,
    include_exported: bool = False,
    _user=Depends(require_roles("race_office")),
    session: AsyncSession = Depends(get_session),
) -> Response:
    """CSV der offenen SEPA-Lastschriften (Name, IBAN, Betrag). Standardmäßig nur
    noch nicht exportierte; mit include_exported=true auch bereits exportierte.
    Markiert die enthaltenen Zahlungen mit dem Export-Zeitpunkt."""
    event = await session.get(Event, event_id)
    if event is None:
        raise HTTPException(404, "Event nicht gefunden")

    conds = [
        Registration.event_id == event_id,
        Payment.method == "sepa_debit",
        Payment.status == "pending",
    ]
    if not include_exported:
        conds.append(Payment.sepa_exported_at.is_(None))

    rows = (
        await session.execute(
            select(Payment, Participant, BibAssignment)
            .join(Registration, Registration.id == Payment.registration_id)
            .join(Participant, Participant.id == Registration.participant_id)
            .outerjoin(BibAssignment, BibAssignment.registration_id == Registration.id)
            .where(*conds)
            .order_by(BibAssignment.bib_number)
        )
    ).all()

    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=";")
    writer.writerow(
        [
            "Startnummer",
            "Teilnehmer",
            "Kontoinhaber",
            "IBAN",
            "Betrag",
            "Waehrung",
            "Mandatsreferenz",
            "Mandatsdatum",
            "Verwendungszweck",
        ]
    )
    now = datetime.now(timezone.utc)
    for pay, part, bib in rows:
        name = f"{part.first_name} {part.last_name}"
        iban = crypto.decrypt(pay.iban_encrypted) if pay.iban_encrypted else ""
        writer.writerow(
            [
                bib.bib_number if bib else "",
                name,
                pay.account_holder or name,
                iban,
                f"{pay.amount_cents / 100:.2f}",
                pay.currency,
                pay.mandate_reference or "",
                pay.mandate_granted_at.date().isoformat() if pay.mandate_granted_at else "",
                f"Startgeld {event.name} {event.year} - {name}",
            ]
        )
        pay.sepa_exported_at = now

    await session.commit()
    filename = f"sepa-export-{event.year}-{now.strftime('%Y%m%d-%H%M%S')}.csv"
    # BOM voranstellen, damit Excel UTF-8 (Umlaute) korrekt erkennt.
    return Response(
        content="﻿" + buf.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# --- Strecken / Startzeiten -----------------------------------------------
@router.patch("/competitions/{competition_id}")
async def update_competition(
    competition_id: uuid.UUID,
    body: CompetitionUpdate,
    _user=Depends(require_roles("race_office")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Setzt u. a. die absolute Startzeit einer Strecke (für die Laufzeit)."""
    comp = await session.get(Competition, competition_id)
    if comp is None:
        raise HTTPException(404, "Strecke nicht gefunden")
    if "start_time" in body.model_fields_set:
        comp.start_time = body.start_time
    if body.price_cents is not None:
        comp.price_cents = body.price_cents
    if "price_junior_cents" in body.model_fields_set:
        comp.price_junior_cents = body.price_junior_cents
    if body.age_class_scheme is not None:
        comp.age_class_scheme = body.age_class_scheme
    if body.gender_scoring is not None:
        comp.gender_scoring = body.gender_scoring
    await session.commit()
    return {
        "id": str(comp.id),
        "lap_count": comp.lap_count,
        "start_time": comp.start_time.isoformat() if comp.start_time else None,
        "price_cents": comp.price_cents,
        "price_junior_cents": comp.price_junior_cents,
        "currency": comp.currency,
    }


# --- Neues Event anlegen --------------------------------------------------
@router.post("/events", status_code=201)
async def create_event(
    body: EventCreate,
    _user=Depends(require_roles("race_office")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Legt ein komplett neues Event mit Strecken an. Bestehende Events und deren
    Daten bleiben unberührt (jahresübergreifende Historie)."""
    if not body.competitions:
        raise HTTPException(422, "Mindestens eine Strecke erforderlich")

    event = Event(
        name=body.name,
        year=body.year,
        event_date=body.event_date,
        registration_deadline=body.registration_deadline,
        default_start_time=body.default_start_time,
        junior_cutoff_date=body.junior_cutoff_date,
        tshirt_included=body.tshirt_included,
        tshirt_options=body.tshirt_options or None,
    )
    session.add(event)
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(409, "Für dieses Jahr existiert bereits ein Event")

    for c in body.competitions:
        title_i18n = {"de": c.title, "en": c.title} if c.title else None
        session.add(
            Competition(
                event_id=event.id,
                lap_count=c.lap_count,
                title_i18n=title_i18n,
                start_time=c.start_time,
                price_cents=c.price_cents,
                price_junior_cents=c.price_junior_cents,
                currency=c.currency,
                age_class_scheme=c.age_class_scheme,
                gender_scoring=c.gender_scoring,
            )
        )
    await session.commit()
    return {"id": str(event.id), "year": event.year, "name": event.name}


@router.delete("/events/{event_id}")
async def delete_event(
    event_id: uuid.UUID,
    _user=Depends(require_roles("admin")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Löscht ein Event samt allen abhängigen Daten (Anmeldungen, Zahlungen,
    Startnummern, Zeiterfassungen, Strecken, Geräte-Tokens) über DB-Kaskaden.
    Teilnehmer-Identitäten bleiben erhalten. Nur für die Rolle `admin`."""
    event = await session.get(Event, event_id)
    if event is None:
        raise HTTPException(404, "Event nicht gefunden")
    await session.execute(delete(Event).where(Event.id == event_id))
    await session.commit()
    return {"ok": True}


# --- Event-Einstellungen (T-Shirt-Optionen) -------------------------------
@router.patch("/events/{event_id}")
async def update_event(
    event_id: uuid.UUID,
    body: EventUpdate,
    _user=Depends(require_roles("race_office")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    event = await session.get(Event, event_id)
    if event is None:
        raise HTTPException(404, "Event nicht gefunden")
    if "tshirt_options" in body.model_fields_set:
        # leere Liste = wieder auf Default zurückfallen
        event.tshirt_options = body.tshirt_options or None
    if "junior_cutoff_date" in body.model_fields_set:
        event.junior_cutoff_date = body.junior_cutoff_date
    if body.tshirt_included is not None:
        event.tshirt_included = body.tshirt_included
    if body.certificate_offset is not None:
        event.certificate_offset = body.certificate_offset
    await session.commit()
    return {
        "id": str(event.id),
        "tshirt_options": event_tshirt_options(event),
        "junior_cutoff_date": event.junior_cutoff_date.isoformat()
        if event.junior_cutoff_date
        else None,
        "tshirt_included": event.tshirt_included,
    }


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
            token=t.token_plain,  # dauerhaft sichtbar (kann für Altdaten None sein)
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
    # Kurzer, menschenlesbarer Code; bei (sehr seltener) Kollision neu würfeln.
    raw = generate_device_code()
    for _ in range(10):
        clash = (
            await session.execute(
                select(DeviceToken.id).where(DeviceToken.token_hash == hash_token(raw))
            )
        ).scalar_one_or_none()
        if clash is None:
            break
        raw = generate_device_code()
    token = DeviceToken(
        event_id=event_id,
        label=body.label,
        token_hash=hash_token(raw),
        token_plain=raw,
        time_offset_seconds=body.time_offset_seconds,
    )
    session.add(token)
    await session.commit()
    return DeviceTokenOut(
        id=token.id,
        label=token.label,
        token=raw,
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
