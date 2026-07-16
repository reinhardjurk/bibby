# CI/CD & Browser-Betrieb (GitHub Actions + Scaleway)

Ziel: Code + Deploys **aus dem Browser**, ohne Secrets/Build/Terraform auf dem
eigenen Rechner, teamfähig.

- **Code bearbeiten:** im Repo `.` drücken → `github.dev` (VS Code im Browser) →
  editieren + committen.
- **App deployen:** GitHub → **Actions → „Deploy" → Run workflow** (Ziel wählen,
  Migrationen an/aus). Läuft in Environment `production` → wartet auf Freigabe.
- **Infrastruktur ändern:** GitHub → **Actions → „Terraform"** (`plan` frei,
  `apply` mit Freigabe).

Das Deploy-Skript `./deploy.sh` bleibt für Notfälle vom Terminal bestehen; im
Normalbetrieb macht alles die Pipeline.

---

## Einmalige Einrichtung (einmal vom aktuellen Rechner, danach nie wieder)

### 1. Privaten State-Bucket anlegen
Scaleway Console → Object Storage → Bucket **`bibby-tfstate`** in **fr-par**,
Sichtbarkeit **privat**. (Enthält Secrets → niemals öffentlich.)

### 2. Terraform-State dorthin migrieren
`infra/backend.tf` ist bereits im Repo. Einmalig lokal:
```bash
cd infra
AWS_ACCESS_KEY_ID=$SCW_ACCESS_KEY AWS_SECRET_ACCESS_KEY=$SCW_SECRET_KEY \
  tofu init -migrate-state
```
Danach liegt der State im Bucket; das lokale `terraform.tfstate` wird nicht mehr
gebraucht.

### 3. GitHub Environment „production" anlegen
Repo → Settings → **Environments** → **New environment** → `production` →
**Required reviewers** = du (und Teammitglieder). Damit muss jeder Deploy/Apply
freigegeben werden.

### 4. Repository-Variablen (nicht geheim)
Settings → Secrets and variables → **Actions → Variables**:

| Name | Wert |
|---|---|
| `BIBBY_REGISTRY` | `rg.fr-par.scw.cloud/bibby` |
| `BIBBY_CONTAINER_ID` | `fe9700dd-cbed-4313-9df0-5e493447968a` |
| `BIBBY_SPA_BUCKET` | `bibby-spa-runbibby` |
| `BIBBY_S3_ENDPOINT` | `https://s3.fr-par.scw.cloud` |
| `VITE_API_BASE` | `https://bibbye668d8a3-bibby-api.functions.fnc.fr-par.scw.cloud` |
| `SCW_DEFAULT_PROJECT_ID` | `d7cd73e2-d1c7-4d87-969a-470eb2efeea0` |
| `SCW_DEFAULT_ORGANIZATION_ID` | *(deine Organisations-UUID)* |

### 5. Repository-Secrets (geheim)
Settings → Secrets and variables → **Actions → Secrets**:

| Name | Inhalt |
|---|---|
| `SCW_ACCESS_KEY` | Scaleway Access Key (`SCWXXXX…`) |
| `SCW_SECRET_KEY` | Scaleway Secret Key |
| `BIBBY_DATABASE_URL` | `postgresql+asyncpg://d0e6b670-…:<db-secret>@<host>:5432/<db>` — hol den Wert mit `cd infra && tofu output -raw database_url` |
| `TFVARS` | **Kompletter Inhalt** von `infra/terraform.tfvars** — plus die bisher als `TF_VAR_*` gesetzten Werte (siehe unten) |

**`TFVARS`** muss ALLE Terraform-Variablen enthalten, auch die, die du früher als
`export TF_VAR_…` gesetzt hattest:
```hcl
# ... dein bisheriger terraform.tfvars-Inhalt ...
db_access_key       = "d0e6b670-9e8d-4c42-ae14-a97d515be965"   # Principal-UUID
db_secret_key       = "<dein SCW Secret Key>"
app_secret_key      = "<BIBBY_SECRET_KEY>"
field_encryption_key= "<Fernet-Key>"
tem_secret_key      = "<TEM Secret Key>"
deploy_container    = true
```

---

## Nutzung im Alltag

**Codeänderung + Deploy (nur App):**
1. Repo öffnen, `.` drücken → github.dev → Datei ändern → committen (Branch/PR
   nach Geschmack, dann mergen).
2. Actions → **Deploy** → *Run workflow*: `target=all`, `migrate=true` bei
   Schema-Änderung (sonst false) → **Freigabe erteilen**.
3. Unten auf der Seite prüfen: `Frontend <sha> · Backend <sha> · DB <rev>`.

**Nur Frontend / nur Backend:** `target=frontend` bzw. `backend`.

**Infra-Änderung:** Datei in `infra/` ändern → Actions → **Terraform** →
`action=plan` ansehen → erneut mit `action=apply` (Freigabe).

---

## Team & Sicherheit

- **Branch Protection** auf `main` (Settings → Branches): PR + Review erzwingen.
- **Least-privilege API-Key:** Lege in Scaleway IAM einen eigenen Key nur für CI
  an (Rechte: Container/Registry/ObjectStorage/ServerlessSQL Read+Write) und nutze
  den in `SCW_ACCESS_KEY`/`SCW_SECRET_KEY` — nicht deinen persönlichen.
- Wer Push-/Actions-Rechte hat, kann über die Freigabe indirekt deployen → das
  `production`-Environment mit Reviewern ist das Schutz-Gate.
- Secrets sind in GitHub verschlüsselt und in Logs maskiert; der State-Bucket ist
  privat. Trotzdem: Zugriff auf das Repo = potenzielle Deploy-Macht → Mitglieder
  bewusst wählen.

---

## Alternativen (falls gewünscht)

- **GitHub Codespaces** statt github.dev: volles VS-Code-Terminal im Browser
  (bauen/testen in der Cloud) — kostet nach Freikontingent.
- **Terraform Cloud (HCP)** statt Scaleway-Bucket fürs State: inkl. State-Locking
  und Web-UI — robuster fürs Team.
- **Auto-Deploy bei Push** statt Knopf: im `deploy.yml` einen `push`-Trigger auf
  `main` ergänzen (weniger Kontrolle, dafür bequemer).
