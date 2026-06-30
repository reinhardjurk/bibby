# Bibby

Anmelde-, Zeiterfassungs- und Ergebnissystem für ein **Rundenrennen**
(Läufer melden sich für 1, 2 oder 3 Runden an). Serverless auf Scaleway,
Python/FastAPI, React-SPA.

```
backend/    FastAPI-API (async SQLAlchemy), Alembic, Seed, Dockerfile
frontend/   React + Vite + TypeScript SPA (mehrsprachig de/en)
db/         schema.sql (Referenz-DDL)
infra/      Terraform für Scaleway
```

## Lokal komplett starten

Voraussetzung: **Docker** (für API + DB) und **Node** (für die SPA).

### 1. API + Datenbank + Demo-Daten

```bash
docker compose up --build
```

Das fährt PostgreSQL hoch, wendet die Alembic-Migration an, spielt
Demo-Daten ein (Events 2025/2026, fünf Läufer mit Zeiten) und startet die API
auf **http://localhost:8000** (Doku: `/docs`).

### 2. Frontend

```bash
cd frontend
npm install        # einmalig
npm run dev        # http://localhost:5173
```

Die SPA zeigt jetzt:
- **Anmeldung**: Event „Bibby Lauf (2026)" mit den drei Strecken im Dropdown
- **Ergebnisse**: Event 2026 → „Mittel (2 Runden)" wählen → Anna, Björn, Carla
  mit Zeiten; Anna trägt das Badge **„2. Teilnahme"**

### Zurücksetzen

```bash
docker compose down -v   # löscht das DB-Volume; nächster Start seedet neu
```

## Demo-Daten im Überblick

| Startnr. | Läufer | Strecke | Ergebnis |
|---|---|---|---|
| 101 | Anna Berg | 2 Runden | Finisher (2. Teilnahme) |
| 102 | Björn Carlsson | 2 Runden | Finisher |
| 103 | Carla Diaz | 2 Runden | Finisher |
| 201 | Dieter Egger | 3 Runden | Finisher |
| 301 | Eva Fischer | 1 Runde | Finisher |

## Migrationen

```bash
# im laufenden api-Container oder lokal mit gesetzter BIBBY_DATABASE_URL
alembic revision --autogenerate -m "beschreibung"
alembic upgrade head
```

Die Baseline (`0001_initial`) erzeugt alle Tabellen aus den Modellen; spätere
Änderungen an `app/models.py` per Autogenerate.

Details je Komponente in `backend/README.md`, `frontend/README.md`,
`infra/README.md`.
