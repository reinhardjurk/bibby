# Anmeldedaten bevorzugt über Umgebungsvariablen setzen:
#   SCW_ACCESS_KEY, SCW_SECRET_KEY, SCW_DEFAULT_PROJECT_ID,
#   SCW_DEFAULT_ORGANIZATION_ID
# Dann bleiben die Variablen unten leer und werden aus der Umgebung gezogen.

provider "scaleway" {
  region  = var.region
  zone    = var.zone
  project_id = var.project_id
}
