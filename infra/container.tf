# IAM-Application + API-Key, mit dem der Container auf die Serverless SQL DB
# zugreift. Die Keys gehen als DB-Credentials in die DATABASE_URL.
resource "scaleway_iam_application" "api" {
  name = "${var.app_name}-api"
}

resource "scaleway_iam_policy" "api_db" {
  name           = "${var.app_name}-api-db"
  application_id = scaleway_iam_application.api.id

  rule {
    project_ids          = [var.project_id]
    permission_set_names = ["ServerlessSQLDatabaseReadWrite"]
  }
}

resource "scaleway_iam_api_key" "api" {
  application_id = scaleway_iam_application.api.id
  description    = "DB-Zugriff des Bibby-API-Containers"
}

locals {
  # asyncpg + SQLAlchemy. SSL-Handling ggf. über connect_args in db.py ergänzen.
  database_url = "postgresql+asyncpg://${scaleway_iam_api_key.api.access_key}:${scaleway_iam_api_key.api.secret_key}@${scaleway_sdb_sql_database.main.endpoint}"
}

resource "scaleway_container_namespace" "main" {
  name = var.app_name
}

resource "scaleway_container" "api" {
  namespace_id   = scaleway_container_namespace.main.id
  name           = "${var.app_name}-api"
  registry_image = "${scaleway_registry_namespace.main.endpoint}/${var.app_name}-api:latest"
  port           = 8000
  cpu_limit      = 1000
  memory_limit   = 1024
  min_scale      = 0
  max_scale      = 5
  deploy         = true

  environment_variables = {
    BIBBY_PUBLIC_BASE_URL    = var.public_base_url
    BIBBY_CORS_ORIGINS       = jsonencode(var.cors_origins)
    BIBBY_SEPA_CREDITOR_NAME = var.sepa_creditor_name
    BIBBY_SEPA_CREDITOR_ID   = var.sepa_creditor_id
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
    BIBBY_TEM_API_KEY          = var.tem_api_key
  }
}
