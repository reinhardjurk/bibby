variable "project_id" {
  description = "Scaleway Project ID"
  type        = string
}

variable "region" {
  description = "Scaleway Region"
  type        = string
  default     = "fr-par"
}

variable "zone" {
  description = "Scaleway Zone"
  type        = string
  default     = "fr-par-1"
}

variable "app_name" {
  description = "Präfix für Ressourcennamen"
  type        = string
  default     = "bibby"
}

# Eindeutiger Suffix, damit Bucket-Namen global eindeutig sind.
variable "bucket_suffix" {
  description = "Eindeutiger Suffix für globale Bucket-Namen"
  type        = string
}

# --- Anwendungs-Secrets (werden als secret_environment_variables injiziert) ---
variable "app_secret_key" {
  description = "HMAC-Schlüssel für Token-Hashing (BIBBY_SECRET_KEY)"
  type        = string
  sensitive   = true
}

variable "field_encryption_key" {
  description = "Fernet-Key für die IBAN-Feldverschlüsselung (urlsafe base64, 32 Byte)"
  type        = string
  sensitive   = true
}

variable "sepa_creditor_name" {
  description = "Name des SEPA-Gläubigers (für den Mandatstext)"
  type        = string
  default     = "Bibby Lauf e.V."
}

variable "sepa_creditor_id" {
  description = "SEPA-Gläubiger-Identifikationsnummer"
  type        = string
  default     = ""
}

variable "tem_api_key" {
  description = "Scaleway TEM API Key"
  type        = string
  sensitive   = true
  default     = ""
}

variable "public_base_url" {
  description = "Öffentliche URL der SPA (für Links in E-Mails)"
  type        = string
}

variable "tem_domain" {
  description = "Versanddomain für Transactional Email (z. B. mail.bibby.example)"
  type        = string
}

variable "cors_origins" {
  description = "Erlaubte Origins der SPA"
  type        = list(string)
}
