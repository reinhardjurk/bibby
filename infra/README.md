# Bibby — Infrastruktur (Terraform / Scaleway)

Provisioniert die serverlose Umgebung auf Scaleway.

| Ressource | Datei | Zweck |
|---|---|---|
| Serverless SQL Database | `database.tf` | PostgreSQL, skaliert auf 0 |
| Container Registry | `registry.tf` | API-Image |
| Serverless Container + IAM | `container.tf` | FastAPI-API, DB-Zugriff via IAM-Key |
| Object Storage + Website | `storage.tf` | SPA-Hosting (Deep-Link-Rewrite) + privater PDF-Bucket |
| Transactional Email | `tem.tf` | Versanddomain |

## Reihenfolge

```bash
# 0. Anmeldedaten
export SCW_ACCESS_KEY=... SCW_SECRET_KEY=... SCW_DEFAULT_PROJECT_ID=...
export TF_VAR_app_secret_key=... TF_VAR_field_encryption_key=... TF_VAR_tem_secret_key=...

cd infra
cp terraform.tfvars.example terraform.tfvars   # restliche Werte eintragen
terraform init
terraform apply

# 1. API-Image bauen & pushen (Registry-Endpoint aus dem Output)
REG=$(terraform output -raw registry_endpoint)
docker build -t $REG/bibby-api:latest ../backend
docker login $REG -u nologin -p $SCW_SECRET_KEY
docker push $REG/bibby-api:latest
terraform apply   # Container zieht das Image

# 2. DB-Schema einspielen (DATABASE_URL aus db_endpoint + IAM-Key)
psql "<connection-string>" -f ../db/schema.sql

# 3. SPA bauen & hochladen
cd ../frontend && npm run build
aws s3 sync dist/ s3://$(cd ../infra && terraform output -raw spa_bucket) \
  --endpoint-url https://s3.fr-par.scw.cloud
```

## Noch manuell / zu verifizieren

- **DATABASE_URL**: In `container.tf` aus Endpoint + IAM-Key zusammengesetzt.
  Format nach dem ersten `apply` gegen `terraform output db_endpoint` prüfen.
  Für asyncpg muss SSL ggf. über `connect_args` in `backend/app/db.py` gesetzt
  werden (Serverless SQL verlangt TLS).
- **TEM-DNS**: Nach `apply` die ausgegebenen SPF/DKIM/MX-Records bei der Domain
  hinterlegen; Scaleway verifiziert dann automatisch.
- **CDN/TLS + eigene Domain**: Über **Scaleway Edge Services** vor den
  Website-Endpoint schalten (`scaleway_edge_services_pipeline` mit Backend-,
  Cache-, TLS- und DNS-Stage). Bewusst nicht ausmodelliert, da die Felder
  account-/feature-abhängig sind — als eigener Schritt nach dem Grund-Setup.
- **IBAN-Verschlüsselung**: `field_encryption_key` (Fernet) muss gesetzt sein
  und darf sich nicht ändern, sonst sind gespeicherte IBANs nicht mehr
  entschlüsselbar. Erzeugen mit
  `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`.
- **SEPA**: `sepa_creditor_id`/`sepa_creditor_name` für den Mandatstext setzen.
  Lastschrifteinzug selbst läuft offline (Banking/SEPA-XML) – das System erfasst
  nur Mandat + IBAN und den Bezahlstatus.

## Hinweis

`terraform`/`tofu` und Docker sind auf dem aktuellen Rechner nicht installiert —
diese Konfiguration wurde daher **nicht** mit `terraform validate`/`plan`
geprüft. Vor dem ersten Einsatz `terraform init && terraform validate` laufen
lassen; einzelne Attributnamen (z. B. DB-`endpoint`, Container-`domain_name`)
können je nach Provider-Version minimal abweichen.
