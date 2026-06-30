"""Demo-Daten für die lokale Entwicklung. Idempotent: läuft nur, wenn Event
2026 noch nicht existiert.

Aufruf: `python -m app.seed`
"""

from __future__ import annotations

import asyncio
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select

from . import services
from .config import settings
from .db import SessionLocal
from .models import (
    AppUser,
    BibAssignment,
    Category,
    Competition,
    Event,
    Payment,
    Registration,
    TimingRecord,
    UserRole,
)
from .security import generate_token, hash_token

START_2026 = datetime(2026, 9, 12, 9, 0, tzinfo=timezone.utc)


async def seed() -> None:
    async with SessionLocal() as s:
        if (
            await s.execute(select(Event).where(Event.year == 2026))
        ).scalar_one_or_none():
            print("seed: Event 2026 existiert bereits – übersprungen.")
            return

        # --- Events ---
        event2025 = Event(name="Bibby Lauf", year=2025, event_date=date(2025, 9, 13))
        event2026 = Event(
            name="Bibby Lauf",
            year=2026,
            event_date=date(2026, 9, 12),
            default_start_time=START_2026,
        )
        s.add_all([event2025, event2026])
        await s.flush()

        # --- Wettbewerbe (Rundenzahl) für 2026 ---
        comp1 = Competition(event_id=event2026.id, lap_count=1, start_time=START_2026,
                            price_cents=1500, title_i18n={"de": "Kurz (1 Runde)", "en": "Short (1 lap)"})
        comp2 = Competition(event_id=event2026.id, lap_count=2, start_time=START_2026,
                            price_cents=2000, title_i18n={"de": "Mittel (2 Runden)", "en": "Medium (2 laps)"})
        comp3 = Competition(event_id=event2026.id, lap_count=3, start_time=START_2026,
                            price_cents=2500, title_i18n={"de": "Lang (3 Runden)", "en": "Long (3 laps)"})
        # Vorjahres-Wettbewerb, damit ein Teilnehmer wiederkehrt.
        comp2025 = Competition(event_id=event2025.id, lap_count=2)
        s.add_all([comp1, comp2, comp3, comp2025])

        # --- Admin-Benutzer (für die Admin-Oberfläche) ---
        admin = AppUser(email="admin@example.com", name="Demo Admin")
        s.add(admin)
        await s.flush()
        s.add(UserRole(user_id=admin.id, role="admin"))

        # --- Altersklassen 2026 ---
        s.add_all([
            Category(event_id=event2026.id, code="AK-U40", min_age=0, max_age=39),
            Category(event_id=event2026.id, code="AK-40", min_age=40, max_age=200),
        ])
        await s.flush()

        # --- Teilnehmer ---
        async def participant(first, last, birth, gender):
            return await services.get_or_create_participant(
                s, first_name=first, last_name=last, birth_date=birth, gender=gender
            )

        anna = await participant("Anna", "Berg", date(1990, 4, 1), "f")
        bjorn = await participant("Björn", "Carlsson", date(1985, 7, 12), "m")
        carla = await participant("Carla", "Diaz", date(1992, 2, 20), "f")
        dieter = await participant("Dieter", "Egger", date(1979, 11, 3), "m")
        eva = await participant("Eva", "Fischer", date(2000, 6, 9), "f")

        manage_links: list[tuple[str, int, str]] = []

        async def register(event, competition, person, bib, *, status="confirmed"):
            raw_token = generate_token()
            reg = Registration(
                event_id=event.id,
                competition_id=competition.id,
                participant_id=person.id,
                email=f"{person.first_name.lower()}@example.com",
                language="de",
                status=status,
                manage_token_hash=hash_token(raw_token),
                consent_data=True,
                consent_publish=True,
            )
            s.add(reg)
            await s.flush()
            s.add(
                Payment(
                    registration_id=reg.id,
                    method="on_site",
                    amount_cents=competition.price_cents,
                    currency=competition.currency,
                    status="paid",
                )
            )
            if bib is not None:
                s.add(BibAssignment(event_id=event.id, bib_number=bib, registration_id=reg.id))
                manage_links.append((f"{person.first_name} {person.last_name}", bib, raw_token))
            return reg

        # 2026-Anmeldungen
        await register(event2026, comp2, anna, 101)
        await register(event2026, comp2, bjorn, 102)
        await register(event2026, comp2, carla, 103)
        await register(event2026, comp3, dieter, 201)
        await register(event2026, comp1, eva, 301)
        # Anna war schon 2025 dabei -> "2. Teilnahme"
        await register(event2025, comp2025, anna, 55)

        # --- Zeiterfassung 2026: Linienüberquerungen (mm:ss nach Start) ---
        def mins(m, sec=0):
            return START_2026 + timedelta(minutes=m, seconds=sec)

        crossings = {
            101: [mins(21, 30), mins(44, 10)],          # Anna, 2 Runden
            102: [mins(20, 5), mins(41, 50)],           # Björn, 2 Runden
            103: [mins(23, 0), mins(47, 30)],           # Carla, 2 Runden
            201: [mins(20, 0), mins(42, 0), mins(65, 0)],  # Dieter, 3 Runden
            301: [mins(22, 15)],                         # Eva, 1 Runde
        }
        for bib, times in crossings.items():
            for i, t in enumerate(times, start=1):
                s.add(
                    TimingRecord(
                        event_id=event2026.id,
                        bib_number=bib,
                        absolute_time=t,
                        dedup_key=f"seed-{bib}-{i}",
                        status="valid",
                    )
                )
        await s.flush()

        # lap_index ableiten
        for bib in crossings:
            await services.recompute_laps(s, event2026.id, bib)

        await s.commit()
        print("seed: Demo-Daten angelegt (Events 2025/2026, 5 Läufer, Zeiten).")
        print("seed: Verwaltungslinks (Startnummer-PDF testbar):")
        for name, bib, raw in manage_links:
            print(f"  #{bib} {name}: {settings.public_base_url}/manage?token={raw}")
        print(f"seed: Admin-Login -> {settings.public_base_url}/admin, E-Mail: admin@example.com")
        print("      (Magic-Link erscheint nach dem Login als [login-link] in diesen Logs)")


if __name__ == "__main__":
    asyncio.run(seed())
