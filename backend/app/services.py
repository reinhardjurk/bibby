"""Domänenlogik: Teilnehmer-Matching, Rundenableitung, Ergebnisberechnung.

Der TEM-Mailversand ist als klar gekennzeichneter Stub implementiert und wird
später gegen die echte API ausgetauscht.
"""

from __future__ import annotations

import unicodedata
import uuid
from datetime import date, datetime

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from .config import settings
from .models import (
    BibAssignment,
    Category,
    Competition,
    Event,
    Participant,
    Registration,
    TimingRecord,
)
from .schemas import LapSplit, ResultRow


# =========================================================================
# Teilnehmer-Identität über Jahre hinweg (Name + Geburtsdatum)
# =========================================================================
def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    return " ".join(text.lower().split())


def build_match_key(last_name: str, first_name: str, birth_date: date) -> str:
    return f"{_normalize(last_name)}|{_normalize(first_name)}|{birth_date.isoformat()}"


async def get_or_create_participant(
    session: AsyncSession,
    *,
    first_name: str,
    last_name: str,
    birth_date: date,
    gender: str,
) -> Participant:
    key = build_match_key(last_name, first_name, birth_date)
    existing = (
        await session.execute(select(Participant).where(Participant.match_key == key))
    ).scalar_one_or_none()
    if existing:
        return existing
    participant = Participant(
        match_key=key,
        first_name=first_name,
        last_name=last_name,
        birth_date=birth_date,
        gender=gender,
    )
    session.add(participant)
    await session.flush()
    return participant


async def assign_next_bib(
    session: AsyncSession, event_id: uuid.UUID, registration_id: uuid.UUID
) -> int:
    """Vergibt die nächste fortlaufende Startnummer im Event und legt die
    Zuordnung an (ohne Commit).

    Ein transaktionsgebundener Advisory-Lock pro Event serialisiert die Vergabe,
    sodass parallele Anmeldungen keine doppelten Nummern erhalten. Der Lock wird
    mit der Transaktion automatisch wieder freigegeben.
    """
    await session.execute(
        text("SELECT pg_advisory_xact_lock(hashtext(:k))"), {"k": f"bib:{event_id}"}
    )
    max_bib = (
        await session.execute(
            select(func.max(BibAssignment.bib_number)).where(
                BibAssignment.event_id == event_id
            )
        )
    ).scalar()
    next_bib = max_bib + 1 if max_bib is not None else settings.bib_start_number
    session.add(
        BibAssignment(event_id=event_id, bib_number=next_bib, registration_id=registration_id)
    )
    await session.flush()
    return next_bib


async def latest_team(session: AsyncSession, participant_id: uuid.UUID) -> str | None:
    """Letzte (nicht-leere) Teamzugehörigkeit dieser Person über alle Anmeldungen
    – wird auf der Verwaltungsseite als Vorschlag angeboten."""
    return (
        await session.execute(
            select(Registration.team)
            .where(
                Registration.participant_id == participant_id,
                Registration.team.isnot(None),
            )
            .order_by(Registration.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


async def participation_count(session: AsyncSession, participant_id: uuid.UUID) -> int:
    """Anzahl Events, an denen die Person teilgenommen hat (für „X. Teilnahme")."""
    return (
        await session.execute(
            select(func.count(func.distinct(Registration.event_id))).where(
                Registration.participant_id == participant_id,
                Registration.status == "confirmed",
            )
        )
    ).scalar_one()


# =========================================================================
# Altersklassen
# =========================================================================
async def resolve_category(
    session: AsyncSession, event: Event, participant: Participant
) -> str | None:
    age = event.event_date.year - participant.birth_date.year
    cats = (
        await session.execute(select(Category).where(Category.event_id == event.id))
    ).scalars().all()
    for c in cats:
        if c.gender and c.gender != participant.gender:
            continue
        if c.min_age is not None and age < c.min_age:
            continue
        if c.max_age is not None and age > c.max_age:
            continue
        return c.code
    return None


# =========================================================================
# Rundenableitung
# =========================================================================
async def recompute_laps(session: AsyncSession, event_id: uuid.UUID, bib_number: int) -> None:
    """Vergibt lap_index für alle Überquerungen einer Startnummer neu.

    Regeln:
    - Nur Records mit status in ('valid','manual') zählen.
    - Records, die < min_lap_seconds nach der letzten gezählten Überquerung
      liegen, werden als 'duplicate' markiert (Doppelerfassung / Prellen).
    - Aufruf nach jedem Ingestion-Batch bzw. nach manueller Korrektur.
    """
    records = (
        await session.execute(
            select(TimingRecord)
            .where(
                TimingRecord.event_id == event_id,
                TimingRecord.bib_number == bib_number,
                TimingRecord.status.in_(("valid", "manual", "duplicate")),
            )
            .order_by(TimingRecord.absolute_time)
        )
    ).scalars().all()

    lap = 0
    last_counted: datetime | None = None
    for rec in records:
        if rec.status == "manual":
            # Manuell gesetzte Records werden immer gezählt.
            lap += 1
            rec.lap_index = lap
            last_counted = rec.absolute_time
            continue
        too_close = (
            last_counted is not None
            and (rec.absolute_time - last_counted).total_seconds() < settings.min_lap_seconds
        )
        if too_close:
            rec.status = "duplicate"
            rec.lap_index = None
        else:
            rec.status = "valid"
            lap += 1
            rec.lap_index = lap
            last_counted = rec.absolute_time


# =========================================================================
# Ergebnisliste pro Wettbewerb
# =========================================================================
async def build_results(
    session: AsyncSession, competition: Competition, *, only_published: bool = True
) -> list[ResultRow]:
    """Ergebnisliste eines Wettbewerbs.

    Die Ränge werden über das gesamte Finisher-Feld berechnet (Platzierungen
    bleiben korrekt). Mit `only_published=True` (öffentliche Liste) werden
    anschließend Läufer ohne Veröffentlichungs-Einwilligung herausgefiltert.
    """
    event = await session.get(Event, competition.event_id)
    start = competition.start_time or event.default_start_time

    regs = (
        await session.execute(
            select(Registration, BibAssignment, Participant)
            .join(BibAssignment, BibAssignment.registration_id == Registration.id)
            .join(Participant, Participant.id == Registration.participant_id)
            .where(
                Registration.competition_id == competition.id,
                Registration.status == "confirmed",
            )
        )
    ).all()

    rows: list[ResultRow] = []
    for reg, bib, participant in regs:
        crossings = (
            await session.execute(
                select(TimingRecord)
                .where(
                    TimingRecord.event_id == competition.event_id,
                    TimingRecord.bib_number == bib.bib_number,
                    TimingRecord.lap_index.isnot(None),
                )
                .order_by(TimingRecord.lap_index)
            )
        ).scalars().all()

        splits: list[LapSplit] = []
        finish_seconds: float | None = None
        if start is not None:
            for c in crossings:
                elapsed = (c.absolute_time - start).total_seconds()
                splits.append(LapSplit(lap_index=c.lap_index, elapsed_seconds=elapsed))
                if c.lap_index == competition.lap_count:
                    finish_seconds = elapsed

        rows.append(
            ResultRow(
                rank=None,  # nach Sortierung gesetzt
                bib_number=bib.bib_number,
                first_name=participant.first_name,
                last_name=participant.last_name,
                category_code=await resolve_category(session, event, participant),
                finish_seconds=finish_seconds,
                splits=splits,
                participation_count=await participation_count(session, participant.id),
                published=reg.consent_publish,
            )
        )

    # Sortierung: Finisher nach Zeit, DNF ans Ende. Rang nur für Finisher.
    rows.sort(key=lambda r: (r.finish_seconds is None, r.finish_seconds or 0.0))
    rank = 0
    for r in rows:
        if r.finish_seconds is not None:
            rank += 1
            r.rank = rank

    return [r for r in rows if r.published or not only_published]


# =========================================================================
# Externe Integrationen (STUBS)
# =========================================================================
# =========================================================================
# SEPA-Lastschrift
# =========================================================================
def validate_iban(raw: str) -> str:
    """Prüft eine IBAN (Format + Prüfsumme mod 97) und gibt sie normalisiert
    (ohne Leerzeichen, Großbuchstaben) zurück. Wirft ValueError bei Fehler."""
    import re

    s = raw.replace(" ", "").upper()
    if not re.fullmatch(r"[A-Z0-9]{15,34}", s):
        raise ValueError("Ungültiges IBAN-Format")
    rearranged = s[4:] + s[:4]
    digits = "".join(str(ord(c) - 55) if c.isalpha() else c for c in rearranged)
    if int(digits) % 97 != 1:
        raise ValueError("IBAN-Prüfsumme ungültig")
    return s


def generate_mandate_reference(year: int) -> str:
    return f"BIBBY-{year}-{uuid.uuid4().hex[:8].upper()}"


async def send_confirmation_email(registration: Registration, manage_token: str) -> None:
    """STUB: verschickt Bestätigungsmail mit Verwaltungslink über Scaleway TEM."""
    link = f"{settings.public_base_url}/manage?token={manage_token}"
    print(f"[TEM stub] -> {registration.email} ({registration.language}): {link}")


# =========================================================================
# Startnummern-PDF (WeasyPrint)
# =========================================================================
def render_bib_pdf(
    *,
    bib_number: int,
    first_name: str,
    last_name: str,
    event_name: str,
    year: int,
    competition_title: str,
) -> bytes:
    """Rendert die Startnummer als A5-PDF (quer). WeasyPrint wird erst hier
    importiert, damit Pfade ohne PDF-Erzeugung die System-Libs nicht brauchen."""
    from weasyprint import HTML

    html = f"""
    <html><head><meta charset="utf-8"><style>
      @page {{ size: A5 landscape; margin: 10mm; }}
      body {{ font-family: Helvetica, Arial, sans-serif; text-align: center; color: #1c2430; }}
      .event {{ font-size: 14pt; color: #6b7785; letter-spacing: 2px; text-transform: uppercase; }}
      .bib {{ font-size: 150pt; font-weight: 800; line-height: 1; margin: 8mm 0; color: #2f6df0; }}
      .name {{ font-size: 24pt; font-weight: 600; }}
      .comp {{ font-size: 14pt; color: #6b7785; margin-top: 4mm; }}
    </style></head><body>
      <div class="event">{event_name} &middot; {year}</div>
      <div class="bib">{bib_number}</div>
      <div class="name">{first_name} {last_name}</div>
      <div class="comp">{competition_title}</div>
    </body></html>
    """
    return HTML(string=html).write_pdf()


def competition_label(competition: Competition, lang: str = "de") -> str:
    """Anzeigename eines Wettbewerbs: title_i18n falls vorhanden, sonst Rundenzahl."""
    if competition.title_i18n and competition.title_i18n.get(lang):
        return competition.title_i18n[lang]
    runden = "Runde" if competition.lap_count == 1 else "Runden"
    return f"{competition.lap_count} {runden}"
