# Transactional Email: Versanddomain registrieren. Nach dem Apply müssen die
# ausgegebenen DNS-Records (SPF, DKIM, MX) bei der Domain hinterlegt werden,
# danach verifiziert Scaleway die Domain automatisch.
resource "scaleway_tem_domain" "main" {
  name       = var.tem_domain
  accept_tos = true
}
