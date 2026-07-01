from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Konfiguration über Umgebungsvariablen (Prefix BIBBY_) bzw. .env.

    In Produktion kommen die Secrets aus dem Scaleway Secret Manager und
    werden als Env-Variablen in den Serverless Container injiziert.
    """

    model_config = SettingsConfigDict(env_prefix="BIBBY_", env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://localhost/bibby"
    # TLS zur DB erzwingen (Scaleway Serverless SQL verlangt SSL). Lokal false.
    database_ssl: bool = False
    # HMAC-Schlüssel zum Hashen von Magic-Link- und Geräte-Tokens.
    secret_key: str = "change-me-in-production"

    # Öffentliche Basis-URL der SPA (für Links in E-Mails).
    public_base_url: str = "https://bibby.example"

    # App-seitige Feldverschlüsselung (IBAN). Fernet-Key (urlsafe base64, 32 Byte).
    # Leer = aus secret_key abgeleitet (nur für Entwicklung empfohlen).
    field_encryption_key: str = ""

    # SEPA-Lastschrift: Gläubiger-Angaben für den Mandatstext.
    sepa_creditor_name: str = "Bibby Lauf e.V."
    sepa_creditor_id: str = "DE00ZZZ00000000000"

    # Scaleway Transactional Email (TEM)
    # Nur der Secret Key des API-Keys (X-Auth-Token); der Access Key ID wird
    # für die HTTP-API NICHT benötigt.
    tem_secret_key: str = ""
    tem_project_id: str = ""                    # Scaleway Project ID (für den API-Call)
    scw_region: str = "fr-par"
    tem_from_email: str = "no-reply@bibby.example"  # Absender – Domäne muss in TEM verifiziert sein
    tem_from_name: str = "Bibby"

    # Test-Modus: leitet ALLE ausgehenden Mails an eine feste Adresse um.
    # Standardmäßig an, damit lokal/Test niemals echte Teilnehmer angemailt werden.
    mail_test_mode: bool = True
    mail_test_recipient: str = ""

    default_currency: str = "EUR"
    # Startnummer wird bei der Anmeldung fortlaufend vergeben; erste Nummer:
    bib_start_number: int = 1
    # Fallback-T-Shirt-Optionen, falls das Event keine eigenen konfiguriert hat.
    default_tshirt_options: list[str] = ["Kein T-Shirt (Spende)", "XS", "S", "M", "L", "XL"]
    # Mindestabstand zweier Linienüberquerungen derselben Startnummer (Sek.).
    # Schützt vor Doppelerfassung; kürzere Abstände werden als duplicate markiert.
    min_lap_seconds: int = 60

    cors_origins: list[str] = ["http://localhost:5173"]


settings = Settings()
