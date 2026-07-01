# Bibby — Backend

FastAPI-API für Anmeldung, Selbstverwaltung, Zeiterfassung und Ergebnislisten
eines Rundenrennens. Deployment als **Scaleway Serverless Container**.

## Lokal starten

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# DB-Schema einspielen (PostgreSQL)
psql "$DATABASE_URL" -f ../db/schema.sql

export BIBBY_DATABASE_URL="postgresql+asyncpg://localhost/bibby"
export BIBBY_SECRET_KEY="dev-secret"
uvicorn app.main:app --reload
```

OpenAPI-Doku: http://localhost:8000/docs

## Struktur

| Datei | Inhalt |
|---|---|
| `app/config.py` | Settings (Env `BIBBY_*`), Secrets via Scaleway Secret Manager |
| `app/models.py` | SQLAlchemy-2.0-Modelle (Spiegel von `db/schema.sql`) |
| `app/schemas.py` | Pydantic-Request/Response (API-Contract) |
| `app/security.py` | Token-Hashing, Geräte-Token-Auth, RBAC (`require_roles`) |
| `app/services.py` | Matching, **Rundenableitung**, Ergebnisberechnung |
| `app/mailer.py` | E-Mail-Versand (Scaleway TEM) mit Test-Modus |
| `app/routers/` | `events`, `registrations`, `manage`, `timing`, `results`, `admin` |

## API-Übersicht

Lebende Referenz: **`/docs`** (Swagger) bzw. `/openapi.json`. Kurzüberblick:

**Öffentlich** (keine Auth)

| Methode & Pfad | Zweck |
|---|---|
| `GET /health` | Health-Check |
| `GET /events` | Events (inkl. T-Shirt-Optionen) |
| `GET /events/{id}/competitions` | Strecken (inkl. Startzeit) |
| `GET /teams` | vergebene Teamnamen (Autocomplete) |
| `POST /registrations` | Anmeldung anlegen (vergibt Startnummer) |
| `GET /events/{id}/results?competition_id=` | öffentliche Ergebnisliste |

**Selbstverwaltung** (Magic-Link-Token in der Query)

| Methode & Pfad | Zweck |
|---|---|
| `GET /manage?token=` | Anmeldung ansehen |
| `PATCH /manage?token=` | Anmeldung ändern (E-Mail, Strecke, Team, T-Shirt) |
| `GET /manage/bib.pdf?token=` | Startnummer als PDF |

**Zeiterfassung**

| Methode & Pfad | Auth | Zweck |
|---|---|---|
| `POST /events/{id}/timings` | Geräte-Token (Bearer) | Erfassungen (Batch, idempotent) – CV-App + Web |
| `GET /events/{id}/timings/{bib}` | Session (timing/race_office/viewer) | Erfassungen einer Startnummer |
| `PATCH /timings/{id}` | Session (timing) | Korrektur (Zeit/Status/Nummer) |
| `DELETE /timings/{id}` | Session (timing) | Erfassung löschen |

**Admin** (`/admin`, Bearer Session-Token, RBAC – `admin` impliziert alles)

| Methode & Pfad | Rolle | Zweck |
|---|---|---|
| `POST /admin/auth/login` | – | Passwort-Login → Session-Token |
| `GET /admin/me` | eingeloggt | eigene Rollen |
| `GET /admin/registrations?event_id=&q=&limit=&offset=` | eingeloggt | paginierte Liste / Suche |
| `GET /admin/registrations/{id}` | eingeloggt | Detail |
| `PATCH /admin/registrations/{id}` | race_office | Voll-Bearbeitung (alle Felder) |
| `POST /admin/registrations/{id}/bib` | race_office | Startnummer setzen |
| `POST /admin/registrations/{id}/reassign` | race_office | Strecke umhängen |
| `POST /admin/registrations/{id}/payment/mark-paid` | race_office | als bezahlt markieren |
| `POST /admin/events/{id}/sepa-export` | race_office | CSV der offenen SEPA-Lastschriften (Name, IBAN, Betrag); markiert als exportiert |
| `POST /admin/participants/merge` | race_office | Teilnehmer zusammenführen |
| `PATCH /admin/competitions/{id}` | race_office | Startzeit / Preise (Erw./Jugend) |
| `PATCH /admin/events/{id}` | race_office | Event-Einstellungen (T-Shirt, Jugend-Stichtag) |
| `POST /admin/events/{id}/recompute-times` | race_office | alle Laufzeiten berechnen |
| `GET /admin/events/{id}/results?competition_id=` | eingeloggt | interne Vollwertung (inkl. nicht-öffentliche) |
| `GET/POST /admin/events/{id}/device-tokens` | timing | Geräte-Tokens auflisten / anlegen |
| `DELETE /admin/device-tokens/{id}` | timing | Geräte-Token sperren |

## Zahlung

Kein Online-PSP. Bei der Anmeldung wählt man:
- **SEPA-Lastschrift**: IBAN + Kontoinhaber + Mandatserteilung. Die IBAN wird
  app-seitig verschlüsselt gespeichert (`crypto.py`, Fernet), nur maskiert
  angezeigt. Es wird eine Mandatsreferenz erzeugt.
- **Barzahlung bei Abholung** der Startnummer.

Der eigentliche Lastschrifteinzug läuft offline (Banking/SEPA-XML). Das
Race-Office markiert Zahlungen über `POST /admin/registrations/{id}/payment/mark-paid`
als bezahlt.

## E-Mail (Scaleway TEM)

Versand über `app/mailer.py` (`send_email`). Konfiguration per Env:

| Variable | Zweck |
|---|---|
| `BIBBY_TEM_SECRET_KEY` | Secret Key des Scaleway-API-Keys mit TEM-Rechten (X-Auth-Token; leer = nur loggen). Access Key ID wird nicht benötigt. |
| `BIBBY_TEM_PROJECT_ID` | Scaleway Project ID |
| `BIBBY_SCW_REGION` | Region (z. B. `fr-par`) |
| `BIBBY_TEM_FROM_EMAIL` | Absender – Domäne muss in TEM verifiziert sein |
| `BIBBY_TEM_FROM_NAME` | Anzeigename des Absenders |
| `BIBBY_MAIL_TEST_MODE` | `true` = ALLE Mails an `BIBBY_MAIL_TEST_RECIPIENT` |
| `BIBBY_MAIL_TEST_RECIPIENT` | Empfänger im Test-Modus |

- **Test-Modus** (Standard `true`): jede Mail geht an die feste Test-Adresse;
  der eigentliche Empfänger steht im Betreff (`[TEST → …]`). Vor dem Echtbetrieb
  auf `false` setzen.
- Ohne `TEM_SECRET_KEY` wird die Mail nur geloggt (lokale Entwicklung).
- Mailfehler lassen die Anmeldung nicht scheitern (werden nur geloggt).

## Noch offen (Stubs / nächste Schritte)

- **SEPA-XML-Export** (pain.008) der offenen Lastschriften fürs Banking.
- **Async-Entkopplung**: Mail/PDF über Scaleway Queue + Functions.
- **Login-Härtung**: getrennter Einmal-Token, der gegen eine Session getauscht wird.

## Contract für die CV-App (separates Projekt)

Die Bilderkennungs-App postet erkannte Paare an denselben Endpunkt wie die
Web-Maske:

```
POST /events/{event_id}/timings
Authorization: Bearer <device-token>
{ "pings": [ { "bib_number": 123, "absolute_time": "2026-09-12T09:31:04Z",
              "dedup_key": "cam1-000457" } ] }
```

`dedup_key` macht das Senden idempotent (Offline-Puffer). `absolute_time` ist
die **Gerätezeit** (bzw. Frame-Zeit bei Video-Nachauswertung); der pro Token
hinterlegte `time_offset_seconds` korrigiert Drift serverseitig.
