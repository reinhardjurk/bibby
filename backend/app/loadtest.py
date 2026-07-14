"""Lasttest-Daten: viele zufällige Anmeldungen quer über alle Wettbewerbe,
Altersklassen und Geschlechter – plus sauberes, automatisiertes Löschen.

    python -m app.loadtest seed [ANZAHL] [JAHR]   # Default 500, neuestes Event
    python -m app.loadtest clear                   # löscht ALLE Lasttest-Daten

Lasttest-Anmeldungen sind eindeutig an der E-Mail-Domain @loadtest.invalid und
an Startnummern ab 90001 erkennbar. `clear` löscht ausschließlich diese – echte
Anmeldungen bleiben unberührt.

Aufruf wie bei Alembic: aus backend/ mit gesetzter BIBBY_DATABASE_URL
(+ BIBBY_DATABASE_SSL=true, BIBBY_SECRET_KEY=x) gegen die Ziel-DB.
"""

from __future__ import annotations

import asyncio
import random
import sys
from datetime import date, timedelta

from sqlalchemy import delete, func, select

from . import services
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
from .security import generate_token, hash_token

MARKER = "@loadtest.invalid"
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

        with_time = 0
        for i in range(n):
            first = random.choice(FIRST)
            # Index im Nachnamen -> global eindeutiger match_key (kein Konflikt).
            last = f"{random.choice(LAST)}{i + 1}"
            gender = random.choices(["f", "m", "x"], weights=[45, 45, 10])[0]
            age = random.randint(6, 85)  # deckt alle Altersklassen ab
            birth = date(event.event_date.year - age, random.randint(1, 12), random.randint(1, 28))
            comp = random.choice(comps)

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
        print(
            f"loadtest: {n} Anmeldungen in Event {event.year} angelegt "
            f"({with_time} mit Zielzeit), Startnummern {BIB_BASE + 1}…{bib - 1}."
        )
        print("loadtest: Löschen mit  python -m app.loadtest clear")


async def clear() -> None:
    async with SessionLocal() as s:
        rows = (
            await s.execute(
                select(Registration.id, Registration.participant_id).where(
                    Registration.email.like(f"%{MARKER}")
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
