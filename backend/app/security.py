"""Token-Erzeugung/-Hashing und Auth-Dependencies (Geräte-Token + RBAC)."""

from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timezone

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .config import settings
from .db import get_session
from .models import AppUser, AuthToken, DeviceToken, UserRole

# --- Token-Helfer ---------------------------------------------------------
# Wir speichern nie den Klartext-Token, nur einen HMAC-Hash. Der Klartext
# wird einmal ausgegeben (Magic-Link / Geräte-Token) und ist danach weg.


def generate_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(raw: str) -> str:
    return hmac.new(settings.secret_key.encode(), raw.encode(), hashlib.sha256).hexdigest()


# --- Geräte-Token (Zeitnahme-Ingestion) -----------------------------------
async def require_device_token(
    authorization: str = Header(...),
    session: AsyncSession = Depends(get_session),
) -> DeviceToken:
    """Authentifiziert eine Ingestion-Quelle (Web-Maske, CV-App).

    Erwartet `Authorization: Bearer <token>`.
    """
    if not authorization.startswith("Bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Bearer-Token erwartet")
    token_hash = hash_token(authorization.removeprefix("Bearer ").strip())
    device = (
        await session.execute(
            select(DeviceToken).where(
                DeviceToken.token_hash == token_hash, DeviceToken.active.is_(True)
            )
        )
    ).scalar_one_or_none()
    if device is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Ungültiges Geräte-Token")
    device.last_used_at = datetime.now(timezone.utc)
    return device


# --- Organisator-Login (Magic-Link) + RBAC --------------------------------
async def current_user(
    authorization: str = Header(...),
    session: AsyncSession = Depends(get_session),
) -> AppUser:
    """Löst einen Session-Token zu einem AppUser auf (inkl. Rollen)."""
    if not authorization.startswith("Bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Bearer-Token erwartet")
    token_hash = hash_token(authorization.removeprefix("Bearer ").strip())
    auth = (
        await session.execute(select(AuthToken).where(AuthToken.token_hash == token_hash))
    ).scalar_one_or_none()
    if auth is None or auth.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sitzung ungültig oder abgelaufen")
    user = await session.get(AppUser, auth.user_id)
    if user is None or not user.active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Benutzer inaktiv")
    return user


async def user_roles(session: AsyncSession, user_id) -> set[str]:
    rows = (
        await session.execute(select(UserRole.role).where(UserRole.user_id == user_id))
    ).scalars()
    return set(rows)


def require_roles(*allowed: str):
    """Dependency-Factory: erlaubt Zugriff, wenn der Nutzer >=1 der Rollen hat.

    `admin` darf implizit alles.
    """

    async def _dep(
        user: AppUser = Depends(current_user),
        session: AsyncSession = Depends(get_session),
    ) -> AppUser:
        roles = await user_roles(session, user.id)
        if "admin" in roles or roles.intersection(allowed):
            return user
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Fehlende Berechtigung")

    return _dep
