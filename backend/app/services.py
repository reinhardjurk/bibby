"""Domänenlogik: Teilnehmer-Matching, Rundenableitung, Ergebnisberechnung.

Der TEM-Mailversand ist als klar gekennzeichneter Stub implementiert und wird
später gegen die echte API ausgetauscht.
"""

from __future__ import annotations

import unicodedata
import uuid
from collections.abc import Iterable
from datetime import date, datetime, timedelta

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from . import mailer
from .config import settings
from .models import (
    AppSetting,
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


def compute_price_cents(event: Event, competition: Competition, birth_date: date) -> int:
    """Startgeld für Strecke + Altersgruppe. Wer am/nach event.junior_cutoff_date
    geboren ist, zahlt price_junior_cents (falls gesetzt), sonst den Standardpreis."""
    is_junior = event.junior_cutoff_date is not None and birth_date >= event.junior_cutoff_date
    if is_junior and competition.price_junior_cents is not None:
        return competition.price_junior_cents
    return competition.price_cents


# =========================================================================
# Rundenableitung
# =========================================================================
def _mean_datetime(times: list[datetime]) -> datetime:
    """Mittelwert mehrerer Zeitpunkte (numerisch stabil über einen Basiswert)."""
    base = min(times)
    avg_offset = sum((t - base).total_seconds() for t in times) / len(times)
    return base + timedelta(seconds=avg_offset)


def lap_crossing_times(records: Iterable[TimingRecord]) -> dict[int, datetime]:
    """Je Runde (lap_index) die Überquerungszeit = Mittelwert aller Erfassungen
    dieser Runde (mehrere Zeitnehmer erfassen dieselbe Überquerung)."""
    by_lap: dict[int, list[datetime]] = {}
    for rec in records:
        if rec.lap_index is not None:
            by_lap.setdefault(rec.lap_index, []).append(rec.absolute_time)
    return {lap: _mean_datetime(ts) for lap, ts in by_lap.items()}


async def recompute_laps(session: AsyncSession, event_id: uuid.UUID, bib_number: int) -> None:
    """Ordnet die Erfassungen einer Startnummer Runden (Zielüberquerungen) zu.

    Modell mit mehreren Zeitnehmern: Erfassungen, die weniger als
    min_lap_seconds auseinanderliegen, gehören zur GLEICHEN Überquerung
    (nur von verschiedenen Geräten aufgenommen). Sie bilden ein Cluster und
    teilen sich denselben lap_index; die eigentliche Überquerungszeit ist der
    Mittelwert dieser Erfassungen (siehe lap_crossing_times). Ein Abstand
    >= min_lap_seconds zur vorherigen Erfassung beginnt eine neue Runde.

    Status: von der Stab-Korrektur auf 'ignored' gesetzte Records werden
    übersprungen; alle übrigen zählen (kein automatisches 'duplicate' mehr).
    Aufruf nach jedem Ingestion-Batch bzw. nach manueller Korrektur.
    """
    records = (
        await session.execute(
            select(TimingRecord)
            .where(
                TimingRecord.event_id == event_id,
                TimingRecord.bib_number == bib_number,
                TimingRecord.status != "ignored",
            )
            .order_by(TimingRecord.absolute_time)
        )
    ).scalars().all()

    lap = 0
    prev_time: datetime | None = None
    for rec in records:
        if (
            prev_time is None
            or (rec.absolute_time - prev_time).total_seconds() >= settings.min_lap_seconds
        ):
            lap += 1  # neue Überquerung (Cluster-Grenze)
        rec.lap_index = lap
        if rec.status != "manual":
            rec.status = "valid"
        prev_time = rec.absolute_time


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
            lap_times = lap_crossing_times(crossings)  # Runde -> gemittelte Zeit
            for lap in sorted(lap_times):
                elapsed = (lap_times[lap] - start).total_seconds()
                splits.append(LapSplit(lap_index=lap, elapsed_seconds=elapsed))
                if lap == competition.lap_count:
                    finish_seconds = elapsed

        rows.append(
            ResultRow(
                rank=None,  # nach Sortierung gesetzt
                bib_number=bib.bib_number,
                first_name=participant.first_name,
                last_name=participant.last_name,
                gender=participant.gender,
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


async def result_placement(
    session: AsyncSession, competition: Competition, bib_number: int
) -> dict | None:
    """Platzierung einer Startnummer im Wettbewerb – vier Wertungen:
    gesamt, gesamt je Geschlecht, Altersklasse, Altersklasse je Geschlecht.
    Ränge kommen aus build_results (über das ganze Feld, bereits nach Zeit
    sortiert). None, wenn die Startnummer (noch) keine Zielzeit hat."""
    rows = await build_results(session, competition, only_published=False)
    me = next((r for r in rows if r.bib_number == bib_number), None)
    if me is None or me.finish_seconds is None or me.rank is None:
        return None
    finishers = [r for r in rows if r.finish_seconds is not None]

    def rank_in(subset: list[ResultRow]) -> int:
        # finishers ist zeitsortiert -> Teilmengen bleiben sortiert.
        return next(i for i, r in enumerate(subset, 1) if r.bib_number == bib_number)

    by_gender = [r for r in finishers if r.gender == me.gender]
    by_class = [r for r in finishers if r.category_code == me.category_code]
    by_class_gender = [r for r in by_class if r.gender == me.gender]

    return {
        "gender": me.gender,
        "class_code": me.category_code,
        "overall_rank": me.rank,
        "overall_total": len(finishers),
        "gender_rank": rank_in(by_gender),
        "gender_total": len(by_gender),
        "class_rank": rank_in(by_class),
        "class_total": len(by_class),
        "class_gender_rank": rank_in(by_class_gender),
        "class_gender_total": len(by_class_gender),
    }


async def recompute_event_times(session: AsyncSession, event_id: uuid.UUID) -> int:
    """Berechnet für alle bestätigten Anmeldungen mit Startnummer die Netto-
    Laufzeit (Zielüberquerung − Startzeit) neu und speichert sie in
    registration.finish_seconds. Läuft dabei zuerst die Rundenableitung für alle
    Startnummern erneut. Rückgabe: Anzahl aktualisierter Anmeldungen.
    """
    event = await session.get(Event, event_id)

    comps = {
        c.id: c
        for c in (
            await session.execute(select(Competition).where(Competition.event_id == event_id))
        ).scalars().all()
    }

    rows = (
        await session.execute(
            select(Registration, BibAssignment)
            .join(BibAssignment, BibAssignment.registration_id == Registration.id)
            .where(Registration.event_id == event_id, Registration.status == "confirmed")
        )
    ).all()

    # Runden für alle beteiligten Startnummern neu ableiten.
    for _reg, bib in rows:
        await recompute_laps(session, event_id, bib.bib_number)
    await session.flush()

    # Zielüberquerungen (lap_index gesetzt) einmalig laden und je Startnummer
    # die gemittelte Zeit pro Runde bilden (mehrere Zeitnehmer -> Mittelwert).
    crossings = (
        await session.execute(
            select(TimingRecord).where(
                TimingRecord.event_id == event_id, TimingRecord.lap_index.isnot(None)
            )
        )
    ).scalars().all()
    per_bib: dict[int, list[TimingRecord]] = {}
    for t in crossings:
        per_bib.setdefault(t.bib_number, []).append(t)
    mean_by_key: dict[tuple[int, int], datetime] = {}
    for bib_number, recs in per_bib.items():
        for lap, mean_time in lap_crossing_times(recs).items():
            mean_by_key[(bib_number, lap)] = mean_time

    # count = Anzahl Anmeldungen, für die tatsächlich eine Zeit ermittelt wurde
    # (nicht bloß verarbeitet) -> 0 ist ein klares Signal für "keine Startzeit
    # gesetzt" oder "keine Zielüberquerung erfasst".
    count = 0
    for reg, bib in rows:
        comp = comps.get(reg.competition_id)
        start = (comp.start_time or event.default_start_time) if comp else None
        finish = None
        if comp and start is not None:
            crossing_time = mean_by_key.get((bib.bib_number, comp.lap_count))
            if crossing_time is not None:
                finish = (crossing_time - start).total_seconds()
        reg.finish_seconds = finish
        if finish is not None:
            count += 1

    await session.commit()
    return count


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


# =========================================================================
# Laufzeit-Konfiguration (app_setting) – z. B. Mail-Testmodus umschaltbar
# ohne Redeploy. Ist kein Wert gesetzt, gilt der Env-Default aus settings.
# =========================================================================
MAIL_TEST_MODE_KEY = "mail_test_mode"


async def get_app_setting(session: AsyncSession, key: str) -> str | None:
    return (
        await session.execute(select(AppSetting.value).where(AppSetting.key == key))
    ).scalar_one_or_none()


async def set_app_setting(session: AsyncSession, key: str, value: str) -> None:
    row = await session.get(AppSetting, key)
    if row is None:
        session.add(AppSetting(key=key, value=value))
    else:
        row.value = value


async def get_mail_test_mode(session: AsyncSession) -> bool:
    """Effektiver Testmodus: DB-Override (falls gesetzt) vor Env-Default."""
    stored = await get_app_setting(session, MAIL_TEST_MODE_KEY)
    if stored is None:
        return settings.mail_test_mode
    return stored == "true"


async def send_confirmation_email(
    registration: Registration, manage_token: str, session: AsyncSession
) -> None:
    """Bestätigungsmail mit Verwaltungslink (über Scaleway TEM / mailer).

    Fehler beim Mailversand dürfen die Anmeldung nicht scheitern lassen –
    daher wird eine Ausnahme nur geloggt. Der Testmodus wird zur Laufzeit
    aus app_setting gelesen (umschaltbar im Special-Admin).
    """
    link = f"{settings.public_base_url}/manage?token={manage_token}"
    if registration.language == "en":
        subject = "Your Bibby registration"
        text = (
            "Thank you for registering!\n\n"
            f"Manage or correct your registration anytime here:\n{link}\n"
        )
    else:
        subject = "Deine Bibby-Anmeldung"
        text = (
            "Danke für deine Anmeldung!\n\n"
            f"Deine Anmeldung kannst du hier jederzeit verwalten oder korrigieren:\n{link}\n"
        )

    test_mode = await get_mail_test_mode(session)
    try:
        await mailer.send_email(
            to=registration.email, subject=subject, text=text, test_mode=test_mode
        )
    except Exception as exc:  # noqa: BLE001 – Mailversand darf nicht blockieren
        print(f"[email] Versand an {registration.email} fehlgeschlagen: {exc}")


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


def format_duration(seconds: float) -> str:
    """Sekunden -> h:mm:ss (bzw. mm:ss unter einer Stunde)."""
    total = int(round(seconds))
    hours, rem = divmod(total, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def render_certificate_pdf(
    *,
    first_name: str,
    last_name: str,
    time_text: str,
    extra_lines: list[str] | None = None,
    background: bytes | None = None,
    background_mime: str | None = None,
) -> bytes:
    """Teilnehmer-Urkunde als A4-PDF (hoch). Auf eine optionale Hintergrund-
    vorlage werden Name, Zeit und weitere Zeilen (z. B. Platzierungen) mittig
    gelegt. WeasyPrint erst hier importiert."""
    import base64
    from html import escape

    from weasyprint import HTML

    bg_css = ""
    if background:
        mime = background_mime or "image/png"
        b64 = base64.b64encode(background).decode()
        bg_css = (
            f"background-image: url('data:{mime};base64,{b64}');"
            "background-size: cover; background-position: center;"
        )

    lines_html = "".join(
        f'<div class="line">{escape(line)}</div>' for line in (extra_lines or [])
    )

    html = f"""
    <html><head><meta charset="utf-8"><style>
      @page {{ size: A4 portrait; margin: 0; }}
      html, body {{ margin: 0; padding: 0; }}
      .page {{ width: 210mm; height: 297mm; display: table; {bg_css} }}
      .center {{ display: table-cell; vertical-align: middle; text-align: center; }}
      .name {{ font-family: Helvetica, Arial, sans-serif; font-size: 34pt;
               font-weight: 700; color: #1c2430; }}
      .time {{ font-family: Helvetica, Arial, sans-serif; font-size: 26pt;
               margin-top: 8mm; color: #2f6df0; }}
      .line {{ font-family: Helvetica, Arial, sans-serif; font-size: 18pt;
               margin-top: 5mm; color: #1c2430; }}
    </style></head><body>
      <div class="page"><div class="center">
        <div class="name">{escape(first_name)} {escape(last_name)}</div>
        <div class="time">{escape(time_text)}</div>
        {lines_html}
      </div></div>
    </body></html>
    """
    return HTML(string=html).write_pdf()
