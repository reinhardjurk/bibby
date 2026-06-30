# Container Registry für das API-Image.
resource "scaleway_registry_namespace" "main" {
  name      = var.app_name
  is_public = false
}

# Build & Push (außerhalb von Terraform), z. B.:
#   docker build -t ${endpoint}/bibby-api:latest ../backend
#   docker login ${endpoint} -u nologin -p $SCW_SECRET_KEY
#   docker push ${endpoint}/bibby-api:latest
