-- Bibby — Datenbankschema (PostgreSQL)
-- Referenz-DDL. Alembic-Migrationen spiegeln dieses Schema.
-- Konventionen: UUID-PKs, timestamptz in UTC, *_i18n als JSONB {"de": "...", "en": "..."}.

CREATE EXTENSION IF NOT EXISTS "pgcrypto"; -- gen_random_uuid()

-- =========================================================================
-- Identität über Jahre hinweg
-- =========================================================================
CREATE TABLE participant (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    -- Normalisierter Match-Key: lower(unaccent(last+first)) || birth_date.
    -- Verbindet Anmeldungen verschiedener Jahre derselben Person.
    match_key       TEXT NOT NULL UNIQUE,
    first_name      TEXT NOT NULL,
    last_name       TEXT NOT NULL,
    birth_date      DATE NOT NULL,          -- at-rest verschlüsselt (Scaleway); öffentl. nur Jahr/AK
    gender          TEXT NOT NULL CHECK (gender IN ('f', 'm', 'x')),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- =========================================================================
-- Veranstaltung (jährlich) und Wettbewerbe (Rundengruppen)
-- =========================================================================
CREATE TABLE event (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name                TEXT NOT NULL,
    year                INT  NOT NULL,
    event_date          DATE NOT NULL,
    location            TEXT,
    default_start_time  TIMESTAMPTZ,        -- Massenstart, falls Gruppen nicht eigene Zeit haben
    registration_deadline TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (year)
);

-- Ein "Wettbewerb" = eine Rundenanzahl (1/2/3) innerhalb eines Events.
CREATE TABLE competition (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id        UUID NOT NULL REFERENCES event(id) ON DELETE CASCADE,
    lap_count       INT  NOT NULL CHECK (lap_count >= 1),
    title_i18n      JSONB,                  -- optionaler Anzeigename, sonst aus lap_count abgeleitet
    start_time      TIMESTAMPTZ,            -- überschreibt event.default_start_time (gestaffelter Start)
    price_cents     INT  NOT NULL DEFAULT 0,
    currency        TEXT NOT NULL DEFAULT 'EUR',
    UNIQUE (event_id, lap_count)
);

-- Altersklassen/Gruppen-Regeln je Event (zum Wettkampftag ausgewertet).
CREATE TABLE category (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id        UUID NOT NULL REFERENCES event(id) ON DELETE CASCADE,
    code            TEXT NOT NULL,          -- z.B. "M40", "W30"
    label_i18n      JSONB,
    gender          TEXT CHECK (gender IN ('f', 'm', 'x')),  -- NULL = geschlechtsoffen
    min_age         INT,
    max_age         INT,
    UNIQUE (event_id, code)
);

-- =========================================================================
-- Anmeldung
-- =========================================================================
CREATE TABLE registration (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id            UUID NOT NULL REFERENCES event(id) ON DELETE CASCADE,
    competition_id      UUID NOT NULL REFERENCES competition(id),
    participant_id      UUID NOT NULL REFERENCES participant(id),
    email               TEXT NOT NULL,      -- kann je Jahr abweichen
    language            TEXT NOT NULL DEFAULT 'de',
    team                TEXT,               -- optionale Teamzugehörigkeit

    -- Anmeldung gilt sofort als bestätigt; Zahlung wird separat geführt.
    status              TEXT NOT NULL DEFAULT 'confirmed'
                          CHECK (status IN ('confirmed', 'cancelled')),
    -- Magic-Link zur Selbstverwaltung: nur Hash gespeichert.
    manage_token_hash   TEXT NOT NULL UNIQUE,
    consent_data        BOOLEAN NOT NULL DEFAULT false,   -- Datenverarbeitung
    consent_publish     BOOLEAN NOT NULL DEFAULT false,   -- Ergebnis-/Fotoveröffentlichung
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- Eine Person nicht doppelt im selben Event:
    UNIQUE (event_id, participant_id)
);
CREATE INDEX idx_registration_event ON registration(event_id);
CREATE INDEX idx_registration_participant ON registration(participant_id);

-- Startnummer: global pro Event, entkoppelt von der Strecke (nachträglich änderbar).
CREATE TABLE bib_assignment (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id        UUID NOT NULL REFERENCES event(id) ON DELETE CASCADE,
    bib_number      INT  NOT NULL,
    registration_id UUID NOT NULL UNIQUE REFERENCES registration(id) ON DELETE CASCADE,
    assigned_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (event_id, bib_number)
);

-- =========================================================================
-- Zahlung: SEPA-Lastschriftmandat oder Barzahlung bei Abholung
-- =========================================================================
CREATE TABLE payment (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    registration_id     UUID NOT NULL REFERENCES registration(id) ON DELETE CASCADE,
    method              TEXT NOT NULL CHECK (method IN ('sepa_debit', 'on_site')),
    amount_cents        INT  NOT NULL,
    currency            TEXT NOT NULL DEFAULT 'EUR',
    status              TEXT NOT NULL DEFAULT 'pending'
                          CHECK (status IN ('pending', 'paid', 'cancelled')),
    -- SEPA-Mandat (nur bei method='sepa_debit'). IBAN verschlüsselt at-rest.
    iban_encrypted      TEXT,
    iban_masked         TEXT,
    account_holder      TEXT,
    mandate_reference   TEXT UNIQUE,
    mandate_granted_at  TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_payment_registration ON payment(registration_id);

-- =========================================================================
-- Zeiterfassung (Rundenrennen)
-- =========================================================================
-- Geräte-Token für Ingestion (Web-Maske, CV-App). Nur Hash gespeichert.
CREATE TABLE device_token (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id            UUID NOT NULL REFERENCES event(id) ON DELETE CASCADE,
    label               TEXT NOT NULL,
    token_hash          TEXT NOT NULL UNIQUE,
    scope               TEXT NOT NULL DEFAULT 'timing:write',
    time_offset_seconds INT  NOT NULL DEFAULT 0,   -- NTP-Drift / Video-Frame-Korrektur
    active              BOOLEAN NOT NULL DEFAULT true,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_used_at        TIMESTAMPTZ
);

-- Rohe Überquerungen der Rundenlinie. Unveränderlich; lap_index wird abgeleitet.
CREATE TABLE timing_record (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id            UUID NOT NULL REFERENCES event(id) ON DELETE CASCADE,
    bib_number          INT  NOT NULL,      -- roh; muss (noch) nicht zugeordnet sein
    absolute_time       TIMESTAMPTZ NOT NULL,  -- Gerätezeit + time_offset angewandt
    source_token_id     UUID REFERENCES device_token(id),
    dedup_key           TEXT NOT NULL,      -- Idempotenz pro Quelle
    lap_index           INT,                -- abgeleitet: n-te gültige Überquerung
    status              TEXT NOT NULL DEFAULT 'valid'
                          CHECK (status IN ('valid', 'ignored', 'duplicate', 'manual')),
    raw_payload         JSONB,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (event_id, dedup_key)
);
CREATE INDEX idx_timing_lookup ON timing_record(event_id, bib_number, absolute_time);

-- =========================================================================
-- Organisatoren (Admin-SPA) — RBAC
-- =========================================================================
CREATE TABLE app_user (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email       TEXT NOT NULL UNIQUE,
    name        TEXT,
    active      BOOLEAN NOT NULL DEFAULT true,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE user_role (
    user_id     UUID NOT NULL REFERENCES app_user(id) ON DELETE CASCADE,
    role        TEXT NOT NULL CHECK (role IN ('admin', 'race_office', 'timing', 'viewer')),
    PRIMARY KEY (user_id, role)
);

-- Kurzlebige Magic-Links für Organisator-Login.
CREATE TABLE auth_token (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL REFERENCES app_user(id) ON DELETE CASCADE,
    token_hash  TEXT NOT NULL UNIQUE,
    expires_at  TIMESTAMPTZ NOT NULL,
    used_at     TIMESTAMPTZ,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
