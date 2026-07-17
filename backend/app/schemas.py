"""Pydantic-Schemas für Requests/Responses (API-Contract)."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, EmailStr, Field, field_validator


# --- Anmeldung ------------------------------------------------------------
# Freiwillige Umfrage "Wie hast du von der Veranstaltung erfahren?".
# Gespeichert wird der Code; die Beschriftung liefert das Frontend (i18n).
HEARD_ABOUT_OPTIONS = (
    "always",
    "friends",
    "social_media",
    "posters",
    "magazines",
    "internet",
)


class RegistrationCreate(BaseModel):
    event_id: uuid.UUID
    competition_id: uuid.UUID
    first_name: str
    last_name: str
    birth_date: date
    gender: str = Field(pattern="^[fmx]$")
    email: EmailStr
    language: str = "de"
    team: str | None = None
    tshirt: str | None = None
    consent_data: bool
    consent_publish: bool = False

    # Freiwillige Angaben (dürfen leer bleiben).
    postal_code: str | None = Field(default=None, max_length=16)
    heard_about: str | None = None

    @field_validator("heard_about")
    @classmethod
    def _check_heard_about(cls, v: str | None) -> str | None:
        if v in (None, ""):
            return None
        if v not in HEARD_ABOUT_OPTIONS:
            raise ValueError(f"Ungültiger Wert; erlaubt: {', '.join(HEARD_ABOUT_OPTIONS)}")
        return v

    # Zahlung: SEPA-Lastschriftmandat oder Barzahlung bei Abholung.
    payment_method: str = Field(pattern="^(sepa_debit|on_site)$")
    iban: str | None = None              # nur bei sepa_debit
    account_holder: str | None = None    # nur bei sepa_debit
    mandate_consent: bool = False        # Einzugsermächtigung erteilt


class RegistrationOut(BaseModel):
    id: uuid.UUID
    status: str
    competition_id: uuid.UUID
    bib_number: int | None = None
    # Klartext-Verwaltungs-Token nur direkt nach Anmeldung zurückgegeben.
    manage_token: str | None = None
    # Bei SEPA-Anmeldung: die erzeugte Mandatsreferenz (für die Bestätigung).
    mandate_reference: str | None = None


class RegistrationUpdate(BaseModel):
    """Selbstverwaltung: erlaubte Felder zur Korrektur."""

    email: EmailStr | None = None
    language: str | None = None
    competition_id: uuid.UUID | None = None
    consent_publish: bool | None = None
    # team kann gesetzt oder geleert ("") werden; daher eigenes "übergeben?"-Flag
    # ist nicht nötig – None = unverändert, "" = leeren.
    team: str | None = None
    tshirt: str | None = None


class ManageView(BaseModel):
    registration: RegistrationOut
    first_name: str
    last_name: str
    email: EmailStr
    event_id: uuid.UUID
    competition_lap_count: int
    team: str | None = None
    # Vorschlag aus einer früheren Anmeldung derselben Person (falls vorhanden).
    suggested_team: str | None = None
    tshirt: str | None = None
    tshirt_options: list[str] = []
    # Netto-Laufzeit (Sek.), falls berechnet – für die Urkunde.
    finish_seconds: float | None = None
    payment_method: str | None = None
    payment_status: str | None = None
    payment_iban_masked: str | None = None
    mandate_reference: str | None = None


# --- Zeiterfassung --------------------------------------------------------
class TimingPing(BaseModel):
    bib_number: int
    absolute_time: datetime  # Gerätezeit (UTC), Offset wird serverseitig angewandt
    # Idempotenz-Schlüssel der Quelle; gleiche Pings dürfen gefahrlos
    # wiederholt werden (Offline-Puffer der CV-App).
    dedup_key: str
    raw_payload: dict | None = None


class TimingBatch(BaseModel):
    pings: list[TimingPing]


class TimingBatchResult(BaseModel):
    accepted: int
    duplicates: int  # bereits via dedup_key vorhanden


class TimingCorrection(BaseModel):
    status: str = Field(pattern="^(valid|ignored|manual)$")
    bib_number: int | None = None
    absolute_time: datetime | None = None


class ManualTiming(BaseModel):
    absolute_time: datetime


class SponsorTierCfg(BaseModel):
    weight: int = Field(ge=0)   # Zeitanteil in der Rotation
    height: int = Field(ge=10, le=400)  # Anzeigehöhe in px


class SponsorTiersUpdate(BaseModel):
    tiers: dict[str, SponsorTierCfg]


class SponsorDisplayUpdate(BaseModel):
    mode: str  # 'rotate' | 'marquee'
    marquee_seconds: int | None = None  # Sekunden pro Laufband-Durchlauf


class SponsorUpdate(BaseModel):
    name: str | None = None
    url: str | None = None


# --- Ergebnisse -----------------------------------------------------------
class LapSplit(BaseModel):
    lap_index: int
    elapsed_seconds: float


class ResultRow(BaseModel):
    rank: int | None
    bib_number: int
    first_name: str
    last_name: str
    gender: str
    category_code: str | None
    team: str | None = None
    finish_seconds: float | None  # None = DNF (Zielrunde nicht erreicht)
    splits: list[LapSplit]
    participation_count: int  # jahresübergreifend, inkl. diesem Event
    # Veröffentlichungs-Einwilligung. In der öffentlichen Liste immer True
    # (nicht einwilligende werden dort herausgefiltert); intern auch False.
    published: bool = True


class ResultList(BaseModel):
    event_id: uuid.UUID
    competition_id: uuid.UUID
    lap_count: int
    rows: list[ResultRow]


# --- Admin / RBAC ---------------------------------------------------------
class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class SessionToken(BaseModel):
    token: str
    expires_at: datetime
    roles: list[str]


class MailSettings(BaseModel):
    """Effektiver Versandmodus + Kontext für die Anzeige.

    mode: 'live' = echte Empfänger · 'test' = alles an test_recipient umgeleitet
    (wird weiter versendet!) · 'off' = gar kein Versand (für Lasttests)."""

    mode: str
    test_recipient: str
    overridden: bool  # True = per app_setting gesetzt, False = Env-Default


class MailModeUpdate(BaseModel):
    mode: str = Field(pattern="^(live|test|off)$")


class MailTexts(BaseModel):
    """Betreff + Text der Anmeldebestätigung je Sprache. {link} im Text wird
    durch den persönlichen Verwaltungslink ersetzt."""

    subject_de: str = Field(min_length=1, max_length=200)
    body_de: str = Field(min_length=1, max_length=5000)
    subject_en: str = Field(min_length=1, max_length=200)
    body_en: str = Field(min_length=1, max_length=5000)


ALLOWED_ROLES = (
    "admin",
    "race_office",
    "timing",
    "sponsor_management",
    "sepa",
    "viewer",
)


class UserOut(BaseModel):
    id: uuid.UUID
    email: str
    name: str | None = None
    active: bool
    roles: list[str]


class UserCreate(BaseModel):
    email: EmailStr
    name: str | None = None
    password: str = Field(min_length=6, max_length=200)
    roles: list[str] = Field(default_factory=list)


class UserUpdate(BaseModel):
    """Alle Felder optional; nur gesetzte werden angewendet. roles ersetzt die
    komplette Rollenmenge, wenn angegeben."""

    name: str | None = None
    active: bool | None = None
    roles: list[str] | None = None
    password: str | None = Field(default=None, min_length=6, max_length=200)


class BibReassign(BaseModel):
    competition_id: uuid.UUID


class ParticipantMerge(BaseModel):
    source_participant_id: uuid.UUID
    target_participant_id: uuid.UUID


class CompetitionUpdate(BaseModel):
    # Absolute Startzeit der Strecke (für die Laufzeitberechnung).
    start_time: datetime | None = None
    price_cents: int | None = None            # Erwachsenen-/Standardpreis
    price_junior_cents: int | None = None     # Jugendpreis (null = wie Erwachsene)
    age_class_scheme: str | None = None       # 'five' | 'one' | 'none'
    gender_scoring: bool | None = None
    relay_scoring: bool | None = None


class EventUpdate(BaseModel):
    tshirt_options: list[str] | None = None
    junior_cutoff_date: date | None = None    # Geburtsdatum ab hier = ermäßigt
    tshirt_included: bool | None = None
    certificate_offset: int | None = None     # Urkunden-Druckversatz (Zeilen)
    postal_code: str | None = None            # PLZ des Veranstaltungsorts (Statistik)


class CompetitionCreate(BaseModel):
    lap_count: int = 1                         # vestigial (Rundenkonzept entfernt)
    title: str | None = None                  # Anzeigename (optional)
    price_cents: int = 0
    price_junior_cents: int | None = None
    currency: str = "EUR"
    start_time: datetime | None = None
    age_class_scheme: str = "five"            # 'five' | 'one' | 'none'
    gender_scoring: bool = True
    relay_scoring: bool = False


class EventCreate(BaseModel):
    name: str
    year: int
    event_date: date
    registration_deadline: datetime | None = None
    default_start_time: datetime | None = None
    junior_cutoff_date: date | None = None
    tshirt_included: bool = False
    tshirt_options: list[str] | None = None
    competitions: list[CompetitionCreate]


class DeviceTokenCreate(BaseModel):
    label: str
    time_offset_seconds: int = 0


class DeviceTokenOut(BaseModel):
    id: uuid.UUID
    label: str
    token: str | None = None  # Klartext nur bei Erstellung
    time_offset_seconds: int
    active: bool


class AdminRegistrationDetail(BaseModel):
    """Vollständige Anmeldedaten für die Admin-Bearbeitung."""

    id: uuid.UUID
    first_name: str
    last_name: str
    birth_date: date
    gender: str
    # Ausgabe-Modell: bewusst str (nicht EmailStr), damit ein evtl. ungültig
    # gespeicherter Wert die Detailansicht nicht mit 500 blockiert.
    email: str
    language: str
    team: str | None
    tshirt: str | None
    tshirt_options: list[str] = []
    postal_code: str | None = None
    heard_about: str | None = None
    consent_data: bool
    consent_publish: bool
    status: str
    bib_number: int | None
    event_id: uuid.UUID
    competition_id: uuid.UUID
    lap_count: int
    payment_method: str | None
    payment_status: str | None
    payment_iban_masked: str | None


class AdminRegistrationUpdate(BaseModel):
    """Admin darf alle Felder korrigieren. None = unverändert."""

    first_name: str | None = None
    last_name: str | None = None
    birth_date: date | None = None
    gender: str | None = None
    email: EmailStr | None = None
    language: str | None = None
    team: str | None = None
    consent_data: bool | None = None
    consent_publish: bool | None = None
    status: str | None = None
    bib_number: int | None = None
    competition_id: uuid.UUID | None = None
    payment_method: str | None = None
    payment_status: str | None = None
    tshirt: str | None = None
