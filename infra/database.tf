# Serverless SQL Database (PostgreSQL, skaliert auf 0).
resource "scaleway_sdb_sql_database" "main" {
  name    = "${var.app_name}-db"
  min_cpu = 0
  max_cpu = 4
}

# Hinweis: Serverless SQL authentifiziert über IAM. Die DATABASE_URL wird in
# container.tf aus dem Endpoint + den IAM-Keys zusammengesetzt. Der genaue
# Aufbau des `endpoint`-Attributs sollte nach dem ersten `apply` gegen die
# tatsächliche Ausgabe geprüft werden.
