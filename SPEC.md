# Bibby — Vollständige Projektspezifikation

Diese Datei beschreibt das Projekt **vollständig und implementierungsunabhängig**,
sodass daraus weitergearbeitet oder neu gebaut werden kann. Sie enthält alle
fachlichen Anforderungen, Architektur-/Design-Entscheidungen, das komplette
Datenmodell, die Geschäftslogik, alle API-Endpunkte, die Frontend-Struktur, die
Konfiguration und den Deploy-Ablauf. **Stand: 2026-07-14** (Git-HEAD-Feature-Set;
Repo `github.com/reinhardjurk/bibby`, Branch `main`).

> Ergänzend zu dieser Datei liegt im Projektgedächtnis (`memory/bibby-project.md`,
> `memory/bibby-scaleway-prod.md`) der Prod-/Deploy-Kontext (Scaleway-IDs, Fallen).

---

## 1. Zweck & Überblick

Bibby ist ein System für eine **jährlich stattfindende Laufveranstaltung**
(Gröbenzeller Familienlauf) und deckt ab:

1. **Anmeldung** über ein Webformular (mit Bestätigungs-E-Mail + Verwaltungslink).
2. **Selbstverwaltung** der Anmeldung durch die Läufer (Änderungen/Korrekturen).
3. **Zeiterfassung** während des Rennens (händisch + über eine separate CV-App,
   beide gegen dieselbe API), inkl. mehrerer Zeitnehmer je Ziellinie.
4. **Ergebnislisten** je Strecke, inkl. Altersklassen/Geschlecht.
5. **Urkundendruck** (einzeln, gruppenweise, komplett) auf Event-Vorlage.
6. **Sponsorenanzeige** (5 gewichtete Klassen, Rotation oder Laufband).
7. **Jahresübergreifende** Teilnehmer-Statistik („nimmt zum 5. Mal teil").

**Serverless auf Scaleway**, Backend **Python/FastAPI**, Frontend **SPA**.
Läuft live unter **https://anmeldung.run-bibby.de**.

### Wichtigstes Domänenkonzept: benannte Strecken, EIN Zieldurchlauf

- Es gibt **kein Rundenkonzept mehr** (früher entfernt). Jeder Teilnehmer
  überquert die Ziellinie im Rahmen seiner Wertung; die **Zielzeit ist der
  Mittelwert ALLER (nicht-ignorierten) Erfassungen** dieser Startnummer minus der
  Startzeit der Strecke (mehrere Zeitnehmer, die dieselbe Ankunft erfassen, werden
  automatisch gemittelt — siehe §5.3).
- Eine **Strecke** (`competition`) wird über ihren **Namen** identifiziert.
  Mehrere Strecken je Event sind erlaubt (z. B. „3,3 km Running", „3,3 km Walking",
  „1 km Kinder"). Das Feld `lap_count` existiert noch als **vestigiale Spalte
  (Default 1)**, hat aber keine Wirkung und ist aus UI/Logik entfernt.
- Jede Strecke konfiguriert ihre **Wertung** selbst: Altersklassen-Schema
  (5-Jahres / 1-Jahres / keine) und Geschlechtswertung (ja/nein) — siehe §5.5.

---

## 2. Tech-Stack & Architektur

| Bereich | Technologie / Scaleway-Dienst |
|---|---|
| Frontend | React 18 + Vite + TypeScript (SPA), eigenes leichtes i18n (de/en), react-router-dom v6, qrcode.react |
| SPA-Hosting | Object Storage + Website (Error-Doc `index.html`), davor **Edge Services** (managed TLS + eigene Domain) |
| Backend | FastAPI, async SQLAlchemy 2.0, asyncpg, Scaleway Serverless Container |
| Datenbank | Scaleway Serverless SQL (PostgreSQL hinter Pooler), Alembic-Migrationen |
| PDF | WeasyPrint (Startnummern + Urkunden); Pillow (Sponsoren-Bildskalierung) |
| E-Mail | Scaleway Transactional Email (TEM) |
| Crypto | Fernet (IBAN), bcrypt (Passwörter), HMAC-SHA256 (Token-Hashing) |
| IaC | Terraform/OpenTofu (`tofu`), Scaleway Provider ~> 2.40 |

- Konfiguration ausschließlich über Env-Variablen mit Präfix **`BIBBY_`**
  (pydantic-settings). **Kein** `if local/prod` im Code — Prod-Werte injiziert
  Terraform als `BIBBY_*`; lokal greifen `.env`/Defaults (Twelve-Factor).
- Backend-Domänenlogik in `backend/app/services.py`; Router je Bereich in
  `backend/app/routers/` (`events`, `registrations`, `manage`, `timing`,
  `results`, `sponsors`, `admin`).

---

## 3. Datenmodell (PostgreSQL)

UUID-PK (Python `uuid4`), `timestamptz` in UTC, `*_i18n` als JSONB
`{"de": "...", "en": "..."}`. ORM in `backend/app/models.py`.

### participant — jahresübergreifende Identität
`id` PK · `match_key` TEXT UNIQUE (normalisiert, §5.1) · `first_name`,
`last_name` · `birth_date` DATE · `gender` CHECK in ('f','m','x') · `created_at`.

### event — jährliche Veranstaltung
`id` · `name` · `year` INT UNIQUE · `event_date` DATE · `location` NULL ·
`default_start_time` timestamptz NULL (Massenstart-Fallback) ·
`registration_deadline` NULL · `tshirt_options` JSONB NULL ·
`junior_cutoff_date` DATE NULL (ab hier ermäßigt) · `tshirt_included` BOOL ·
**`certificate_bg`** BYTEA NULL (Urkunden-Hintergrundbild) ·
**`certificate_bg_mime`** TEXT NULL · **`certificate_offset`** INT DEFAULT 0
(vertikaler Druckversatz in „Zeilen", ±; 1 Zeile ≈ 8 mm) · `created_at`.

### competition — eine Strecke innerhalb eines Events
`id` · `event_id` FK CASCADE · `lap_count` INT (**vestigial**, Default 1) ·
`title_i18n` JSONB NULL (Anzeigename, unterscheidet Strecken) · `start_time`
timestamptz NULL (überschreibt `event.default_start_time`) · `price_cents` ·
`price_junior_cents` NULL · `currency` DEFAULT 'EUR' ·
**`age_class_scheme`** TEXT DEFAULT 'five' ('five'|'one'|'none') ·
**`gender_scoring`** BOOL DEFAULT true. Keine Unique-Bedingung auf lap_count.

### category — Altersklassen-Regeln (DEPRECATED, ungenutzt)
Tabelle existiert noch, wird aber **nicht mehr benutzt** — Altersklassen werden
berechnet (§5.5).

### registration — Anmeldung
`id` · `event_id` FK CASCADE · `competition_id` FK · `participant_id` FK ·
`email` · `language` DEFAULT 'de' · `team` TEXT NULL · `tshirt` TEXT NULL ·
`status` DEFAULT 'confirmed' CHECK in ('confirmed','cancelled') ·
`finish_seconds` DOUBLE NULL (gespeicherte Netto-Zeit, Snapshot; §5.3) ·
`manage_token_hash` TEXT UNIQUE · `consent_data` BOOL · `consent_publish` BOOL ·
`created_at`,`updated_at` · **UNIQUE(event_id, participant_id)**.

### bib_assignment — Startnummer (global pro Event)
`id` · `event_id` FK CASCADE · `bib_number` INT · `registration_id` FK CASCADE
UNIQUE · `assigned_at` · **UNIQUE(event_id, bib_number)**.

### payment — Zahlung (kein Online-PSP)
`id` · `registration_id` FK CASCADE · `method` CHECK ('sepa_debit','on_site') ·
`amount_cents` (Snapshot) · `currency` · `status` CHECK
('pending','paid','cancelled') · `iban_encrypted` (Fernet) · `iban_masked` ·
`account_holder` · `mandate_reference` UNIQUE NULL · `mandate_granted_at` ·
`sepa_exported_at` timestamptz NULL · `created_at`,`updated_at`.

### timing_record — rohe Linien-Überquerung
`id` · `event_id` FK CASCADE · `bib_number` INT · `absolute_time` timestamptz
(Gerätezeit + Offset) · `source_token_id` FK NULL · `dedup_key` TEXT ·
`lap_index` INT NULL (**vestigial**, wird nicht mehr gesetzt/gelesen) ·
`status` DEFAULT 'valid' CHECK ('valid','ignored','duplicate','manual') ·
`raw_payload` JSONB NULL · `created_at` · **UNIQUE(event_id, dedup_key)**.

### device_token — Zeitnahme-Geräte
`id` · `event_id` FK CASCADE · `label` · `token_hash` TEXT UNIQUE ·
**`token_plain`** TEXT NULL (menschenlesbarer Klartext-Code, **dauerhaft
sichtbar** — bewusst gespeichert) · `scope` DEFAULT 'timing:write' ·
`time_offset_seconds` INT · `active` BOOL · `created_at`,`last_used_at`.

### app_user / user_role / auth_token
`app_user`: `email` UNIQUE, `password_hash` (bcrypt), `active`. `user_role`:
PK(user_id, role), role CHECK ('admin','race_office','timing','viewer').
`auth_token`: `token_hash` UNIQUE, `expires_at` (**72 h TTL**), `used_at`.

### app_setting — Laufzeit-Konfiguration (key/value)
`key` TEXT PK · `value` TEXT · `updated_at`. Nutzung: `mail_test_mode` (Live/Test
umschaltbar ohne Redeploy), `sponsor_tiers` (JSON), `sponsor_display`
('rotate'|'marquee'), `sponsor_marquee_seconds`. Überschreibt — falls gesetzt —
den Env-Default.

### sponsor — Sponsorenlogo
`id` · `tier` INT CHECK 1..5 (die „Klasse"/„Ordner") · `name` TEXT NULL ·
`url` TEXT NULL (Ziel beim Klick) · `image` BYTEA · `image_mime` TEXT ·
`created_at`.

### Migrationen (Alembic, additiv, `backend/alembic/versions/`)
`0001` Baseline (create_all) · `0002` registration.team · `0003`
app_user.password_hash · `0004` registration.finish_seconds · `0005`
registration.tshirt + event.tshirt_options · `0006` price_junior_cents +
junior_cutoff_date + tshirt_included · `0007` payment.sepa_exported_at · `0008`
DROP UNIQUE(event_id,lap_count) · **`0009`** app_setting · **`0010`**
event.certificate_bg(+mime) · **`0011`** event.certificate_offset · **`0012`**
device_token.token_plain · **`0013`** competition.age_class_scheme +
gender_scoring · **`0014`** sponsor · **`0015`** sponsor.url.
Additive Migrationen nutzen `ADD COLUMN/CREATE TABLE IF NOT EXISTS` (verträglich
mit der create_all-Baseline).

---

## 4. Rollen (RBAC) & Auth

- **admin** — alles (implizit alle Rechte), inkl. Event löschen, Mail-Modus live.
- **race_office** — Anmeldungen, Startnummern, Merge, Events/Strecken, Zahlungen,
  SEPA, Sponsoren, Urkunden/Ergebnisdruck.
- **timing** — Zeiten erfassen/korrigieren/löschen/manuell anlegen, Geräte-Tokens.
- **viewer** — nur Lesen/Export.

**Login passwortbasiert:** `POST /admin/auth/login {email,password}` → bcrypt →
Session-Token (`auth_token`, **72 h**). Fehler → 401 generisch. `/admin/*` trägt
`Authorization: Bearer <token>`; `require_roles(...)` prüft, **`admin` ist immer
erlaubt** (`security.py`). Zeitnahme-Auth getrennt über Geräte-Tokens. Session-
und Manage-Token werden **nur als HMAC-Hash** (`secret_key`) gespeichert; der
Geräte-Code liegt zusätzlich im Klartext (`token_plain`), damit er dauerhaft
angezeigt werden kann.

---

## 5. Geschäftslogik (`services.py`)

### 5.1 Teilnehmer-Identität
`match_key = normalize(last)+"|"+normalize(first)+"|"+birth_date.iso`,
`normalize` = NFKD, Diakritika weg, lowercase, getrimmt. Beim Anmelden per
match_key finden oder neu anlegen. Admin kann zwei participant **mergen**.

### 5.2 Startnummernvergabe
Automatisch bei der Anmeldung, fortlaufend `max(bib)+1` (Start
`bib_start_number`=1), Nebenläufigkeit über `pg_advisory_xact_lock` pro Event.
Nachträglich änderbar. Streckenunabhängig.

### 5.3 Zeiterfassung & Zielzeit (OHNE Runden)
- Eine **Ingestion-API** für alle Quellen: `POST /events/{id}/timings` mit Batch
  `{bib_number, absolute_time, dedup_key, raw_payload?}`. **Idempotent** über
  `ON CONFLICT (event_id, dedup_key) DO NOTHING`. `time_offset_seconds` des
  Geräts wird serverseitig addiert.
- **Zielzeitpunkt einer Startnummer = Mittelwert ALLER Erfassungen mit
  `status != 'ignored'`** (`services.bib_finish_datetime` + `_mean_datetime`).
  Kein `recompute_laps`, kein `lap_index` mehr.
- **Netto-Laufzeit = Mittelwert − (competition.start_time || event.default_start_time)**.
  Fehlt die Startzeit → **DNF** (häufigste Support-Ursache!). `status='ignored'`
  schließt eine Fehlerfassung aus.
- Ergebnisse werden in `build_results` **live** berechnet. Zusätzlich persistiert
  „Alle Laufzeiten berechnen" (`recompute_event_times`) `registration.finish_seconds`
  als Snapshot; Rückgabe = Anzahl tatsächlich ermittelter Zeiten (0 = klares
  Signal für fehlende Startzeit/Erfassung).
- **Manuelle Erfassung** (`POST /events/{id}/timings/{bib}/manual`, Rolle timing):
  legt einen Record mit `status='manual'` an — auch wenn für die Nummer noch keine
  Erfassung existiert.

### 5.4 Preisberechnung
`compute_price_cents(event, competition, birth_date)`: `is_junior` = geboren
am/nach `event.junior_cutoff_date` → `competition.price_junior_cents` (falls
gesetzt), sonst `price_cents`. Berechnet **beim Anmelden**, gespeichert als
`payment.amount_cents` (Snapshot). T-Shirt-Wahl ändert den Betrag nicht.

### 5.5 Ergebnisse, Altersklassen & Platzierungen
- **Altersklasse wird berechnet** (`compute_age_class(age, scheme)`,
  `age = event.event_date.year − birth_year`), je nach `competition.age_class_scheme`:
  `five` → U20, AK20 (20–24), AK25, AK30 …; `one` → `AK<alter>` (z. B. AK41);
  `none` → keine Altersklasse. Die `category`-Tabelle wird **nicht** genutzt.
- `build_results(competition, only_published=True)` liefert `ResultRow`
  {rank, bib_number, first_name, last_name, gender, category_code, team,
  finish_seconds, splits=[] (leer), participation_count, published}. Sortierung:
  Finisher nach Zeit, DNF ans Ende; **Rang über das ganze Feld**.
- **DSGVO:** öffentliche Liste filtert `consent_publish=false` heraus (Ränge
  trotzdem übers ganze Feld); interner Admin-Endpunkt = Vollwertung.
- **Vier Platzierungen** (`placement_from_rows`): gesamt, gesamt je Geschlecht,
  Altersklasse, Altersklasse je Geschlecht. `certificate_lines(placement, lang,
  gender_scoring)` blendet je Streckenkonfig die passenden Zeilen ein (keine
  Geschlechtszeilen ohne `gender_scoring`; keine AK-Zeilen bei Schema `none`).
- `participation_count` = Anzahl Events mit bestätigter Anmeldung dieser Person.

### 5.6 Team
`registration.team` (frei), Autovervollständigung über `GET /teams`
(`<datalist>`); Verwaltungsseite schlägt das letzte Team der Person vor.

### 5.7 PDFs (WeasyPrint)
- **Startnummer:** `GET /manage/bib.pdf?token=` — A5 quer, Nummer/Name/Event/Strecke.
- **Urkunde:** A4 hoch, Inhalt per Flexbox **mittig** zentriert, Reihenfolge
  **Name · Startnummer · Team (falls vorhanden) · Zeit · Platzierungen**. Auf
  optionale Event-Hintergrundvorlage (`event.certificate_bg`) gelegt, vertikal
  verschoben um `event.certificate_offset` Zeilen. `render_certificates_pdf`
  rendert **mehrseitig** (eine Urkunde je Seite); `render_certificate_pdf` ist der
  Einzel-Wrapper. Teilnehmer holen ihre Urkunde über
  `GET /manage/certificate.pdf?token=` (nur wenn `finish_seconds` gesetzt).

### 5.8 Sponsoren
- 5 **Klassen** (`tier` 1..5). Konfiguration je Klasse in `app_setting`
  (`sponsor_tiers` JSON): `weight` (Zeitanteil in der Rotation, z. B. 30:20:10:5:1)
  und `height` (MAX-Anzeigehöhe px). Anzeigemodus (`sponsor_display`) =
  `rotate` oder `marquee`; Laufband-Dauer `sponsor_marquee_seconds` (5–300).
- **Rotation:** pro 5-s-Slot wird die Klasse **nach Gewicht gelost** (→ exaktes
  Zeitverhältnis), innerhalb der Klasse Round-Robin; immer **genau EIN** Logo im
  DOM (minimaler Load).
- **Laufband:** alle Logos scrollen endlos (Größe je Klasse), nahtlose Schleife
  (Track verdoppelt, `translateX(-50%)`), respektiert `prefers-reduced-motion`.
- **Feste Bandhöhe** (= größte Klassenhöhe) → die Leiste ändert ihre Größe beim
  Logowechsel nie; Logos werden per `object-fit: contain` skaliert.
- Beim Upload werden **Raster-Logos serverseitig** (Pillow) auf 400 px Höhe
  herunterskaliert und als PNG gespeichert; **SVG** bleibt vektoriell. Logos mit
  hinterlegter **URL** sind klickbar (neuer Tab, `rel=noopener`).

---

## 6. Zahlung (SEPA-Lastschrift oder Barzahlung)

Kein Online-PSP. Anmeldung wählt **SEPA-Lastschrift** (IBAN + Kontoinhaber +
Mandat; IBAN mod-97-geprüft, Fernet-verschlüsselt, nur maskiert; Mandatsref
`BIBBY-{year}-{8hex}`) oder **Barzahlung bei Abholung**. Anmeldung sofort
`confirmed`, `payment.status='pending'`; Race-Office markiert „bezahlt".
**SEPA-CSV-Export** (`POST /admin/events/{id}/sepa-export`): Semikolon-CSV mit
UTF-8-BOM (Startnummer;Teilnehmer;Kontoinhaber;IBAN;Betrag;Waehrung;Mandatsref;
Mandatsdatum;Verwendungszweck) der offenen, noch nicht exportierten Lastschriften;
setzt `sepa_exported_at`; `?include_exported=true` schließt wieder ein. pain.008-
XML noch nicht implementiert.

---

## 7. E-Mail (Scaleway TEM)

`mailer.send_email(to, subject, text, html?, test_mode?)`:
- **Test-Modus** (`mail_test_mode`, Default an; zur **Laufzeit umschaltbar** via
  `app_setting`, Endpunkte `GET/PATCH /admin/mail-settings`, PATCH nur admin):
  leitet **alle** Mails an `mail_test_recipient` um, echter Empfänger im Betreff.
- Ohne `tem_secret_key` nur Log (lokal). Versand:
  `POST …/transactional-email/v1alpha1/regions/{region}/emails`, Header
  **`X-Auth-Token: <Secret Key>`** (nur Secret Key!), Body
  `{from:{email,name}, to:[{email}], subject, text, html?, project_id}`.
- **Mailfehler dürfen die Anmeldung nicht scheitern lassen** — werden nur
  geloggt (⇒ Mailprobleme via direktem `curl` gegen TEM debuggen, nicht via App).
- Prod: Domain `mail.run-bibby.de` verifiziert (MX/SPF/DKIM/DMARC), Absender
  `no-reply@mail.run-bibby.de`. **DKIM-Selector = Scaleway-Project-ID.**

---

## 8. API-Endpunkte

Lebende Referenz zusätzlich: FastAPI `/docs`.

### Öffentlich
- `GET /health` · `GET /version` (Backend-Build + DB-Schema-Revision)
- `GET /events` (inkl. tshirt_options, junior_cutoff_date, tshirt_included,
  has_certificate_background, certificate_offset)
- `GET /events/{id}/competitions` (inkl. price_*, start_time, age_class_scheme,
  gender_scoring)
- `GET /teams` · `POST /registrations` · `GET /events/{id}/results?competition_id=`
- `GET /sponsors` (Metadaten + tiers/display/marquee_seconds, **ohne** Bild-Blob)
- `GET /sponsors/{id}/image` (Bild, `Cache-Control: immutable 7d`)

### Selbstverwaltung (Manage-Token in Query)
- `GET /manage?token=` · `PATCH /manage?token=`
- `GET /manage/bib.pdf?token=` · `GET /manage/certificate.pdf?token=`

### Zeiterfassung
- `POST /events/{id}/timings` (Geräte-Token, Batch, idempotent)
- `POST /events/{id}/timings/{bib}/manual` (Session timing — Einzel anlegen)
- `GET /events/{id}/timings/{bib}` · `PATCH /timings/{id}` · `DELETE /timings/{id}`

### Admin (`/admin`, Bearer, RBAC)
- `POST /auth/login` · `GET /me`
- `GET/PATCH /mail-settings` (Test/Live; PATCH nur admin)
- Anmeldungen: `GET /registrations?event_id=&q=&limit=&offset=` ·
  `GET/PATCH /registrations/{id}` · `POST /registrations/{id}/bib?bib_number=` ·
  `POST /registrations/{id}/reassign` · `POST /registrations/{id}/payment/mark-paid`
- `POST /participants/merge` · `POST /events` · `DELETE /events/{id}` (admin) ·
  `PATCH /events/{id}` (tshirt_options, junior_cutoff_date, tshirt_included,
  **certificate_offset**) · `POST /events/{id}/certificate-background` (Upload)
- `PATCH /competitions/{id}` (start_time, price_*, **age_class_scheme,
  gender_scoring**)
- `POST /events/{id}/recompute-times` · `GET /events/{id}/results?competition_id=`
- `POST /events/{id}/sepa-export?include_exported=`
- Geräte-Tokens: `GET/POST /events/{id}/device-tokens` · `DELETE /device-tokens/{id}`
- **Ergebnisdruck/Urkunden:**
  `GET /events/{id}/competitions/{cid}/certificate-groups` (config-getriebene
  Wertungsgruppen [Altersklasse × Geschlecht]) ·
  `GET /events/{id}/competitions/{cid}/certificates?age_class=&gender=&background=&lang=`
  (Sammel-PDF je Gruppe) ·
  `GET /events/{id}/competitions/{cid}/certificates-all?background=&lang=`
  (alle Urkunden, sortiert AK↑→Geschlecht→**schlechteste Platzierung zuerst**) ·
  `GET /events/{id}/certificate?bib=&background=&lang=` (Einzel per Startnummer)
- **Sponsoren:** `POST /sponsors` (Upload, Form: tier,name,url,file) ·
  `PATCH /sponsors/{id}` (name,url) · `DELETE /sponsors/{id}` ·
  `PATCH /sponsor-tiers` (Gewicht/Höhe je Klasse) ·
  `PATCH /sponsor-display` (mode + optional marquee_seconds)

---

## 9. Frontend (SPA)

Zwei Layout-Bereiche mit eigener Navigation (`components/Layouts.tsx`).

### Läufer-Bereich (öffentlich)
- `/teilnahme` — Anmeldeformular (Event, Strecke, Person, E-Mail, Team, T-Shirt,
  Preis-Live-Anzeige, Zahlungsweg, Einwilligungen). Nach Absenden: Verwaltungslink
  + Startnummer + PDF (+ Mandatsref bei SEPA). **`<SponsorBar />` oben und unten.**
- `/teilnahme/ergebnisse` — Ergebnisse (Gesamt / Altersklasse / AK & Geschlecht)
- `/manage?token=` — Selbstverwaltung; Startnummer-PDF; **Urkunde** (bei Zeit);
  **`<SponsorBar />` oben und unten.**
- `/` → `/teilnahme`

### Staff-Bereich (Login/Rollen bzw. Geräte-Token)
- `/team` — Admin: Suche (Name/Startnummer) + Voll-Bearbeitung
- `/team/special` — operativ: Anmeldungsliste, „Laufzeiten berechnen",
  Erfassungen je Startnummer (korrigieren/löschen/**manuell hinzufügen**), interne
  Vollwertung, Geräte-Tokens (Code + QR **dauerhaft** sichtbar), Mail-Test/Live
- `/team/veryspecial` — Events anlegen/löschen; Event-Einstellungen (T-Shirt,
  Jugend-Stichtag, **Urkunden-Hintergrund + Druckversatz**); Strecken &
  Startzeiten/Preise **+ AK-Schema + Geschlechtswertung**
- `/team/sepa` — SEPA-Export
- `/team/ergebnisdruck` — Lauf wählen → Wertungsgruppen mit Sammel-Download,
  „Alle Urkunden des Laufs", Einzeldruck per Startnummer, Checkbox „Hintergrund
  mitdrucken"
- `/team/sponsoren` — Anzeigemodus (Rotation/Laufband + Tempo), Klassen (Gewicht/
  Höhe), Upload (Klasse/Name/URL/Datei), Liste (Vorschau/Name/URL/Löschen)
- `/team/zeiterfassung` — Zeiterfassung (Kiosk)

Alte Pfade leiten weiter (`/results`, `/admin`, `/special-admin`, `/timing?…`).
Unten auf jeder Seite: Build-Zeile `Frontend <sha> · Backend <sha> · DB <rev>`.

### Zeiterfassungs-Seite (Kiosk)
Einrichtung per Geräte-Code (localStorage) oder QR-Scan
(`/team/zeiterfassung?token=&event=`). Erfassung über **grafisches Ziffernfeld**
(keine Handytastatur), Gerätezeit sofort festgehalten. **Persistente
localStorage-Queue** + Auto-Retry alle 4 s (überlebt Reload/Offline).

### Responsivität & i18n
Mobile-Media-Query (≤640 px) stapelt `.row`-Formularzeilen (Bearbeiten-Ansicht),
Tabellen scrollen horizontal, Buttons volle Breite. Eigener i18n-Provider
(de/en), `useI18n().t(key, vars)`; QR-Code **clientseitig** gerendert.

### Build-Kennung
Frontend: `VITE_BUILD` (Git-SHA) via Vite-`define` `__APP_BUILD__` (sonst
Zeitstempel). Backend: `BIBBY_BUILD` (Docker `--build-arg BUILD`).

---

## 10. Konfiguration (Env `BIBBY_*`, `backend/app/config.py`)

`database_url` (asyncpg) · `database_ssl` (Prod true) · `secret_key` (Token-HMAC)
· `public_base_url` · `build` · `field_encryption_key` (Fernet, IBAN) ·
`bib_start_number`=1 · `default_tshirt_options` · `min_lap_seconds`=60
(**vestigial** nach Runden-Entfernung) · SEPA `sepa_creditor_name/_id` · TEM
`tem_secret_key` (nur Secret Key!), `tem_project_id`, `scw_region`,
`tem_from_email`, `tem_from_name` · `mail_test_mode`=true, `mail_test_recipient`
(Laufzeit-Override via app_setting) · `cors_origins`.
Terraform-Variablen zusätzlich: `min_scale` (Container-Warmhaltung), `min_lap_seconds`.

---

## 11. Lokale Entwicklung & Deployment

**Lokal:** docker-compose (postgres:16 + API). Seed (`python -m app.seed`,
nur lokal) legt Demo-Daten an (Admin `admin@example.com`/`admin`). Frontend
`npm run dev`. **Lasttest:** `python -m app.loadtest seed [N] [JAHR]` / `clear`
(aus `backend/`, gleiche Env wie Alembic) — Testdaten `@loadtest.de`,
Startnummern ab 90001, `clear` matcht `%@loadtest.%`.

**Prod (Scaleway, live):** SPA-Bucket `bibby-spa-runbibby` hinter Edge Services
(`https://anmeldung.run-bibby.de`), Serverless Container (`min_scale=0` → Kaltstart
~9 s beim ersten Zugriff, per tfvars `min_scale=1` warmhaltbar), Serverless SQL,
TEM. **Deploy-Skript** `./deploy.sh [all|backend|frontend]` im Repo-Root: baut
das Image (`--no-cache --pull --platform linux/amd64`, `--build-arg BUILD=<sha>`),
pusht, **`scw container container redeploy`** (Terraform rollt bei gleichem
`:latest`-Tag NICHT neu aus!), baut/synct das SPA. **Migrationen laufen MANUELL**
(lokales venv gegen Prod-DB, `alembic upgrade head`) — NICHT beim Container-Start,
NICHT im Seed. Reihenfolge: **Migration zuerst, dann deploy.sh** (neues Modell
referenziert neue Spalten → sonst 500 auf `/events`).

**Prod-Fallen (siehe memory):** Scaleway-Project-ID (`d7cd73e2…`) ≠ Principal-UUID
(`d0e6b670…`, DB-User & DKIM-Selector); `unset TF_VAR_project_id` vor `tofu apply`;
`EmailStr` lehnt `.invalid`-Adressen ab (deshalb ist `AdminRegistrationDetail.email`
ein `str`, kein `EmailStr`).

---

## 12. Bekannte offene Punkte / Nicht-Ziele

- **Offen (Stand 2026-07-14):** Prod-Migrationen 0011–0015 noch NICHT eingespielt
  und der letzte Deploy steht aus (erst `alembic upgrade head`, dann `./deploy.sh`).
- `mail_test_mode` steht auf true — für echte Teilnehmer-Mails auf false.
- pain.008-SEPA-XML (nur CSV vorhanden); Betrags-Neuberechnung bei Admin-Änderung
  (Snapshot); dedizierter least-privilege DB-Key; Benutzerverwaltung im UI
  (weitere Organisatoren) — aktuell nur via `python -m app.create_admin`.
- CV-App (Bilderkennung bib/Zeit) = separates Projekt, nutzt denselben
  Ingestion-Endpunkt mit Geräte-Token.
- `category`-Tabelle, `competition.lap_count`, `timing_record.lap_index` und
  `min_lap_seconds` sind **vestigial** (aus dem entfernten Rundenkonzept) und
  könnten später bereinigt werden.
