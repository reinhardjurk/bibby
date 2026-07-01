# Bibby — Vollständige Projektspezifikation

Diese Datei beschreibt das Projekt **vollständig und implementierungsunabhängig**,
sodass es aus dieser Spezifikation neu gebaut werden kann. Sie enthält alle
fachlichen Anforderungen, Architektur- und Design-Entscheidungen, das komplette
Datenmodell, die Geschäftslogik, alle API-Endpunkte, die Frontend-Struktur und
die Konfiguration.

---

## 1. Zweck & Überblick

Bibby ist ein System für eine **jährlich stattfindende Laufveranstaltung** und
deckt ab:

1. **Anmeldung** der Läufer über ein Webformular (mit Bestätigungs-E-Mail).
2. **Selbstverwaltung** der Anmeldung durch die Läufer (Änderungen/Korrekturen).
3. **Zeiterfassung** während des Rennens (händisch + über eine separate
   CV-App/Kamera, beide gegen dieselbe API).
4. **Ergebnislisten** je Strecke, inkl. Altersklassen/Geschlecht.
5. **Jahresübergreifende** Teilnehmer-Statistik („nimmt zum 5. Mal teil").

**Serverless auf Scaleway**, Backend in **Python/FastAPI**, Frontend als
**Single-Page-App**.

### Wichtigstes Domänenkonzept: Rundenrennen mit benannten Strecken

- Gelaufen wird in **Runden** (Rundenlinie an Start/Ziel). Läufer melden sich für
  eine **Strecke** an, die eine bestimmte Rundenzahl (`lap_count`) hat.
- Eine Strecke wird über ihren **Namen** identifiziert, **nicht** über die
  Rundenzahl. Mehrere Strecken je Event dürfen dieselbe Rundenzahl haben, z. B.
  „3,3 km Running" (1 Runde), „3,3 km Walking" (1 Runde), „1 km Kinder" (1 Runde),
  sowie Mehrrunden-Varianten (2/3 Runden).
- `lap_count` = **Anzahl der Zielüberquerungen**, ab der ein Läufer dieser Strecke
  „im Ziel" ist. Zwischenzeiten (Splits) je Runde fallen dabei automatisch an.

---

## 2. Tech-Stack & Architektur

| Bereich | Technologie / Scaleway-Dienst |
|---|---|
| Frontend | React + Vite + TypeScript (SPA), eigenes leichtes i18n (de/en) |
| SPA-Hosting | Scaleway Object Storage + Website (404 → index.html Rewrite) |
| Backend | FastAPI, async SQLAlchemy 2.0, Deployment als Scaleway Serverless Container |
| Datenbank | Scaleway Serverless SQL Database (PostgreSQL), Migrationen via Alembic |
| Dateien | Object Storage (Startnummern-PDF) |
| E-Mail | Scaleway Transactional Email (TEM) |
| Secrets | Scaleway Secret Manager / Env-Variablen |
| IaC | Terraform (Scaleway Provider) |

Konfiguration ausschließlich über Umgebungsvariablen mit Präfix **`BIBBY_`**
(pydantic-settings). Backend-Domänenlogik liegt in einem `services`-Modul;
Router pro Bereich.

---

## 3. Datenmodell (PostgreSQL)

UUID-Primärschlüssel (Python-seitig `uuid4`), `timestamptz` in UTC,
`*_i18n`-Felder als JSONB `{"de": "...", "en": "..."}`.

### participant — jahresübergreifende Identität
- `id` UUID PK
- `match_key` TEXT UNIQUE — normalisiert: `lower(unaccent(last_name+first_name)) || '|' || birth_date`
- `first_name`, `last_name` TEXT
- `birth_date` DATE (at-rest verschlüsselt gedacht; öffentlich nur Jahr/Altersklasse)
- `gender` TEXT CHECK in ('f','m','x')
- `created_at` timestamptz

### event — jährliche Veranstaltung
- `id` UUID PK
- `name` TEXT
- `year` INT UNIQUE
- `event_date` DATE
- `location` TEXT NULL
- `default_start_time` timestamptz NULL — Massenstart-Fallback
- `registration_deadline` timestamptz NULL
- `tshirt_options` JSONB NULL — konfigurierbare T-Shirt-Optionen; NULL = Default
- `junior_cutoff_date` DATE NULL — wer am/nach diesem Datum geboren ist, zahlt ermäßigt; NULL = keine Ermäßigung
- `tshirt_included` BOOLEAN DEFAULT false — informativ (T-Shirt im Startgeld enthalten)
- `created_at` timestamptz

### competition — eine Strecke innerhalb eines Events
- `id` UUID PK
- `event_id` UUID FK → event ON DELETE CASCADE
- `lap_count` INT CHECK >= 1
- `title_i18n` JSONB NULL — Anzeigename (unterscheidet Strecken!)
- `start_time` timestamptz NULL — überschreibt event.default_start_time
- `price_cents` INT DEFAULT 0 — Erwachsenen-/Standardpreis
- `price_junior_cents` INT NULL — Jugendpreis (NULL = wie Erwachsene)
- `currency` TEXT DEFAULT 'EUR'
- **KEINE** Unique-Bedingung auf (event_id, lap_count) — mehrere Strecken dürfen dieselbe Rundenzahl haben

### category — Altersklassen-Regeln je Event
- `id` UUID PK
- `event_id` UUID FK → event CASCADE
- `code` TEXT (z. B. "M40", "W30"), UNIQUE(event_id, code)
- `label_i18n` JSONB NULL
- `gender` TEXT NULL CHECK in ('f','m','x') — NULL = geschlechtsoffen
- `min_age` INT NULL, `max_age` INT NULL

### registration — Anmeldung
- `id` UUID PK
- `event_id` UUID FK → event CASCADE
- `competition_id` UUID FK → competition
- `participant_id` UUID FK → participant
- `email` TEXT (kann je Jahr abweichen)
- `language` TEXT DEFAULT 'de'
- `team` TEXT NULL — optionale Teamzugehörigkeit
- `tshirt` TEXT NULL — gewählte T-Shirt-Option
- `status` TEXT DEFAULT 'confirmed' CHECK in ('confirmed','cancelled') — Anmeldung gilt sofort als bestätigt
- `finish_seconds` DOUBLE PRECISION NULL — gespeicherte Netto-Laufzeit (Snapshot, siehe §5.3)
- `manage_token_hash` TEXT UNIQUE — HMAC-Hash des Selbstverwaltungs-Tokens
- `consent_data` BOOLEAN DEFAULT false — Einwilligung Datenverarbeitung (Pflicht bei Anmeldung)
- `consent_publish` BOOLEAN DEFAULT false — Einwilligung Ergebnisveröffentlichung (optional)
- `created_at`, `updated_at` timestamptz
- **UNIQUE(event_id, participant_id)** — eine Person nicht doppelt je Event

### bib_assignment — Startnummer (global pro Event, streckenunabhängig)
- `id` UUID PK
- `event_id` UUID FK → event CASCADE
- `bib_number` INT
- `registration_id` UUID FK → registration CASCADE, UNIQUE
- `assigned_at` timestamptz
- **UNIQUE(event_id, bib_number)**

### payment — Zahlung (kein Online-PSP!)
- `id` UUID PK
- `registration_id` UUID FK → registration CASCADE
- `method` TEXT CHECK in ('sepa_debit','on_site')
- `amount_cents` INT — beim Anmelden berechneter Betrag (Snapshot)
- `currency` TEXT DEFAULT 'EUR'
- `status` TEXT DEFAULT 'pending' CHECK in ('pending','paid','cancelled')
- `iban_encrypted` TEXT NULL — IBAN app-seitig verschlüsselt (Fernet)
- `iban_masked` TEXT NULL — z. B. "DE89 **** 3000"
- `account_holder` TEXT NULL
- `mandate_reference` TEXT UNIQUE NULL — z. B. "BIBBY-2026-AB12CD34"
- `mandate_granted_at` timestamptz NULL
- `sepa_exported_at` timestamptz NULL — Zeitpunkt des letzten SEPA-CSV-Exports
- `created_at`, `updated_at` timestamptz

### timing_record — rohe Linien-Überquerung (unveränderlich)
- `id` UUID PK
- `event_id` UUID FK → event CASCADE
- `bib_number` INT — roh; muss (noch) nicht zugeordnet sein
- `absolute_time` timestamptz — Gerätezeit + Offset
- `source_token_id` UUID FK → device_token NULL
- `dedup_key` TEXT — Idempotenz je Quelle
- `lap_index` INT NULL — abgeleitet (n-te gültige Überquerung)
- `status` TEXT DEFAULT 'valid' CHECK in ('valid','ignored','duplicate','manual')
- `raw_payload` JSONB NULL
- `created_at` timestamptz
- **UNIQUE(event_id, dedup_key)**; Index (event_id, bib_number, absolute_time)

### device_token — Zeitnahme-Geräte (Web-Maske, CV-App)
- `id` UUID PK
- `event_id` UUID FK → event CASCADE
- `label` TEXT
- `token_hash` TEXT UNIQUE — HMAC-Hash; Klartext nur bei Erstellung ausgegeben
- `scope` TEXT DEFAULT 'timing:write'
- `time_offset_seconds` INT DEFAULT 0 — NTP-Drift / Video-Frame-Korrektur
- `active` BOOLEAN DEFAULT true
- `created_at`, `last_used_at` timestamptz

### app_user — Organisatoren (Admin-Login)
- `id` UUID PK
- `email` TEXT UNIQUE
- `name` TEXT NULL
- `password_hash` TEXT NULL — bcrypt
- `active` BOOLEAN DEFAULT true
- `created_at` timestamptz

### user_role — RBAC (Mehrfachrollen)
- `user_id` UUID FK → app_user CASCADE
- `role` TEXT CHECK in ('admin','race_office','timing','viewer')
- PK(user_id, role)

### auth_token — Session-Token
- `id` UUID PK
- `user_id` UUID FK → app_user CASCADE
- `token_hash` TEXT UNIQUE
- `expires_at` timestamptz (12 h TTL)
- `used_at` timestamptz NULL
- `created_at` timestamptz

### Migrationen (Alembic, additiv)
1. `0001` Baseline — alle Tabellen (via `Base.metadata.create_all`).
2. `0002` registration.team
3. `0003` app_user.password_hash
4. `0004` registration.finish_seconds
5. `0005` registration.tshirt + event.tshirt_options
6. `0006` competition.price_junior_cents + event.junior_cutoff_date + event.tshirt_included
7. `0007` payment.sepa_exported_at
8. `0008` DROP UNIQUE(event_id, lap_count) auf competition

Additive Migrationen verwenden `ADD COLUMN IF NOT EXISTS`, damit sie mit der
create_all-Baseline verträglich sind.

---

## 4. Rollen (RBAC) & Auth

- **admin** — alles (implizit alle Rechte), inkl. Event löschen, Benutzer.
- **race_office** — Anmeldungen bearbeiten, Startnummern, Teilnehmer mergen,
  Ergebnisse freigeben, Events anlegen/konfigurieren, Zahlungen, SEPA-Export.
- **timing** — Zeiten erfassen/korrigieren/löschen, Geräte-Tokens verwalten.
- **viewer** — nur Lesen/Export.

**Organisator-Login: passwortbasiert.** `POST /admin/auth/login {email, password}`
→ bcrypt-Prüfung → gibt bei Erfolg einen **Session-Token** zurück (AuthToken,
12 h). Fehler → 401 generisch (keine User-Enumeration). Alle `/admin/*`-Aufrufe
tragen `Authorization: Bearer <token>`. `require_roles(...)` prüft; `admin` ist
immer erlaubt.

**Zeitnahme-Auth getrennt:** Geräte-Tokens (`Authorization: Bearer <device-token>`)
für die Ingestion. Tokens werden nur als Hash gespeichert; Klartext einmalig bei
Erstellung ausgegeben (im Admin als QR-Code + Text).

Alle Tokens (Session, Manage-Link, Geräte) werden **nur als HMAC-Hash**
(`secret_key`) gespeichert.

---

## 5. Geschäftslogik

### 5.1 Teilnehmer-Identität
`match_key = normalize(last_name)+"|"+normalize(first_name)+"|"+birth_date.iso`,
`normalize` = NFKD, Diakritika entfernt, lowercase, getrimmt. Beim Anmelden:
existierenden participant per match_key finden oder neu anlegen. Admin kann zwei
participant-Datensätze **mergen** (Anmeldungen umhängen, Quelle löschen).

### 5.2 Startnummernvergabe
**Automatisch bei der Anmeldung**, fortlaufend pro Event
(`max(bib_number)+1`, Start konfigurierbar `bib_start_number`=1). Nebenläufigkeit
über einen transaktionsgebundenen **Advisory-Lock** pro Event
(`pg_advisory_xact_lock(hashtext('bib:'||event_id))`). Nachträglich änderbar
(Admin). Startnummer ist streckenunabhängig.

### 5.3 Zeiterfassung & Rundenableitung
- Eine **Ingestion-API** für alle Quellen (händische Web-Maske + CV-App):
  `POST /events/{id}/timings` mit Batch von `{bib_number, absolute_time, dedup_key, raw_payload?}`.
- **Idempotent** über `INSERT ... ON CONFLICT (event_id, dedup_key) DO NOTHING`.
- Zeit ist die **Gerätezeit** beim Erfassen; der pro Geräte-Token hinterlegte
  `time_offset_seconds` wird serverseitig addiert.
- **Rundenableitung** (`recompute_laps(event_id, bib)`), nach jedem Batch/Korrektur:
  gültige Überquerungen einer bib chronologisch durchgehen, `lap_index` 1..n
  vergeben; Überquerungen, die **< `min_lap_seconds` (=60 s)** nach der letzten
  gezählten liegen, werden als `duplicate` markiert (Prellschutz);
  Status `manual` zählt immer.
- **Zielzeit** = Überquerung mit `lap_index == competition.lap_count`.
  **Netto-Laufzeit** = `absolute_time − (competition.start_time || event.default_start_time)`.
- Ergebnisse werden in `build_results` **live** berechnet. Zusätzlich kann das
  Race-Office per Button „Alle Laufzeiten berechnen" (`recompute_event_times`)
  `registration.finish_seconds` als **Snapshot** persistieren (für die Liste).

### 5.4 Preisberechnung
`compute_price_cents(event, competition, birth_date)`:
- `is_junior = event.junior_cutoff_date != NULL && birth_date >= junior_cutoff_date`
- wenn junior und `competition.price_junior_cents != NULL` → Jugendpreis,
  sonst `competition.price_cents`.
- Wird **beim Anmelden** berechnet und in `payment.amount_cents` gespeichert
  (Snapshot; wird bei nachträglicher Admin-Änderung nicht automatisch neu berechnet).
- Das T-Shirt ist im Preis enthalten (Flag `tshirt_included`, informativ);
  die T-Shirt-Wahl (inkl. „Kein T-Shirt (Spende)") ändert den Betrag **nicht**.

### 5.5 Ergebnislisten
`build_results(competition, only_published=True)`:
- Alle bestätigten Anmeldungen der Strecke mit Startnummer; je Startnummer die
  Überquerungen mit `lap_index` laden → Splits + finish_seconds.
- Sortierung: Finisher nach Zeit, DNF ans Ende; **Rang nur für Finisher**,
  berechnet über das **gesamte** Finisher-Feld (Platzierungen bleiben korrekt).
- **DSGVO:** öffentliche Liste (`only_published=True`) filtert Läufer ohne
  `consent_publish` heraus; jede Zeile trägt ein `published`-Flag. Der interne
  Admin-Endpunkt liefert die Vollwertung (`only_published=False`).
- Zeilen enthalten zusätzlich `gender`, `category_code` (aus category-Regeln,
  Alter = `event.event_date.year − birth_year`) und `participation_count`
  (Anzahl Events mit bestätigter Anmeldung dieser Person → „X. Teilnahme").
- **Öffentliche Ansichten** (Frontend): (a) Gesamt, (b) nach Altersklasse,
  (c) nach Altersklasse & Geschlecht. Gruppierung + Platzierung je Gruppe wird
  clientseitig aus der zeitsortierten Liste berechnet.

### 5.6 Team
`registration.team` (frei). Anmelde- und Verwaltungsformular bieten
**Autovervollständigung** über bereits vergebene Teamnamen (`GET /teams`, natives
`<datalist>`). Auf der Verwaltungsseite wird zusätzlich das **letzte Team** der
Person (aus einer früheren Anmeldung) als Vorschlag vorbelegt.

### 5.7 Startnummern-PDF
`GET /manage/bib.pdf?token=` rendert ein A5-Quer-PDF (WeasyPrint) mit großer
Startnummer, Name, Event und Streckenname.

---

## 6. Zahlung (SEPA-Lastschrift oder Barzahlung)

**Kein Online-Payment-Provider.** Bei der Anmeldung wählt man:
- **SEPA-Lastschrift:** IBAN + Kontoinhaber + Einwilligung (Mandat). IBAN wird
  per **IBAN-Prüfung (Format + mod-97)** validiert, dann **app-seitig
  verschlüsselt** (Fernet, `field_encryption_key`) gespeichert; nur maskiert
  angezeigt. Eine **Mandatsreferenz** wird erzeugt (`BIBBY-{year}-{8 hex}`).
- **Barzahlung bei Abholung** der Startnummer.

Die Anmeldung gilt sofort als `confirmed`; `payment.status` startet `pending`.
Das **Race-Office** markiert „bezahlt" (`POST /admin/registrations/{id}/payment/mark-paid`).

**SEPA-CSV-Export** (`POST /admin/events/{id}/sepa-export`, Rolle race_office):
liefert eine CSV (Semikolon-getrennt, **UTF-8-BOM** für Excel) mit
`Startnummer;Teilnehmer;Kontoinhaber;IBAN(entschlüsselt);Betrag;Waehrung;Mandatsreferenz;Mandatsdatum;Verwendungszweck`
der **offenen, noch nicht exportierten** SEPA-Lastschriften. Setzt bei den
enthaltenen Zahlungen `sepa_exported_at = now` → erkennbar, was schon abgerechnet
ist. Query `?include_exported=true` schließt bereits exportierte wieder ein. Der
eigentliche Lastschrifteinzug läuft offline (Banking/SEPA-XML pain.008 — noch
nicht implementiert).

---

## 7. E-Mail (Scaleway TEM)

`send_email(to, subject, text, html?)`:
- **Test-Modus** (`mail_test_mode`, Standard **an**): leitet **alle** Mails an
  `mail_test_recipient` um; der echte Empfänger steht im Betreff `[TEST → …]`.
- Ohne `tem_secret_key` wird die Mail nur geloggt (lokale Entwicklung).
- Versand: `POST https://api.scaleway.com/transactional-email/v1alpha1/regions/{region}/emails`
  mit Header **`X-Auth-Token: <Secret Key>`** (nur der Secret Key des Scaleway-
  API-Keys, **kein** Access Key ID) und Body
  `{from:{email,name}, to:[{email}], subject, text, html?, project_id}`.
- Absender-Domäne muss in TEM verifiziert sein.
- **Mailfehler dürfen die Anmeldung nicht scheitern lassen** (nur loggen).

Bestätigungsmail bei Anmeldung: lokalisiert (de/en), enthält den Verwaltungslink
`{public_base_url}/manage?token=…`.

---

## 8. API-Endpunkte

Lebende Referenz zusätzlich: FastAPI `/docs`.

### Öffentlich (keine Auth)
- `GET /health`
- `GET /events` — inkl. tshirt_options, junior_cutoff_date, tshirt_included
- `GET /events/{id}/competitions` — inkl. price_cents, price_junior_cents, start_time
- `GET /teams` — distinct vergebene Teamnamen
- `POST /registrations` — Anmeldung (vergibt Startnummer, legt Payment an, mailt)
- `GET /events/{id}/results?competition_id=` — öffentliche Ergebnisliste

### Selbstverwaltung (Magic-Link-Token in Query)
- `GET /manage?token=` — Anmeldung ansehen (inkl. team, tshirt+optionen, Zahlung)
- `PATCH /manage?token=` — ändern (email, language, competition_id, consent_publish, team, tshirt)
- `GET /manage/bib.pdf?token=` — Startnummer-PDF

### Zeiterfassung
- `POST /events/{id}/timings` — Geräte-Token — Batch-Ingestion (idempotent)
- `GET /events/{id}/timings/{bib}` — Session (timing/race_office/viewer) — Überquerungen
- `PATCH /timings/{id}` — Session (timing) — korrigieren (Zeit/Status/bib; recompute alt+neu)
- `DELETE /timings/{id}` — Session (timing) — löschen (recompute)

### Admin (`/admin`, Bearer Session-Token, RBAC)
- `POST /admin/auth/login` — Passwort-Login → SessionToken
- `GET /admin/me` — eigene Rollen
- `GET /admin/registrations?event_id=&q=&limit=&offset=` — paginierte Suche/Liste (default 50, max 200)
- `GET /admin/registrations/{id}` — Detail (alle Felder inkl. tshirt_options)
- `PATCH /admin/registrations/{id}` — race_office — Voll-Bearbeitung aller Felder
  (Identität ändert match_key → Kollision 409; nutzt `model_fields_set` für nullable-Clearing)
- `POST /admin/registrations/{id}/bib?bib_number=` — race_office
- `POST /admin/registrations/{id}/reassign {competition_id}` — race_office
- `POST /admin/registrations/{id}/payment/mark-paid` — race_office
- `POST /admin/events/{id}/sepa-export?include_exported=` — race_office — CSV
- `POST /admin/participants/merge {source, target}` — race_office
- `POST /admin/events {name,year,event_date,…,competitions:[…]}` — race_office — neues Event + Strecken
- `DELETE /admin/events/{id}` — **admin** — Event + abhängige Daten (Kaskade), Teilnehmer bleiben
- `PATCH /admin/events/{id} {tshirt_options?, junior_cutoff_date?, tshirt_included?}` — race_office
- `PATCH /admin/competitions/{id} {start_time?, price_cents?, price_junior_cents?}` — race_office
- `POST /admin/events/{id}/recompute-times` — race_office — alle Laufzeiten neu berechnen/speichern
- `GET /admin/events/{id}/results?competition_id=` — Vollwertung (inkl. nicht-öffentliche)
- `GET|POST /admin/events/{id}/device-tokens` — timing — auflisten / anlegen (Klartext einmalig)
- `DELETE /admin/device-tokens/{id}` — timing — sperren

---

## 9. Frontend (SPA)

Zwei Layout-Bereiche mit eigener Navigation:

### Läufer-Bereich (öffentlich)
- `/teilnahme` — Anmeldeformular (Event, Strecke, Person, E-Mail, Team, T-Shirt,
  Preis-Live-Anzeige, Zahlungsweg, Einwilligungen). Nach Absenden:
  Verwaltungslink + Startnummer + PDF-Link (+ Mandatsreferenz bei SEPA).
- `/teilnahme/ergebnisse` — Ergebnislisten (Ansichten: Gesamt / Altersklasse / Altersklasse & Geschlecht)
- `/manage?token=…` — Selbstverwaltung (E-Mail, Strecke, Team, T-Shirt ändern; Status/Startnummer/Zahlung; PDF)
- `/` → Weiterleitung auf `/teilnahme`

### Staff-Bereich (Login/Rollen bzw. Geräte-Token)
- `/team` — **Admin**: Suche (Name/Startnummer) + Voll-Bearbeitung
- `/team/special` — **Special-Admin** (operativ): paginierte Anmeldungsliste
  (+ „Laufzeiten berechnen"), Erfassungen je Startnummer (korrigieren/löschen),
  interne Vollwertung, Geräte-Tokens (mit QR-Code)
- `/team/veryspecial` — **Event-Verwaltung**: Event anlegen/löschen,
  Event-Einstellungen (T-Shirt-Optionen, Jugend-Stichtag, T-Shirt inklusive),
  Strecken & Startzeiten/Preise
- `/team/sepa` — **SEPA-Export**
- `/team/zeiterfassung` — **Zeiterfassung** (Kiosk)

Weiterleitungen alter Pfade: `/results`→`/teilnahme/ergebnisse`,
`/admin`→`/team`, `/special-admin`→`/team/special`,
`/timing?…`→`/team/zeiterfassung?…`.

### Zeiterfassungs-Seite (Kiosk)
- Einrichtung: Event wählen + Geräte-Token eingeben (in `localStorage`) **oder**
  QR-Code scannen (URL `/team/zeiterfassung?token=…&event=…`, wird nach Übernahme
  aus der Adresszeile entfernt).
- Erfassung: **grafisches Ziffernfeld** (Anzeige + Ziffern 0–9, C, ⌫, großer
  ERFASSEN-Button) — keine Handytastatur. Beim Druck wird die **Gerätezeit sofort**
  festgehalten.
- **Robustheit:** Erfasste Paare landen in einer **in `localStorage`
  persistierten Warteschlange** und werden per Auto-Retry (alle 4 s + beim Laden)
  gesendet → überlebt Reload/Absturz/Offline.

### i18n
Eigener leichter Provider: Wörterbuch de/en, `useI18n().t(key, vars)`,
Platzhalter `{name}`. Sprache in `localStorage`. QR-Code **clientseitig**
gerendert (Token darf nicht an externen Dienst).

---

## 10. Konfiguration (Env `BIBBY_*`)

- `database_url` (asyncpg; in Prod SSL via connect_args nötig)
- `secret_key` — HMAC für Token-Hashing
- `public_base_url` — Basis-URL der SPA (Links in Mails)
- `field_encryption_key` — Fernet-Key für IBAN (Prod fest; sonst aus secret_key abgeleitet)
- `bib_start_number` (=1)
- `default_tshirt_options` (=["Kein T-Shirt (Spende)","XS","S","M","L","XL"])
- `min_lap_seconds` (=60)
- `default_currency` (="EUR")
- SEPA-Mandat: `sepa_creditor_name`, `sepa_creditor_id`
- TEM: `tem_secret_key` (nur Secret Key!), `tem_project_id`, `scw_region` (fr-par),
  `tem_from_email` (verifizierte Domäne), `tem_from_name`
- Mail-Test: `mail_test_mode` (=true), `mail_test_recipient`
- `cors_origins` — erlaubte SPA-Origins

---

## 11. Lokale Entwicklung & Deployment

**Lokal:** Docker-Compose = PostgreSQL + API-Container. Der Container-Befehl:
`alembic upgrade head && python -m app.seed && uvicorn --reload`. Frontend per
`npm run dev`. Seed legt Demo-Daten an (Events 2025/2026, mehrere Läufer inkl.
einer SEPA-Anmeldung mit gültiger Test-IBAN `DE89370400440532013000`,
Admin-User `admin@example.com` / Passwort `admin`, Jugend-Stichtag 2008-01-01,
Preise Erw./Jugend, T-Shirt inklusive).

**Scaleway (Terraform):** Serverless SQL, Container-Registry, Serverless
Container (FastAPI, IAM-Key für DB), Object-Storage-Buckets (SPA-Website +
privat für PDFs), TEM-Domäne, Secrets als env. Deploy: `terraform apply` →
Image bauen & pushen → Migrationen einspielen → SPA bauen & hochladen →
TEM-DNS setzen. **In Prod laufen Migrationen nicht automatisch** (Container
startet nur uvicorn) und der **Seed darf nicht laufen**.

---

## 12. Bekannte offene Punkte / Nicht-Ziele

- CV-App (Bilderkennung bib/Zeit) ist ein **separates Projekt**; nutzt denselben
  Ingestion-Endpunkt mit Geräte-Token.
- pain.008-SEPA-XML (nur CSV vorhanden).
- Betrags-Neuberechnung bei nachträglicher Admin-Änderung (Betrag ist Snapshot).
- asyncpg-SSL-`connect_args` für Serverless SQL (Prod).
- CDN/TLS/eigene Domäne via Scaleway Edge Services (nur Object-Storage-Website).
- Login-Härtung (Einmal-Token gegen Session tauschen).
- Benutzerverwaltung im UI (weitere Organisatoren/Passwörter) — aktuell nur Seed.
- Prod-Migrations-Ablauf (separater Schritt/Job).
