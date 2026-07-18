# Tests

Shell-Testfälle gegen eine **laufende** Bibby-API. Jedes Skript prüft einen
Aspekt und endet mit Exit-Code `0` (bestanden) bzw. `≠ 0` (fehlgeschlagen), lässt
sich also in CI oder einer Schleife verwenden.

## Voraussetzungen

Zugangsdaten kommen aus Umgebungsvariablen:

```bash
export BIBBY_ADMIN_EMAIL="admin@example.com"
export BIBBY_ADMIN_PASSWORD="…"
export BIBBY_API_BASE="http://localhost:8000"   # optional, das ist der Default
```

Die Lasttests rufen `python -m app.loadtest` auf. Standardmäßig aus `backend/`
mit installierten Abhängigkeiten. Läuft die API in Docker, stattdessen:

```bash
export BIBBY_LOADTEST_CMD="docker compose exec -T api python -m app.loadtest"
```

## Testfälle

| Skript | Prüft | Verändert Daten? |
|---|---|---|
| `smoke.sh` | Health, Version, öffentliche Events, Admin-Login | nein |
| `mail-mode.sh` | Mailversand-Schalter live/test/off | nein (stellt zurück) |
| `loadtest-timing.sh [ZEITNEHMER] [BATCH] [STARTNR]` | Ingestion-API + Idempotenz der Offline-Queue | ja, räumt selbst auf |
| `loadtest-register.sh [ANZAHL] [PARALLEL]` | Anmeldung + Startnummernvergabe unter Nebenläufigkeit | ja, räumt selbst auf |
| `loadtest-clear.sh` | entfernt alle Lasttest-Daten | ja (nur Lasttest-Daten) |
| `run-all.sh` | führt alle der Reihe nach aus | s. o. |

Einzeln ausführen:

```bash
bash tests/smoke.sh
bash tests/loadtest-timing.sh 4 25 300
bash tests/loadtest-register.sh 200 20
```

## Sicherheit

- `loadtest-register.sh` schaltet den Mailversand für die Dauer des Tests auf
  **off** (sonst löst jede Testanmeldung eine echte Bestätigungsmail aus) und
  stellt den vorherigen Modus danach wieder her.
- Alle Lasttest-Daten sind markiert (E-Mail `@loadtest.*`, Startnummern ab 90001,
  Geräte-Token-Label `loadtest-…`). Die Skripte räumen hinter sich auf; falls
  doch etwas übrig bleibt, entfernt `loadtest-clear.sh` es vollständig.
- Gegen **Production** erzeugen die Lasttests echte DB-Last und (beim
  Register-Test) echte Anmeldedatensätze. Nach dem Lauf aufräumen und für
  belastbare Durchsatzzahlen vorher `min_scale ≥ 1` setzen (sonst misst du den
  Kaltstart).
