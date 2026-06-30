# --- SPA-Bucket (statisches Hosting) ---
resource "scaleway_object_bucket" "spa" {
  name = "${var.app_name}-spa-${var.bucket_suffix}"
}

resource "scaleway_object_bucket_website_configuration" "spa" {
  bucket = scaleway_object_bucket.spa.id

  index_document {
    suffix = "index.html"
  }

  # SPA-Deep-Links (/manage, /results) auf index.html zurückführen.
  error_document {
    key = "index.html"
  }
}

# Öffentlicher Lesezugriff für die ausgelieferten Assets.
resource "scaleway_object_bucket_policy" "spa_public" {
  bucket = scaleway_object_bucket.spa.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid       = "PublicRead"
      Effect    = "Allow"
      Principal = "*"
      Action    = ["s3:GetObject"]
      Resource  = ["${scaleway_object_bucket.spa.name}/*"]
    }]
  })
}

# --- PDF-Bucket (privat: Startnummern) ---
resource "scaleway_object_bucket" "pdf" {
  name = "${var.app_name}-pdf-${var.bucket_suffix}"
}

# Hinweis CDN/TLS + eigene Domain: Scaleway Edge Services
# (scaleway_edge_services_pipeline + backend/cache/tls/dns stages) vor den
# Website-Endpoint schalten. Bewusst nicht vollständig ausmodelliert, da die
# Felder accountabhängig sind — siehe README, Abschnitt "CDN".
