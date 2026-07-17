"""Lasttest-Daten: viele zufällige Anmeldungen quer über alle Strecken,
Altersklassen und Geschlechter – plus sauberes, automatisiertes Löschen.

    python -m app.loadtest seed [ANZAHL] [JAHR]   # Default 500, neuestes Event
    python -m app.loadtest clear                   # löscht ALLE Lasttest-Daten

Erzeugt werden auch die Daten, die die Wertung und den Statistik-Tab füttern:
- **Teams**: gezielt Dreier-Gruppen (werden zu Staffeln, sofern die Strecke
  Staffellogik hat) sowie Vereine/Paare/Vierer, die bewusst KEINE Staffel
  ergeben – damit ist die Abgrenzung mitgetestet.
- **Postleitzahlen**: überwiegend aus der Region des Events, der Rest streut
  bundesweit; ein Teil bleibt bewusst leer (die Angabe ist freiwillig).
- **"Wie erfahren?"** und **T-Shirt-Größe**, ebenfalls nicht flächendeckend.

Zielzeiten entstehen erst durch "Alle Laufzeiten berechnen" (Special-Admin);
dabei werden auch die Staffeln gebildet.

Lasttest-Anmeldungen sind eindeutig an der E-Mail-Domain @loadtest.de und an
Startnummern ab 90001 erkennbar. `clear` löscht ausschließlich diese (inkl.
Alt-Daten mit @loadtest.invalid) – echte Anmeldungen bleiben unberührt.

Aufruf wie bei Alembic: aus backend/ mit gesetzter BIBBY_DATABASE_URL
(+ BIBBY_DATABASE_SSL=true, BIBBY_SECRET_KEY=x) gegen die Ziel-DB.
"""

from __future__ import annotations

import asyncio
import random
import sys
from datetime import date, timedelta

from sqlalchemy import delete, func, select

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
MARKER = "@loadtest.de"
# clear erkennt Alt- ('@loadtest.invalid') und Neu-Daten ('@loadtest.de').
CLEAR_LIKE = "%@loadtest.%"
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


async def clear() -> None:
    async with SessionLocal() as s:
        rows = (
            await s.execute(
                select(Registration.id, Registration.participant_id).where(
                    Registration.email.like(CLEAR_LIKE)
                )
            )
        ).all()
        if not rows:
            print("loadtest: nichts zu löschen.")
            return
        reg_ids = [r.id for r in rows]
        part_ids = list({r.participant_id for r in rows})

        # Zeiterfassungen sind nicht per FK an die Anmeldung gebunden -> über die
        # Startnummern der Lasttest-Anmeldungen gezielt entfernen.
        bibs = (
            await s.execute(
                select(BibAssignment.event_id, BibAssignment.bib_number).where(
                    BibAssignment.registration_id.in_(reg_ids)
                )
            )
        ).all()
        for ev, b in bibs:
            await s.execute(
                delete(TimingRecord).where(
                    TimingRecord.event_id == ev, TimingRecord.bib_number == b
                )
            )

        # Anmeldung löschen -> Payment + BibAssignment kaskadieren (ON DELETE CASCADE).
        await s.execute(delete(Registration).where(Registration.id.in_(reg_ids)))
        await s.execute(delete(Participant).where(Participant.id.in_(part_ids)))
        await s.commit()
        print(
            f"loadtest: {len(reg_ids)} Anmeldungen, {len(part_ids)} Teilnehmer, "
            f"{len(bibs)} Zeiterfassungen gelöscht."
        )


if __name__ == "__main__":
    args = sys.argv[1:]
    cmd = args[0] if args else "seed"
    if cmd == "seed":
        count = int(args[1]) if len(args) > 1 else 500
        yr = int(args[2]) if len(args) > 2 else None
        asyncio.run(seed(count, yr))
    elif cmd == "clear":
        asyncio.run(clear())
    else:
        print("Aufruf: python -m app.loadtest [seed [ANZAHL] [JAHR] | clear]")
        raise SystemExit(2)
