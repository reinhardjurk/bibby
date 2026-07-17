"""Lasttest-Werkzeuge für Bibby.

Zwei Klassen von Befehlen:

**Direkt in die DB** (schnell, aber KEIN echter Lasttest – Seeder für UI/Statistik):
    python -m app.loadtest seed [ANZAHL] [JAHR]
    python -m app.loadtest clear
Braucht die BIBBY_DATABASE_URL (wie Alembic).

**Über die echte API** (laufen ohne DB-Zugang, daher auch gegen Production):
    python -m app.loadtest api-register URL EMAIL PASSWORT [ANZAHL] [PARALLEL] [JAHR]
    python -m app.loadtest api-timing   URL EMAIL PASSWORT [ZEITNEHMER] [BATCH] [STARTNUMMERN] [JAHR]
    python -m app.loadtest api-clear    URL EMAIL PASSWORT
EMAIL/PASSWORT sind ein Admin-Login. Beispiel gegen Prod:
    python -m app.loadtest api-timing https://bibby...scw.cloud admin@x.de geheim 4 25 300

- `api-register` testet POST /registrations inkl. der Startnummernvergabe unter
  Nebenläufigkeit (keine doppelten Nummern). VERLANGT Mailversand='off' (sonst
  Abbruch), damit keine echten Bestätigungsmails entstehen.
- `api-timing` testet die Ingestion-API (mehrere Zeitnehmer + Offline-Queue).
  Nutzt Startnummern ab 90001, berührt also nie echte Anmeldungen.
- `api-clear` löscht ALLE Lasttest-Daten (Anmeldungen @loadtest.*, deren
  Erfassungen, API-Lasttest-Erfassungen und -Geräte-Tokens). Echte Daten bleiben.

Alle Lasttest-Daten sind markiert (E-Mail @loadtest.de, Startnummern ab 90001,
Geräte-Token-Label 'loadtest-...') und dadurch sauber und vollständig löschbar.
"""

from __future__ import annotations

import asyncio
import random
import sys
import time
import uuid as uuidlib
from datetime import date, datetime, timedelta, timezone

import httpx
from sqlalchemy import func, select

from . import geo, services
from .config import settings
from .db import SessionLocal
from .models import (
    BibAssignment,
    Competition,
    Event,
    Participant,
    Payment,
    Registration,
    TimingRecord,
)
from .schemas import HEARD_ABOUT_OPTIONS
from .security import generate_token, hash_token

# Erkennbare, aber gültige Domain (EmailStr akzeptiert keine .invalid-TLD).
# Das eigentliche Löschkriterium lebt in services.purge_loadtest_data.
MARKER = "@loadtest.de"
BIB_BASE = 90000

FIRST = [
    "Anna", "Ben", "Carla", "David", "Eva", "Finn", "Greta", "Hans", "Ida", "Jan",
    "Klara", "Lars", "Mia", "Nils", "Olga", "Paul", "Rosa", "Sven", "Tina", "Uwe",
    "Vera", "Willi", "Xenia", "Yannick", "Zoe", "Björn", "Sara", "Tom", "Lena", "Max",
]
LAST = [
    "Berg", "Carlsson", "Diaz", "Egger", "Fischer", "Gruber", "Huber", "Ivanov",
    "Jung", "Klein", "Lang", "Meyer", "Nowak", "Ott", "Peters", "Richter", "Schmidt",
    "Thomas", "Ulrich", "Voss", "Weber", "Yilmaz", "Zimmer",
]
TEAM_WORDS = [
    "Blitz", "Turbo", "Wiesel", "Gepard", "Komet", "Rakete", "Donner", "Sturm",
    "Falke", "Adler", "Panther", "Kobra", "Tiger", "Delfin", "Otter",
]
CLUB_NAMES = [
    "LG Nord", "TSV Süd", "Laufgruppe Ost", "SV West", "Team Kondition",
]
# Anteil der Anmeldungen, die die freiwilligen Angaben ausfüllen.
P_POSTAL = 0.8
P_HEARD = 0.7
# Anteil der PLZ aus der Region des Veranstaltungsorts (Rest streut bundesweit).
P_LOCAL = 0.7


def _random_plz(local_region: str | None) -> str:
    """Zufällige PLZ; überwiegend aus der Region des Events. Nur die ersten zwei
    Ziffern sind für die Auswertung relevant (s. geo.py), der Rest ist Füllung."""
    if local_region and random.random() < P_LOCAL:
        region = local_region
    else:
        region = random.choice(geo.region_codes())
    return f"{region}{random.randint(0, 999):03d}"


def _plan_teams(n: int, comps: list[Competition]) -> list[tuple[Competition, str | None]]:
    """Verteilt n Anmeldungen auf (Strecke, Teamname) und erzeugt dabei gezielt:

    - **Staffeln**: genau 3 gleiche Teamnamen in DERSELBEN Strecke (bevorzugt auf
      Strecken mit Staffellogik) -> werden zu Staffeln.
    - **Vereine** (5–12 Mitglieder), **Paare** (2) und ein **Vierer**: gleicher
      Teamname, aber NICHT genau 3 -> bewusst KEINE Staffel (testet die Abgrenzung).
    - Rest ohne Team.
    """
    relay_comps = [c for c in comps if c.relay_scoring] or comps
    plan: list[tuple[Competition, str | None]] = []

    # Staffeln: ~ jede 25. Anmeldung startet eine Dreier-Staffel.
    for i in range(max(1, n // 25)):
        if len(plan) + 3 > n:
            break
        comp = random.choice(relay_comps)
        plan.extend([(comp, f"{random.choice(TEAM_WORDS)} {i + 1}")] * 3)

    # Vereine: viele Mitglieder in EINER Strecke -> nie genau 3.
    for idx, club in enumerate(CLUB_NAMES):
        size = random.randint(5, 12)
        if len(plan) + size > n:
            break
        comp = random.choice(comps)
        plan.extend([(comp, club)] * size)

    # Zwei Paare und ein Vierer -> ebenfalls keine Staffel.
    for size, label in ((2, "Duo A"), (2, "Duo B"), (4, "Quartett")):
        if len(plan) + size > n:
            break
        comp = random.choice(comps)
        plan.extend([(comp, label)] * size)

    # Rest: ohne Team.
    while len(plan) < n:
        plan.append((random.choice(comps), None))

    plan = plan[:n]
    random.shuffle(plan)
    return plan


async def seed(n: int, year: int | None) -> None:
    async with SessionLocal() as s:
        if year is not None:
            event = (
                await s.execute(select(Event).where(Event.year == year))
            ).scalar_one_or_none()
        else:
            event = (
                await s.execute(select(Event).order_by(Event.year.desc()))
            ).scalars().first()
        if event is None:
            print("loadtest: kein Event gefunden.")
            return

        comps = (
            await s.execute(select(Competition).where(Competition.event_id == event.id))
        ).scalars().all()
        if not comps:
            print(f"loadtest: Event {event.year} hat keine Wettbewerbe.")
            return

        cur_max = (
            await s.execute(
                select(func.max(BibAssignment.bib_number)).where(
                    BibAssignment.event_id == event.id
                )
            )
        ).scalar() or 0
        bib = max(cur_max + 1, BIB_BASE + 1)

        plan = _plan_teams(n, list(comps))
        local_region = geo.region_of(event.postal_code)
        shirts = event.tshirt_options or settings.default_tshirt_options

        with_time = 0
        for i in range(n):
            comp, team = plan[i]
            first = random.choice(FIRST)
            # Index im Nachnamen -> global eindeutiger match_key (kein Konflikt).
            last = f"{random.choice(LAST)}{i + 1}"
            gender = random.choices(["f", "m", "x"], weights=[45, 45, 10])[0]
            age = random.randint(6, 85)  # deckt alle Altersklassen ab
            birth = date(event.event_date.year - age, random.randint(1, 12), random.randint(1, 28))

            part = Participant(
                match_key=services.build_match_key(last, first, birth),
                first_name=first,
                last_name=last,
                birth_date=birth,
                gender=gender,
            )
            s.add(part)
            await s.flush()

            reg = Registration(
                event_id=event.id,
                competition_id=comp.id,
                participant_id=part.id,
                email=f"lt{i + 1}{MARKER}",
                language="de",
                team=team,
                tshirt=random.choice(shirts) if shirts else None,
                # Freiwillige Angaben: bewusst nicht bei allen gesetzt, damit die
                # Statistik auch den Fall "ohne Angabe" abdeckt.
                postal_code=_random_plz(local_region) if random.random() < P_POSTAL else None,
                heard_about=(
                    random.choice(HEARD_ABOUT_OPTIONS) if random.random() < P_HEARD else None
                ),
                status="confirmed",
                manage_token_hash=hash_token(generate_token()),
                consent_data=True,
                consent_publish=True,
            )
            s.add(reg)
            await s.flush()

            s.add(
                Payment(
                    registration_id=reg.id,
                    method="on_site",
                    amount_cents=services.compute_price_cents(event, comp, birth),
                    currency=comp.currency,
                    status="paid",
                )
            )
            s.add(BibAssignment(event_id=event.id, bib_number=bib, registration_id=reg.id))

            # Zielzeit nur, wenn die Strecke eine Startzeit hat (sonst DNF).
            start = comp.start_time or event.default_start_time
            if start is not None:
                finish = start + timedelta(seconds=random.randint(600, 5400))  # 10–90 min
                s.add(
                    TimingRecord(
                        event_id=event.id,
                        bib_number=bib,
                        absolute_time=finish,
                        dedup_key=f"lt-{event.id}-{bib}",
                        status="valid",
                    )
                )
                with_time += 1

            bib += 1
            if (i + 1) % 100 == 0:
                await s.flush()
                print(f"loadtest: {i + 1}/{n} …")

        await s.commit()

        # Wie viele Dreier-Gruppen je Strecke -> so viele Staffeln entstehen beim
        # Berechnen (nur auf Strecken mit Staffellogik).
        groups: dict[tuple, int] = {}
        for comp, team in plan:
            if team:
                groups[(comp.id, team)] = groups.get((comp.id, team), 0) + 1
        relays = sum(
            1
            for (comp_id, _t), size in groups.items()
            if size == 3 and next(c for c in comps if c.id == comp_id).relay_scoring
        )
        print(
            f"loadtest: {n} Anmeldungen in Event {event.year} angelegt "
            f"({with_time} mit Zielzeit), Startnummern {BIB_BASE + 1}…{bib - 1}."
        )
        print(
            f"loadtest: {len(groups)} Teams, davon {relays} als Staffel wertbar "
            "(genau 3 gleiche Teamnamen auf einer Strecke mit Staffellogik)."
        )
        if not any(c.relay_scoring for c in comps):
            print(
                "loadtest: HINWEIS – keine Strecke hat 'mit Staffellogik'; "
                "es entstehen daher keine Staffeln."
            )
        if not event.postal_code:
            print(
                "loadtest: HINWEIS – Event hat keine PLZ; die Anreise-Statistik "
                "bleibt leer (Events -> Event-Einstellungen)."
            )
        print("loadtest: jetzt im Special-Admin 'Alle Laufzeiten berechnen' ausführen")
        print("loadtest: Löschen mit  python -m app.loadtest clear")


# =========================================================================
# Lasttests über die ECHTE API — laufen ohne DB-Zugang, auch gegen Production
# =========================================================================
def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _pct(values: list[float], p: float) -> float:
    """p-tes Perzentil (0..100) einer Latenzliste."""
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[max(0, min(len(ordered) - 1, round(p / 100 * (len(ordered) - 1))))]


def _report(label: str, latencies: list[float], errors: list[str], units: int, secs: float) -> None:
    print(f"  {label}: {units} in {len(latencies)} Requests, {secs:.1f}s -> {units / secs:.0f}/s")
    if latencies:
        print(
            f"    Latenz  p50={_pct(latencies, 50) * 1000:.0f}ms  "
            f"p95={_pct(latencies, 95) * 1000:.0f}ms  max={max(latencies) * 1000:.0f}ms"
        )
    print(f"    Fehler: {len(errors)}")
    for e in errors[:3]:
        print(f"    ! {e}")


async def _login(client: httpx.AsyncClient, base: str, email: str, password: str) -> str | None:
    r = await client.post(f"{base}/admin/auth/login", json={"email": email, "password": password})
    if r.status_code != 200:
        print(f"loadtest: Login fehlgeschlagen ({r.status_code}): {r.text[:120]}")
        return None
    return r.json()["token"]


async def _newest_event(client: httpx.AsyncClient, base: str, year: int | None) -> dict | None:
    r = await client.get(f"{base}/events")
    r.raise_for_status()
    events = r.json()
    if year is not None:
        events = [e for e in events if e["year"] == year]
    if not events:
        print("loadtest: kein passendes Event gefunden.")
        return None
    return events[0]


async def _require_mail_off(client: httpx.AsyncClient, base: str, token: str) -> bool:
    """Lasttest-Anmeldungen lösen echte Bestätigungsmails aus. Im Modus 'test'
    gehen sie gesammelt an die Testadresse – auch das will niemand hundertfach.
    Daher wird nur bei 'off' gestartet."""
    r = await client.get(f"{base}/admin/mail-settings", headers=_auth(token))
    r.raise_for_status()
    mode = r.json()["mode"]
    if mode != "off":
        print(
            f"loadtest: ABBRUCH – Mailversand steht auf '{mode}'. Jede Testanmeldung\n"
            "          würde eine echte Mail erzeugen. Im Special-Admin unter\n"
            "          'E-Mail-Versand' auf 'Aus' schalten und danach zurückstellen."
        )
        return False
    return True


async def api_register(
    base: str, email: str, password: str, n: int, parallel: int, year: int | None
) -> None:
    """Lasttest der Anmeldung über die ECHTE API (POST /registrations).

    Prüft dabei die kritischste Stelle: die Startnummernvergabe unter
    Nebenläufigkeit (pg_advisory_xact_lock) – keine Nummer darf doppelt sein.
    """
    base = base.rstrip("/")
    async with httpx.AsyncClient(timeout=60) as client:
        token = await _login(client, base, email, password)
        if not token:
            return
        if not await _require_mail_off(client, base, token):
            return
        event = await _newest_event(client, base, year)
        if not event:
            return
        r = await client.get(f"{base}/events/{event['id']}/competitions")
        r.raise_for_status()
        comps = r.json()
        if not comps:
            print("loadtest: Event hat keine Strecken.")
            return

        print(f"loadtest: Anmeldung gegen {base}  (Event {event['name']} {event['year']})")
        print(f"loadtest: {n} Anmeldungen, {parallel} parallel")

        bibs: list[int] = []
        latencies: list[float] = []
        errors: list[str] = []
        sem = asyncio.Semaphore(parallel)
        run = uuidlib.uuid4().hex[:8]
        lock = asyncio.Lock()

        async def one(i: int) -> None:
            comp = random.choice(comps)
            age = random.randint(6, 85)
            body = {
                "event_id": event["id"],
                "competition_id": comp["id"],
                "first_name": random.choice(FIRST),
                # run-Präfix -> global eindeutige Person (kein Match auf Altdaten).
                "last_name": f"{random.choice(LAST)}{run}{i}",
                "birth_date": date(
                    date.fromisoformat(event["event_date"]).year - age,
                    random.randint(1, 12),
                    random.randint(1, 28),
                ).isoformat(),
                "gender": random.choices(["f", "m", "x"], weights=[45, 45, 10])[0],
                "email": f"lt-{run}-{i}{MARKER}",
                "consent_data": True,
                "consent_publish": True,
                "payment_method": "on_site",
            }
            async with sem:
                t0 = time.perf_counter()
                try:
                    resp = await client.post(f"{base}/registrations", json=body)
                    dt = time.perf_counter() - t0
                    async with lock:
                        latencies.append(dt)
                        if resp.status_code != 201:
                            errors.append(f"HTTP {resp.status_code}: {resp.text[:120]}")
                        else:
                            bib = resp.json().get("bib_number")
                            if bib is not None:
                                bibs.append(bib)
                except Exception as exc:  # noqa: BLE001 – im Lasttest zählt jeder Fehler
                    async with lock:
                        latencies.append(time.perf_counter() - t0)
                        errors.append(str(exc)[:120])

        t0 = time.perf_counter()
        await asyncio.gather(*(one(i) for i in range(n)))
        elapsed = time.perf_counter() - t0
        _report("Anmeldungen", latencies, errors, n, elapsed)

        print("\nloadtest: Prüfungen")
        ok = True

        def verify(label: str, cond: bool, detail: str) -> None:
            nonlocal ok
            print(("  OK   " if cond else "  FEHLER ") + f"{label}: {detail}")
            ok = ok and cond

        verify("alle Anmeldungen angenommen", len(bibs) == n, f"{len(bibs)}/{n}")
        dupes = len(bibs) - len(set(bibs))
        verify(
            "Startnummern eindeutig (Nebenläufigkeit)",
            dupes == 0,
            f"{len(set(bibs))} verschiedene, {dupes} doppelt",
        )
        if bibs:
            verify(
                "Startnummern lückenlos fortlaufend",
                max(bibs) - min(bibs) + 1 == len(bibs),
                f"{min(bibs)}…{max(bibs)}",
            )
        verify("keine Fehler", not errors, f"{len(errors)} Fehler")
        print(
            "\nloadtest: "
            + ("alles in Ordnung." if ok else "PROBLEME – siehe oben.")
            + "  Aufräumen:  python -m app.loadtest api-clear URL EMAIL PASSWORT"
        )


async def api_timing(
    base: str, email: str, password: str, senders: int, batch_size: int, bib_count: int,
    year: int | None,
) -> None:
    """Lasttest der Zeiterfassung über die ECHTE Ingestion-API.

    Simuliert `senders` Zeitnehmer, die ALLE dieselben Startnummern erfassen (so
    entsteht die Mittelung mehrerer Erfassungen), und sendet den Schwung danach
    ERNEUT – das ahmt die Offline-Queue nach und muss vollständig als Duplikat
    abgewiesen werden.

    Nutzt bewusst Startnummern ab 90001: Erfassungen hängen nicht an einer
    Anmeldung, echte Teilnehmer werden also garantiert nicht berührt.
    """
    base = base.rstrip("/")
    async with httpx.AsyncClient(timeout=60) as client:
        token = await _login(client, base, email, password)
        if not token:
            return
        event = await _newest_event(client, base, year)
        if not event:
            return
        event_id = event["id"]

        # Je simuliertem Zeitnehmer ein echtes Geräte-Token über die Admin-API.
        tokens: list[tuple[str, str]] = []  # (id, klartext)
        for i in range(senders):
            r = await client.post(
                f"{base}/admin/events/{event_id}/device-tokens",
                json={"label": f"{services.LOADTEST_TOKEN_LABEL}{i + 1}", "time_offset_seconds": 0},
                headers=_auth(token),
            )
            if r.status_code != 200:
                print(f"loadtest: Geräte-Token anlegen fehlgeschlagen: {r.status_code} {r.text[:120]}")
                return
            body = r.json()
            tokens.append((body["id"], body["token"]))

        bibs = [BIB_BASE + 1 + i for i in range(bib_count)]
        run = uuidlib.uuid4().hex[:8]
        start = datetime.now(timezone.utc)
        url = f"{base}/events/{event_id}/timings"

        def pings_for(sender: int) -> list[dict]:
            return [
                {
                    "bib_number": bib,
                    # leicht versetzt – wie mehrere Zeitnehmer an einer Ziellinie
                    "absolute_time": (
                        start + timedelta(seconds=random.randint(600, 5400) + random.uniform(-2, 2))
                    ).isoformat(),
                    "dedup_key": f"{services.LOADTEST_DEDUP_PREFIX}{run}-s{sender}-b{bib}",
                }
                for bib in bibs
            ]

        plans = {i: pings_for(i) for i in range(senders)}
        total = sum(len(p) for p in plans.values())
        print(f"loadtest: Zeiterfassung gegen {url}")
        print(f"loadtest: {senders} Zeitnehmer x {bib_count} Startnummern = {total} Pings, Batch {batch_size}")

        latencies: list[float] = []
        errors: list[str] = []
        accepted = duplicates = 0
        lock = asyncio.Lock()

        async def send_all(sender: int) -> None:
            nonlocal accepted, duplicates
            headers = _auth(tokens[sender][1])
            pings = plans[sender]
            for i in range(0, len(pings), batch_size):
                chunk = pings[i : i + batch_size]
                t0 = time.perf_counter()
                try:
                    r = await client.post(url, json={"pings": chunk}, headers=headers)
                    dt = time.perf_counter() - t0
                    async with lock:
                        latencies.append(dt)
                        if r.status_code != 200:
                            errors.append(f"HTTP {r.status_code}: {r.text[:120]}")
                        else:
                            accepted += r.json()["accepted"]
                            duplicates += r.json()["duplicates"]
                except Exception as exc:  # noqa: BLE001
                    async with lock:
                        latencies.append(time.perf_counter() - t0)
                        errors.append(str(exc)[:120])

        async def round_(label: str) -> tuple[int, int]:
            nonlocal accepted, duplicates
            accepted = duplicates = 0
            latencies.clear()
            errors.clear()
            t0 = time.perf_counter()
            await asyncio.gather(*(send_all(i) for i in range(senders)))
            _report(label, latencies, errors, total, time.perf_counter() - t0)
            print(f"    akzeptiert={accepted}  duplikate={duplicates}")
            return accepted, duplicates

        acc1, dup1 = await round_("Runde 1 (neu)")
        acc2, dup2 = await round_("Runde 2 (Wiederholung, Offline-Queue)")

        # Geräte-Tokens wieder entfernen.
        for tid, _raw in tokens:
            await client.delete(f"{base}/admin/device-tokens/{tid}", headers=_auth(token))

        print("\nloadtest: Prüfungen")
        ok = True

        def verify(label: str, cond: bool, detail: str) -> None:
            nonlocal ok
            print(("  OK   " if cond else "  FEHLER ") + f"{label}: {detail}")
            ok = ok and cond

        verify("Runde 1 vollständig angenommen", acc1 == total and dup1 == 0,
               f"akzeptiert={acc1}/{total}, duplikate={dup1}")
        verify("Wiederholung wird verworfen (Idempotenz)", acc2 == 0 and dup2 == total,
               f"akzeptiert={acc2}, duplikate={dup2}")
        verify("keine Fehler", not errors, f"{len(errors)} Fehler")
        print(
            "\nloadtest: "
            + ("alles in Ordnung." if ok else "PROBLEME – siehe oben.")
            + "  Aufräumen:  python -m app.loadtest api-clear URL EMAIL PASSWORT"
        )


async def api_clear(base: str, email: str, password: str) -> None:
    """Räumt die Lasttest-Daten über die Admin-API auf (ohne DB-Zugang)."""
    base = base.rstrip("/")
    async with httpx.AsyncClient(timeout=120) as client:
        token = await _login(client, base, email, password)
        if not token:
            return
        r = await client.post(f"{base}/admin/loadtest/clear", headers=_auth(token))
        if r.status_code != 200:
            print(f"loadtest: Aufräumen fehlgeschlagen ({r.status_code}): {r.text[:200]}")
            return
        c = r.json()
        print(
            f"loadtest: {c['registrations']} Anmeldungen, {c['participants']} Teilnehmer, "
            f"{c['timings']} Zeiterfassungen, {c['device_tokens']} Geräte-Tokens gelöscht."
        )


async def clear() -> None:
    """Direkt per DB aufräumen (Alternative zu api-clear, wenn man DB-Zugang hat).
    Nutzt exakt dieselbe Logik wie der Admin-Endpunkt."""
    async with SessionLocal() as s:
        c = await services.purge_loadtest_data(s)
        if not any(c.values()):
            print("loadtest: nichts zu löschen.")
            return
        print(
            f"loadtest: {c['registrations']} Anmeldungen, {c['participants']} Teilnehmer, "
            f"{c['timings']} Zeiterfassungen, {c['device_tokens']} Geräte-Tokens gelöscht."
        )


if __name__ == "__main__":
    args = sys.argv[1:]
    cmd = args[0] if args else "seed"
    if cmd == "seed":
        count = int(args[1]) if len(args) > 1 else 500
        yr = int(args[2]) if len(args) > 2 else None
        asyncio.run(seed(count, yr))
    elif cmd == "api-register":
        # api-register URL EMAIL PASSWORT [ANZAHL] [PARALLEL] [JAHR]
        if len(args) < 4:
            print("Aufruf: python -m app.loadtest <befehl>\n"
            "  seed [ANZAHL] [JAHR]                                  (DB)\n"
            "  api-register URL EMAIL PASSWORT [ANZAHL] [PARALLEL] [JAHR]\n"
            "  api-timing   URL EMAIL PASSWORT [ZEITNEHMER] [BATCH] [STARTNUMMERN] [JAHR]\n"
            "  api-clear    URL EMAIL PASSWORT\n"
            "  clear                                                 (DB)")
            raise SystemExit(2)
        asyncio.run(
            api_register(
                args[1], args[2], args[3],
                int(args[4]) if len(args) > 4 else 100,
                int(args[5]) if len(args) > 5 else 10,
                int(args[6]) if len(args) > 6 else None,
            )
        )
    elif cmd == "api-timing":
        # api-timing URL EMAIL PASSWORT [ZEITNEHMER] [BATCH] [STARTNUMMERN] [JAHR]
        if len(args) < 4:
            print("Aufruf: python -m app.loadtest <befehl>\n"
            "  seed [ANZAHL] [JAHR]                                  (DB)\n"
            "  api-register URL EMAIL PASSWORT [ANZAHL] [PARALLEL] [JAHR]\n"
            "  api-timing   URL EMAIL PASSWORT [ZEITNEHMER] [BATCH] [STARTNUMMERN] [JAHR]\n"
            "  api-clear    URL EMAIL PASSWORT\n"
            "  clear                                                 (DB)")
            raise SystemExit(2)
        asyncio.run(
            api_timing(
                args[1], args[2], args[3],
                int(args[4]) if len(args) > 4 else 3,
                int(args[5]) if len(args) > 5 else 20,
                int(args[6]) if len(args) > 6 else 200,
                int(args[7]) if len(args) > 7 else None,
            )
        )
    elif cmd == "api-clear":
        if len(args) < 4:
            print("Aufruf: python -m app.loadtest <befehl>\n"
            "  seed [ANZAHL] [JAHR]                                  (DB)\n"
            "  api-register URL EMAIL PASSWORT [ANZAHL] [PARALLEL] [JAHR]\n"
            "  api-timing   URL EMAIL PASSWORT [ZEITNEHMER] [BATCH] [STARTNUMMERN] [JAHR]\n"
            "  api-clear    URL EMAIL PASSWORT\n"
            "  clear                                                 (DB)")
            raise SystemExit(2)
        asyncio.run(api_clear(args[1], args[2], args[3]))
    elif cmd == "clear":
        asyncio.run(clear())
    else:
        print("Aufruf: python -m app.loadtest <befehl>\n"
            "  seed [ANZAHL] [JAHR]                                  (DB)\n"
            "  api-register URL EMAIL PASSWORT [ANZAHL] [PARALLEL] [JAHR]\n"
            "  api-timing   URL EMAIL PASSWORT [ZEITNEHMER] [BATCH] [STARTNUMMERN] [JAHR]\n"
            "  api-clear    URL EMAIL PASSWORT\n"
            "  clear                                                 (DB)")
        raise SystemExit(2)
