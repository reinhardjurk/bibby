"""E-Mail-Versand über Scaleway Transactional Email (TEM).

- Test-Modus (settings.mail_test_mode): leitet ALLE Mails an
  settings.mail_test_recipient um; der ursprüngliche Empfänger steht im Betreff.
- Ohne TEM-API-Key: Entwicklungs-Fallback, der die Mail nur ausgibt (loggt).
- Absender ist settings.tem_from_email; die Domäne muss in TEM verifiziert sein.
"""

from __future__ import annotations

import httpx

from .config import settings


async def send_email(
    *,
    to: str,
    subject: str,
    text: str,
    html: str | None = None,
    test_mode: bool | None = None,
) -> None:
    # test_mode überschreibt den Env-Default (kommt zur Laufzeit aus app_setting).
    effective_test_mode = settings.mail_test_mode if test_mode is None else test_mode
    recipient = to
    if effective_test_mode:
        # Sicherheitsnetz: nie echte Empfänger im Testbetrieb.
        recipient = settings.mail_test_recipient or settings.tem_from_email
        subject = f"[TEST → {to}] {subject}"

    # Ohne Secret Key nur loggen (lokale Entwicklung).
    if not settings.tem_secret_key:
        print(f"[email dev] to={recipient} subject={subject!r}\n{text}\n")
        return

    payload: dict = {
        "from": {"email": settings.tem_from_email, "name": settings.tem_from_name},
        "to": [{"email": recipient}],
        "subject": subject,
        "text": text,
        "project_id": settings.tem_project_id,
    }
    if html:
        payload["html"] = html

    url = (
        "https://api.scaleway.com/transactional-email/v1alpha1"
        f"/regions/{settings.scw_region}/emails"
    )
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            url, json=payload, headers={"X-Auth-Token": settings.tem_secret_key}
        )
    if resp.status_code >= 400:
        # Der Antwort-Body nennt die genaue Ursache (z. B. unverifizierte
        # Absender-Domäne, fehlende IAM-Berechtigung, falsche project_id).
        raise RuntimeError(f"TEM {resp.status_code}: {resp.text}")
