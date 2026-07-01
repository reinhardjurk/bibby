"""Pydantic-Schemas für Requests/Responses (API-Contract)."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, EmailStr, Field


# --- Anmeldung ------------------------------------------------------------
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


class EventUpdate(BaseModel):
    tshirt_options: list[str] | None = None
    junior_cutoff_date: date | None = None    # Geburtsdatum ab hier = ermäßigt
    tshirt_included: bool | None = None


class CompetitionCreate(BaseModel):
    lap_count: int
    title: str | None = None                  # Anzeigename (optional)
    price_cents: int = 0
    price_junior_cents: int | None = None
    currency: str = "EUR"
    start_time: datetime | None = None


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
    email: EmailStr
    language: str
    team: str | None
    tshirt: str | None
    tshirt_options: list[str] = []
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
