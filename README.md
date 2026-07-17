# Bibby

Anmelde-, Zeiterfassungs- und Ergebnissystem für eine **jährliche
Laufveranstaltung** (Gröbenzeller Familienlauf). Läufer melden sich für eine von
mehreren **benannten Strecken** an (z. B. „3,3 km Running", „1 km Kinder"). Es
gibt **kein Rundenkonzept** — die Zielzeit ist der Mittelwert aller Ziel­erfassungen
einer Startnummer minus der Startzeit der Strecke.

Serverless auf Scaleway, Backend **Python/FastAPI**, Frontend **React-SPA**.
Live unter **https://anmeldung.run-bibby.de**.

```
backend/    FastAPI-API (async SQLAlchemy), Alembic-Migrationen, Seed, Dockerfile
frontend/   React + Vite + TypeScript SPA (mehrsprachig de/en)
db/         schema.sql (Referenz-DDL)
infra/      Terraform/OpenTofu für Scaleway
.github/    CI/CD-Workflows (Deploy + Terraform, manuell auslösbar)
```

## Dokumentation

| Datei | Inhalt |
|---|---|
| [`BENUTZERHANDBUCH.md`](BENUTZERHANDBUCH.md) | **Handbuch für das Team** (Empfang/Kassieren, Lauf-Admin, Sponsoren, SEPA) |
| [`SPEC.md`](SPEC.md) | Vollständige technische Spezifikation (Datenmodell, Logik, API) |
| [`CI-SETUP.md`](CI-SETUP.md) | Einrichtung von Deploy/Terraform über GitHub Actions (Secrets, Freigaben) |

## Kernkonzepte

- **Benannte Strecken statt Runden.** Zielzeit = Mittelwert aller nicht
  ignorierten Erfassungen − Startzeit der Strecke. Fehlt die Startzeit → **DNF**
  (häufigste Support-Ursache).
- **Wertung je Strecke konfigurierbar:** Altersklassen-Schema (5-Jahres /
  1-Jahres / keine) und Geschlechtswertung (ja/nein). Altersklassen werden
  berechnet, nicht gepflegt.
- **Zahlung ohne Online-PSP:** SEPA-Lastschrift (IBAN verschlüsselt, CSV-Export)
  oder Barzahlung bei Abholung.
- **PDFs:** Startnummer (A5 quer) und Urkunde (A4), beide mit optional
  hochladbarer Event-Hintergrundvorlage.
- **Sponsoren:** 5 gewichtete Klassen, Anzeige als Rotation oder Laufband.
- **Laufzeit-Konfiguration** ohne Redeploy (Mail Test/Live, Mailtexte,
  Sponsoren-Anzeige) über die `app_setting`-Tabelle.

## Lokal starten

Voraussetzung: **Docker** (API + DB) und **Node** (SPA).

### 1. API + Datenbank + Demo-Daten

```bash
docker compose up --build
```

Startet PostgreSQL, wendet die Alembic-Migrationen an, spielt Demo-Daten ein
(zwei Events, mehrere Strecken, ein paar Läufer mit Zeiten, Admin-Login
`admin@example.com` / `admin`) und startet die API auf
**http://localhost:8000** (interaktive Doku: `/docs`).

### 2. Frontend

```bash
cd frontend
npm install        # einmalig
npm run dev        # http://localhost:5173
```

- **Anmeldung**: `/teilnahme`
- **Ergebnisse**: `/teilnahme/ergebnisse`
- **Team-Bereich** (Login erforderlich): `/team`

### Zurücksetzen

```bash
docker compose down -v   # löscht das DB-Volume; nächster Start seedet neu
```

## Migrationen

Additive Migrationen in `backend/alembic/versions/` (`ADD COLUMN`/`CREATE TABLE
IF NOT EXISTS`, verträglich mit der `create_all`-Baseline `0001`).

```bash
# lokal oder gegen Prod mit gesetzter BIBBY_DATABASE_URL
alembic upgrade head
```

**Wichtig:** In Prod laufen Migrationen **nicht** automatisch beim
Container-Start. Reihenfolge beim Ausrollen: **erst Migration, dann Deploy** (das
neue Modell referenziert neue Spalten). Über die CI erledigt das der
`Deploy`-Workflow mit `migrate: true`.

## Deployment (browser-/teamfähig)

Deploy und Terraform laufen über **GitHub Actions** (manuell auslösbar, mit
Freigabe über die Environment `production`) — kein lokaler Rechner mit Secrets
nötig. Details in [`CI-SETUP.md`](CI-SETUP.md).

- **`Deploy`-Workflow**: Ziel `all | backend | frontend`, optional `migrate`.
  Baut das Image (`linux/amd64`), pusht in die Scaleway-Registry, rollt den
  Container neu aus (`scw container container redeploy` — Terraform rollt bei
  gleichem `:latest`-Tag **nicht** neu aus), baut/synct die SPA.
- **`Terraform`-Workflow**: `plan` / `apply` gegen den Scaleway-Remote-State.

Als lokaler Fallback existiert `./deploy.sh [all|backend|frontend]`.

## Lasttest

Zwei Klassen von Befehlen (`python -m app.loadtest <befehl>`):

**Direkt in die DB** — schneller Seeder für UI/Statistik (kein echter Lasttest,
braucht `BIBBY_DATABASE_URL` wie Alembic):

```bash
python -m app.loadtest seed [N] [JAHR]   # Testdaten (@loadtest.de, Startnr. ab 90001)
python -m app.loadtest clear             # entfernt ALLE Lasttest-Daten
```

`seed` erzeugt auch Teams (gezielt Dreier-Gruppen → Staffeln, plus Vereine/Paare,
die bewusst keine Staffel ergeben), gestreute Postleitzahlen und die freiwilligen
Angaben. Zeiten und Staffeln entstehen erst durch **„Alle Laufzeiten berechnen"**.

**Über die echte API** — laufen **ohne DB-Zugang**, also auch **gegen Production**
(brauchen nur einen Admin-Login):

```bash
python -m app.loadtest api-register URL EMAIL PASSWORT [N] [PARALLEL] [JAHR]
python -m app.loadtest api-timing   URL EMAIL PASSWORT [ZEITNEHMER] [BATCH] [STARTNR] [JAHR]
python -m app.loadtest api-clear    URL EMAIL PASSWORT
```

- `api-register` testet `POST /registrations` inkl. der **Startnummernvergabe
  unter Nebenläufigkeit** (keine doppelten/lückenhaften Nummern). Bricht ab,
  wenn der Mailversand nicht auf **„Aus"** steht — sonst erzeugt jede Anmeldung
  eine echte Bestätigungsmail.
- `api-timing` testet die **Ingestion-API** (mehrere Zeitnehmer + Offline-Queue);
  prüft Durchsatz, Latenz (p50/p95/max) und die Idempotenz der Wiederholung.
  Nutzt Startnummern ab 90001, berührt echte Anmeldungen nie.
- `api-clear` löscht alle Lasttest-Daten (auch der API-Läufe) über die Admin-API.

**Mailversand-Schalter** (Special-Admin → E-Mail-Versand): **Live** / **Test**
(Umleitung an die Testadresse) / **Aus** (gar kein Versand). Für den Anmelde-
Lasttest auf **Aus** stellen und danach zurück auf **Test**.

Details je Komponente in `backend/README.md`, `frontend/README.md`,
`infra/README.md`.
