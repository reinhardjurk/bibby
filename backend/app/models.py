"""SQLAlchemy-2.0-Modelle, gespiegelt aus db/schema.sql."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


def _pk() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


class Participant(Base):
    __tablename__ = "participant"

    id: Mapped[uuid.UUID] = _pk()
    match_key: Mapped[str] = mapped_column(String, unique=True)
    first_name: Mapped[str]
    last_name: Mapped[str]
    birth_date: Mapped[date] = mapped_column(Date)
    gender: Mapped[str] = mapped_column(String(1))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (CheckConstraint("gender IN ('f','m','x')", name="ck_participant_gender"),)


class Event(Base):
    __tablename__ = "event"

    id: Mapped[uuid.UUID] = _pk()
    name: Mapped[str]
    year: Mapped[int] = mapped_column(Integer, unique=True)
    event_date: Mapped[date] = mapped_column(Date)
    location: Mapped[str | None]
    default_start_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    registration_deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Konfigurierbare T-Shirt-Optionen (Liste von Strings). NULL = Default.
    tshirt_options: Mapped[list | None] = mapped_column(JSONB)
    # Wer an oder nach diesem Datum geboren ist, zahlt den ermäßigten (Jugend-)
    # Preis. NULL = keine Ermäßigung (alle zahlen den Erwachsenenpreis).
    junior_cutoff_date: Mapped[date | None] = mapped_column(Date)
    # T-Shirt im Startgeld enthalten (informativ; ändert den Preis nicht).
    tshirt_included: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    competitions: Mapped[list[Competition]] = relationship(back_populates="event")


class Competition(Base):
    __tablename__ = "competition"

    id: Mapped[uuid.UUID] = _pk()
    event_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("event.id", ondelete="CASCADE"))
    lap_count: Mapped[int] = mapped_column(Integer)
    title_i18n: Mapped[dict | None] = mapped_column(JSONB)
    start_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Erwachsenen-/Standardpreis; Jugendpreis optional (NULL = wie Erwachsene).
    price_cents: Mapped[int] = mapped_column(Integer, default=0)
    price_junior_cents: Mapped[int | None] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3), default="EUR")

    event: Mapped[Event] = relationship(back_populates="competitions")

    # Mehrere Strecken je Event dürfen dieselbe Rundenzahl haben (z. B.
    # "3,3 km Running" und "3,3 km Walking"); Unterscheidung über den Namen.
    __table_args__ = (CheckConstraint("lap_count >= 1", name="ck_competition_lap_count"),)


class Category(Base):
    __tablename__ = "category"

    id: Mapped[uuid.UUID] = _pk()
    event_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("event.id", ondelete="CASCADE"))
    code: Mapped[str]
    label_i18n: Mapped[dict | None] = mapped_column(JSONB)
    gender: Mapped[str | None] = mapped_column(String(1))
    min_age: Mapped[int | None]
    max_age: Mapped[int | None]

    __table_args__ = (UniqueConstraint("event_id", "code", name="uq_category_event_code"),)


class Registration(Base):
    __tablename__ = "registration"

    id: Mapped[uuid.UUID] = _pk()
    event_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("event.id", ondelete="CASCADE"))
    competition_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("competition.id"))
    participant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("participant.id"))
    email: Mapped[str]
    language: Mapped[str] = mapped_column(String(5), default="de")
    # Optionale Teamzugehörigkeit (kann je Jahr abweichen).
    team: Mapped[str | None] = mapped_column(String)
    # Gewählte T-Shirt-Option (aus event.tshirt_options).
    tshirt: Mapped[str | None] = mapped_column(String)
    # Anmeldung gilt sofort als bestätigt; Zahlung wird separat geführt.
    status: Mapped[str] = mapped_column(String, default="confirmed")
    # Gespeicherte Netto-Laufzeit (Sek.), berechnet per "Alle Laufzeiten berechnen".
    # None = noch nicht berechnet oder Zielrunde nicht erreicht (DNF).
    finish_seconds: Mapped[float | None] = mapped_column(Float)
    manage_token_hash: Mapped[str] = mapped_column(String, unique=True)
    consent_data: Mapped[bool] = mapped_column(Boolean, default=False)
    consent_publish: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    participant: Mapped[Participant] = relationship()
    competition: Mapped[Competition] = relationship()
    # selectin: lädt die Startnummer eager mit. Lazy-Load würde unter async
    # SQLAlchemy einen MissingGreenlet-Fehler auslösen (-> HTTP 500).
    bib: Mapped[BibAssignment | None] = relationship(
        back_populates="registration", uselist=False, lazy="selectin"
    )

    __table_args__ = (
        UniqueConstraint("event_id", "participant_id", name="uq_registration_event_participant"),
        CheckConstraint(
            "status IN ('pending_payment','confirmed','cancelled')", name="ck_registration_status"
        ),
    )


class BibAssignment(Base):
    __tablename__ = "bib_assignment"

    id: Mapped[uuid.UUID] = _pk()
    event_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("event.id", ondelete="CASCADE"))
    bib_number: Mapped[int] = mapped_column(Integer)
    registration_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("registration.id", ondelete="CASCADE"), unique=True
    )
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    registration: Mapped[Registration] = relationship(back_populates="bib")

    __table_args__ = (UniqueConstraint("event_id", "bib_number", name="uq_bib_event_number"),)


class Payment(Base):
    __tablename__ = "payment"

    id: Mapped[uuid.UUID] = _pk()
    registration_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("registration.id", ondelete="CASCADE")
    )
    # 'sepa_debit' = Lastschriftmandat, 'on_site' = Barzahlung bei Abholung.
    method: Mapped[str] = mapped_column(String)
    amount_cents: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3), default="EUR")
    # 'pending' = offen, 'paid' = eingezogen/bezahlt, 'cancelled'.
    status: Mapped[str] = mapped_column(String, default="pending")

    # SEPA-Mandat (nur bei method='sepa_debit'). IBAN verschlüsselt at-rest.
    iban_encrypted: Mapped[str | None] = mapped_column(String)
    iban_masked: Mapped[str | None] = mapped_column(String)
    account_holder: Mapped[str | None] = mapped_column(String)
    mandate_reference: Mapped[str | None] = mapped_column(String, unique=True)
    mandate_granted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Zeitpunkt des letzten SEPA-CSV-Exports (NULL = noch nicht exportiert).
    sepa_exported_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        CheckConstraint("method IN ('sepa_debit','on_site')", name="ck_payment_method"),
        CheckConstraint("status IN ('pending','paid','cancelled')", name="ck_payment_status"),
    )


class DeviceToken(Base):
    __tablename__ = "device_token"

    id: Mapped[uuid.UUID] = _pk()
    event_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("event.id", ondelete="CASCADE"))
    label: Mapped[str]
    token_hash: Mapped[str] = mapped_column(String, unique=True)
    scope: Mapped[str] = mapped_column(String, default="timing:write")
    time_offset_seconds: Mapped[int] = mapped_column(Integer, default=0)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class TimingRecord(Base):
    __tablename__ = "timing_record"

    id: Mapped[uuid.UUID] = _pk()
    event_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("event.id", ondelete="CASCADE"))
    bib_number: Mapped[int] = mapped_column(Integer)
    absolute_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    source_token_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("device_token.id"))
    dedup_key: Mapped[str]
    lap_index: Mapped[int | None]
    status: Mapped[str] = mapped_column(String, default="valid")
    raw_payload: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("event_id", "dedup_key", name="uq_timing_dedup"),
        CheckConstraint(
            "status IN ('valid','ignored','duplicate','manual')", name="ck_timing_status"
        ),
    )


class AppUser(Base):
    __tablename__ = "app_user"

    id: Mapped[uuid.UUID] = _pk()
    email: Mapped[str] = mapped_column(String, unique=True)
    name: Mapped[str | None]
    password_hash: Mapped[str | None] = mapped_column(String)  # bcrypt
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    roles: Mapped[list[UserRole]] = relationship(back_populates="user")


class UserRole(Base):
    __tablename__ = "user_role"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("app_user.id", ondelete="CASCADE"), primary_key=True
    )
    role: Mapped[str] = mapped_column(String, primary_key=True)

    user: Mapped[AppUser] = relationship(back_populates="roles")

    __table_args__ = (
        CheckConstraint(
            "role IN ('admin','race_office','timing','viewer')", name="ck_user_role"
        ),
    )


class AuthToken(Base):
    __tablename__ = "auth_token"

    id: Mapped[uuid.UUID] = _pk()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.id", ondelete="CASCADE"))
    token_hash: Mapped[str] = mapped_column(String, unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
