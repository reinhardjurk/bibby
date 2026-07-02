"""One-off: einen Admin-Benutzer anlegen (oder dessen Passwort setzen).

Aufruf (z. B. gegen die Prod-DB):

    BIBBY_DATABASE_URL="postgresql+asyncpg://<user>:<pass>@<host>:5432/<db>" \
    BIBBY_DATABASE_SSL=true BIBBY_SECRET_KEY=dev \
    python -m app.create_admin <email> <password>
"""

from __future__ import annotations

import asyncio
import sys

from sqlalchemy import select

from .db import SessionLocal
from .models import AppUser, UserRole
from .passwords import hash_password


async def main(email: str, password: str) -> None:
    async with SessionLocal() as session:
        user = (
            await session.execute(select(AppUser).where(AppUser.email == email))
        ).scalar_one_or_none()
        if user is None:
            user = AppUser(email=email, name=email, password_hash=hash_password(password))
            session.add(user)
            await session.flush()
            print(f"Benutzer angelegt: {email}")
        else:
            user.password_hash = hash_password(password)
            print(f"Passwort aktualisiert: {email}")

        has_admin = (
            await session.execute(
                select(UserRole).where(UserRole.user_id == user.id, UserRole.role == "admin")
            )
        ).scalar_one_or_none()
        if has_admin is None:
            session.add(UserRole(user_id=user.id, role="admin"))
        await session.commit()
        print("Rolle 'admin' gesetzt.")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python -m app.create_admin <email> <password>")
        raise SystemExit(1)
    asyncio.run(main(sys.argv[1], sys.argv[2]))
