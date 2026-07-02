output "api_endpoint" {
  description = "Öffentliche URL des API-Containers (erst nach deploy_container=true)"
  value       = one(scaleway_container.api[*].domain_name)
}

output "registry_endpoint" {
  description = "Registry-Endpoint zum Pushen des API-Images"
  value       = scaleway_registry_namespace.main.endpoint
}

output "spa_website_endpoint" {
  description = "Website-Endpoint des SPA-Buckets"
  value       = scaleway_object_bucket_website_configuration.spa.website_endpoint
}

output "spa_bucket" {
  description = "Name des SPA-Buckets (für den Asset-Upload)"
  value       = scaleway_object_bucket.spa.name
}

output "pdf_bucket" {
  description = "Privater Bucket für Startnummern-PDFs"
  value       = scaleway_object_bucket.pdf.name
}

output "db_endpoint" {
  description = "Endpoint der Serverless SQL Database (roh, mit postgres://-Präfix)"
  value       = scaleway_sdb_sql_database.main.endpoint
}

output "database_url" {
  description = "Zusammengesetzte DATABASE_URL (asyncpg) – zum Prüfen/Debuggen"
  value       = local.database_url
  sensitive   = true
}

output "tem_dns_records" {
  description = "DNS-Records, die für die Mail-Domain gesetzt werden müssen"
  value       = scaleway_tem_domain.main.reputation
  sensitive   = false
}
