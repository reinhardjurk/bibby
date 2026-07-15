"""Domänenlogik: Teilnehmer-Matching, Rundenableitung, Ergebnisberechnung.

Der TEM-Mailversand ist als klar gekennzeichneter Stub implementiert und wird
später gegen die echte API ausgetauscht.
"""

from __future__ import annotations

import json
import unicodedata
import uuid
from datetime import date, datetime, timedelta

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from . import mailer
from .config import settings
from .models import (
    AppSetting,
    BibAssignment,
    Competition,
    Event,
    Participant,
    Registration,
    TimingRecord,
)
from .schemas import ResultRow


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
def compute_age_class(age: int, scheme: str = "five") -> str:
    """Geschlechtsneutrale Altersklasse aus dem Alter (Geschlecht separat gewertet).
    scheme="five": 5-Jahres-Schema (Laufsport) – U20, AK20 (20–24), AK25, AK30 …
    scheme="one":  Einjahres-Schema – jede Altersstufe eigene Klasse (AK<alter>)."""
    if scheme == "one":
        return f"AK{age}"
    if age < 20:
        return "U20"
    return f"AK{(age // 5) * 5}"


async def resolve_category(
    session: AsyncSession, event: Event, participant: Participant, scheme: str = "five"
) -> str | None:
    """Altersklasse aus dem Alter am Veranstaltungstag (Jahr − Geburtsjahr).
    Berechnet nach compute_age_class; die Category-Tabelle wird nicht mehr
    benötigt (session-Parameter bleibt aus Signaturgründen erhalten)."""
    if scheme == "none" or participant.birth_date is None:
        return None
    age = event.event_date.year - participant.birth_date.year
    return compute_age_class(age, scheme)


def compute_price_cents(event: Event, competition: Competition, birth_date: date) -> int:
    """Startgeld für Strecke + Altersgruppe. Wer am/nach event.junior_cutoff_date
    geboren ist, zahlt price_junior_cents (falls gesetzt), sonst den Standardpreis."""
    is_junior = event.junior_cutoff_date is not None and birth_date >= event.junior_cutoff_date
    if is_junior and competition.price_junior_cents is not None:
        return competition.price_junior_cents
    return competition.price_cents


# =========================================================================
# Zeitermittlung (ohne Rundenkonzept)
# =========================================================================
def _mean_datetime(times: list[datetime]) -> datetime:
    """Mittelwert mehrerer Zeitpunkte (numerisch stabil über einen Basiswert)."""
    base = min(times)
    avg_offset = sum((t - base).total_seconds() for t in times) / len(times)
    return base + timedelta(seconds=avg_offset)


async def bib_finish_datetime(
    session: AsyncSession, event_id: uuid.UUID, bib_number: int
) -> datetime | None:
    """Zielzeitpunkt einer Startnummer = Mittelwert ALLER nicht-ignorierten
    Erfassungen (mehrere Zeitnehmer erfassen dieselbe Zielüberquerung). Kein
    Rundenkonzept mehr. None, wenn keine gültige Erfassung existiert."""
    times = (
        await session.execute(
            select(TimingRecord.absolute_time).where(
                TimingRecord.event_id == event_id,
                TimingRecord.bib_number == bib_number,
                TimingRecord.status != "ignored",
            )
        )
    ).scalars().all()
    if not times:
        return None
    return _mean_datetime(list(times))


# =========================================================================
# Ergebnisliste pro Wettbewerb
# =========================================================================
async def build_results(
    session: AsyncSession,
    competition: Competition,
    *,
    only_published: bool = True,
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
        finish_seconds: float | None = None
        if start is not None:
            finish_dt = await bib_finish_datetime(session, competition.event_id, bib.bib_number)
            if finish_dt is not None:
                finish_seconds = (finish_dt - start).total_seconds()

        rows.append(
            ResultRow(
                rank=None,  # nach Sortierung gesetzt
                bib_number=bib.bib_number,
                first_name=participant.first_name,
                last_name=participant.last_name,
                gender=participant.gender,
                category_code=await resolve_category(
                    session, event, participant, competition.age_class_scheme
                ),
                team=reg.team,
                finish_seconds=finish_seconds,
                splits=[],
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


def placement_from_rows(rows: list[ResultRow], bib_number: int) -> dict | None:
    """Vier Platzierungen einer Startnummer aus bereits berechneten Ergebnis-
    Zeilen (build_results): gesamt, gesamt je Geschlecht, Altersklasse,
    Altersklasse je Geschlecht. None, wenn keine Zielzeit."""
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


async def result_placement(
    session: AsyncSession, competition: Competition, bib_number: int
) -> dict | None:
    """Wie placement_from_rows, berechnet die Ergebnis-Zeilen selbst."""
    rows = await build_results(session, competition, only_published=False)
    return placement_from_rows(rows, bib_number)


def certificate_lines(
    placement: dict | None, lang: str = "de", *, gender_scoring: bool = True
) -> list[str]:
    """Platzierungszeilen für die Urkunde je nach Strecken-Wertung: Gesamt immer;
    Geschlechtswertung nur bei gender_scoring; Altersklasse nur, wenn eine
    zugeordnet ist (class_code gesetzt = Schema != 'none')."""
    if not placement:
        return []
    en = lang == "en"
    gender_words = (
        {"f": "female", "m": "male", "x": "diverse"}
        if en
        else {"f": "weiblich", "m": "männlich", "x": "divers"}
    )
    g = gender_words.get(placement["gender"], placement["gender"] or "")
    code = placement["class_code"]
    of = "of" if en else "von"
    overall = "Overall rank" if en else "Platz gesamt"
    ak = "Age group" if en else "Altersklasse"
    lines = [f"{overall}: {placement['overall_rank']} {of} {placement['overall_total']}"]
    if gender_scoring:
        lines.append(
            f"{overall} ({g}): {placement['gender_rank']} {of} {placement['gender_total']}"
        )
    if code:
        lines.append(f"{ak} {code}: {placement['class_rank']} {of} {placement['class_total']}")
        if gender_scoring:
            lines.append(
                f"{ak} {code} ({g}): "
                f"{placement['class_gender_rank']} {of} {placement['class_gender_total']}"
            )
    return lines


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

    # count = Anzahl Anmeldungen, für die tatsächlich eine Zeit ermittelt wurde
    # (nicht bloß verarbeitet) -> 0 ist ein klares Signal für "keine Startzeit
    # gesetzt" oder "keine Erfassung".
    count = 0
    for reg, bib in rows:
        comp = comps.get(reg.competition_id)
        start = (comp.start_time or event.default_start_time) if comp else None
        finish = None
        if start is not None:
            finish_dt = await bib_finish_datetime(session, event_id, bib.bib_number)
            if finish_dt is not None:
                finish = (finish_dt - start).total_seconds()
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
SPONSOR_TIERS_KEY = "sponsor_tiers"

# Je Sponsorenklasse: weight = Zeitanteil in der Rotation, height = Anzeigehöhe (px).
DEFAULT_SPONSOR_TIERS: dict[str, dict[str, int]] = {
    "1": {"weight": 30, "height": 90},
    "2": {"weight": 20, "height": 70},
    "3": {"weight": 10, "height": 55},
    "4": {"weight": 5, "height": 45},
    "5": {"weight": 1, "height": 35},
}


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


async def get_sponsor_tiers(session: AsyncSession) -> dict[str, dict[str, int]]:
    """Konfiguration der 5 Sponsorenklassen; fehlende Werte -> Defaults."""
    raw = await get_app_setting(session, SPONSOR_TIERS_KEY)
    if not raw:
        return DEFAULT_SPONSOR_TIERS
    try:
        stored = json.loads(raw)
    except (ValueError, TypeError):
        return DEFAULT_SPONSOR_TIERS
    return {
        tier: {**defaults, **(stored.get(tier) or {})}
        for tier, defaults in DEFAULT_SPONSOR_TIERS.items()
    }


async def set_sponsor_tiers(session: AsyncSession, tiers: dict) -> None:
    await set_app_setting(session, SPONSOR_TIERS_KEY, json.dumps(tiers))


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
    """Anzeigename eines Wettbewerbs: title_i18n falls vorhanden, sonst 'Lauf'."""
    if competition.title_i18n and competition.title_i18n.get(lang):
        return competition.title_i18n[lang]
    return "Lauf"


def format_duration(seconds: float) -> str:
    """Sekunden -> h:mm:ss (bzw. mm:ss unter einer Stunde)."""
    total = int(round(seconds))
    hours, rem = divmod(total, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


# Eine "Zeile" Versatz entspricht diesem vertikalen Weg (mm).
CERT_LINE_MM = 8


def render_certificates_pdf(
    certs: list[dict],
    *,
    background: bytes | None = None,
    background_mime: str | None = None,
    offset_lines: int = 0,
) -> bytes:
    """Ein oder mehrere Urkunden als A4-PDF (je eine Seite). Jede cert ist ein
    dict {first_name, last_name, time_text, bib_text, extra_lines}. Name/Zeit/
    Zeilen werden mittig auf eine optionale Hintergrundvorlage gelegt.
    offset_lines verschiebt den Druck vertikal (+ nach unten, - nach oben)."""
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

    def page(cert: dict) -> str:
        lines = "".join(
            f'<div class="line">{escape(x)}</div>' for x in (cert.get("extra_lines") or [])
        )
        bib_html = (
            f'<div class="bib">{escape(cert["bib_text"])}</div>' if cert.get("bib_text") else ""
        )
        team_html = (
            f'<div class="team">{escape(cert["team"])}</div>' if cert.get("team") else ""
        )
        return (
            '<div class="page"><div class="content">'
            f'<div class="name">{escape(cert["first_name"])} {escape(cert["last_name"])}</div>'
            f"{bib_html}{team_html}"
            f'<div class="time">{escape(cert["time_text"])}</div>'
            f"{lines}</div></div>"
        )

    pages = "".join(page(c) for c in certs)
    html = f"""
    <html><head><meta charset="utf-8"><style>
      @page {{ size: A4 portrait; margin: 0; }}
      html, body {{ margin: 0; padding: 0; }}
      .page {{ width: 210mm; height: 297mm; {bg_css}
               display: flex; align-items: center; justify-content: center;
               page-break-after: always; }}
      .page:last-child {{ page-break-after: auto; }}
      .content {{ text-align: center; transform: translateY({offset_lines * CERT_LINE_MM}mm); }}
      .name {{ font-family: Helvetica, Arial, sans-serif; font-size: 34pt;
               font-weight: 700; color: #1c2430; }}
      .bib {{ font-family: Helvetica, Arial, sans-serif; font-size: 20pt;
              margin-top: 4mm; color: #1c2430; }}
      .team {{ font-family: Helvetica, Arial, sans-serif; font-size: 18pt;
               margin-top: 2mm; color: #1c2430; }}
      .time {{ font-family: Helvetica, Arial, sans-serif; font-size: 26pt;
               margin-top: 8mm; color: #2f6df0; }}
      .line {{ font-family: Helvetica, Arial, sans-serif; font-size: 18pt;
               margin-top: 5mm; color: #1c2430; }}
    </style></head><body>{pages}</body></html>
    """
    return HTML(string=html).write_pdf()


def certificate_bib_text(bib_number: int, lang: str = "de") -> str:
    """Beschriftung der Startnummer auf der Urkunde (lokalisiert)."""
    return f"Bib {bib_number}" if lang == "en" else f"Startnummer {bib_number}"


def render_certificate_pdf(
    *,
    first_name: str,
    last_name: str,
    time_text: str,
    bib_text: str | None = None,
    team: str | None = None,
    extra_lines: list[str] | None = None,
    background: bytes | None = None,
    background_mime: str | None = None,
    offset_lines: int = 0,
) -> bytes:
    """Einzelne Teilnehmer-Urkunde (Wrapper um render_certificates_pdf)."""
    return render_certificates_pdf(
        [
            {
                "first_name": first_name,
                "last_name": last_name,
                "time_text": time_text,
                "bib_text": bib_text,
                "team": team,
                "extra_lines": extra_lines or [],
            }
        ],
        background=background,
        background_mime=background_mime,
        offset_lines=offset_lines,
    )
