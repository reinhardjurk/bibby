"""App-seitige Feldverschlüsselung für sensible Daten (IBAN)."""

from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from .config import settings


def _key() -> bytes:
    if settings.field_encryption_key:
        return settings.field_encryption_key.encode()
    # Fallback: deterministisch aus secret_key ableiten (nur Entwicklung).
    return base64.urlsafe_b64encode(hashlib.sha256(settings.secret_key.encode()).digest())


_fernet = Fernet(_key())


def encrypt(plaintext: str) -> str:
    return _fernet.encrypt(plaintext.encode()).decode()


def decrypt(token: str) -> str:
    return _fernet.decrypt(token.encode()).decode()


def try_decrypt(token: str) -> str | None:
    """Wie decrypt(), aber None statt Exception, wenn der Token nicht zum aktuellen
    Key passt (z.B. nach Key-/Secret-Rotation). So reißt ein einzelner unlesbarer
    Datensatz nicht einen ganzen Export in einen 500."""
    try:
        return decrypt(token)
    except (InvalidToken, ValueError):
        return None


def mask_iban(iban: str) -> str:
    """DE89 3704 0044 0532 0130 00 -> 'DE89 **** 3000'."""
    s = iban.replace(" ", "")
    if len(s) < 8:
        return "****"
    return f"{s[:4]} **** {s[-4:]}"
