# DB-Zugangsdaten kommen als Variablen (ein API-Key mit
# ServerlessSQLDatabaseReadWrite). So muss Terraform kein IAM verwalten.
locals {
  # Das endpoint-Attribut enthält ein "postgres://"-Präfix -> abschneiden und
  # Credentials + asyncpg-Treiber einsetzen. SSL erledigt db.py (database_ssl).
  # Auth: Username = API-Key Access-Key, Passwort = Secret-Key.
  # postgres://-Präfix und ?sslmode=…-Query entfernen (asyncpg kennt sslmode
  # nicht; SSL erledigt db.py via connect_args).
  db_host      = split("?", trimprefix(scaleway_sdb_sql_database.main.endpoint, "postgres://"))[0]
  database_url = "postgresql+asyncpg://${var.db_access_key}:${var.db_secret_key}@${local.db_host}"
}

resource "scaleway_container_namespace" "main" {
  name = var.app_name
}

# Wird erst angelegt, wenn deploy_container=true (das Image muss dann in der
# Registry liegen, Scaleway prüft es bereits beim Erstellen).
resource "scaleway_container" "api" {
  count          = var.deploy_container ? 1 : 0
  namespace_id   = scaleway_container_namespace.main.id
  name           = "${var.app_name}-api"
  registry_image = "${scaleway_registry_namespace.main.endpoint}/${var.app_name}-api:latest"
  port           = 8000
  cpu_limit      = 1000
  memory_limit   = 1024
  min_scale      = var.min_scale
  max_scale      = 5
  deploy         = true

  # "redirected" = nur HTTPS (HTTP wird auf HTTPS umgeleitet) -> HTTPSConnectionsOnly=true.
  # "enabled"    = HTTP UND HTTPS erlaubt                     -> HTTPSConnectionsOnly=false.
  http_option = "redirected"

  environment_variables = {
    BIBBY_PUBLIC_BASE_URL    = var.public_base_url
    BIBBY_DATABASE_SSL       = "true"
    BIBBY_CORS_ORIGINS       = jsonencode(var.cors_origins)
    BIBBY_SEPA_CREDITOR_NAME = var.sepa_creditor_name
    BIBBY_SEPA_CREDITOR_ID   = var.sepa_creditor_id
    BIBBY_MIN_LAP_SECONDS    = tostring(var.min_lap_seconds)
    # E-Mail (TEM)
    BIBBY_TEM_FROM_EMAIL      = "no-reply@${var.tem_domain}"
    BIBBY_TEM_FROM_NAME       = var.tem_from_name
    BIBBY_TEM_PROJECT_ID      = var.project_id
    BIBBY_SCW_REGION          = var.region
    BIBBY_MAIL_TEST_MODE      = tostring(var.mail_test_mode)
    BIBBY_MAIL_TEST_RECIPIENT = var.mail_test_recipient
  }

  secret_environment_variables = {
    BIBBY_DATABASE_URL         = local.database_url
    BIBBY_SECRET_KEY           = var.app_secret_key
    BIBBY_FIELD_ENCRYPTION_KEY = var.field_encryption_key
    BIBBY_TEM_SECRET_KEY       = var.tem_secret_key
  }
}
