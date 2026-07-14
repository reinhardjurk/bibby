#!/usr/bin/env bash
#
# Bibby-Deploy: Backend-Image bauen/pushen/ausrollen + SPA bauen/hochladen.
#
# Voraussetzungen (Env):
#   SCW_ACCESS_KEY, SCW_SECRET_KEY   – Scaleway-Zugang (Registry + Object Storage)
#   scw CLI konfiguriert             – für den Container-Redeploy
#   frontend/.env mit VITE_API_BASE  – API-URL fürs SPA-Build
#
# Aufruf:
#   ./deploy.sh            # Backend UND Frontend
#   ./deploy.sh backend    # nur Backend
#   ./deploy.sh frontend   # nur Frontend
#
# Migrationen laufen bewusst NICHT hier mit (separat, siehe infra/README.md):
#   cd backend && source .venv/bin/activate
#   BIBBY_DATABASE_URL="$(cd ../infra && tofu output -raw database_url)" \
#   BIBBY_DATABASE_SSL=true BIBBY_SECRET_KEY=x alembic upgrade head

set -euo pipefail

# --- Konfiguration (per Env überschreibbar) -------------------------------
REG="${BIBBY_REGISTRY:-rg.fr-par.scw.cloud/bibby}"
IMAGE="$REG/bibby-api:latest"
BUCKET="${BIBBY_SPA_BUCKET:-bibby-spa-runbibby}"
CONTAINER_ID="${BIBBY_CONTAINER_ID:-fe9700dd-cbed-4313-9df0-5e493447968a}"
S3_ENDPOINT="${BIBBY_S3_ENDPOINT:-https://s3.fr-par.scw.cloud}"

TARGET="${1:-all}"
case "$TARGET" in all|backend|frontend) ;; *) echo "Aufruf: $0 [all|backend|frontend]"; exit 2 ;; esac

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

BUILD="$(git rev-parse --short HEAD)"
echo "==> Bibby-Deploy | Ziel: $TARGET | Build: $BUILD"

# --- Voraussetzungen prüfen ------------------------------------------------
: "${SCW_ACCESS_KEY:?SCW_ACCESS_KEY muss gesetzt sein}"
: "${SCW_SECRET_KEY:?SCW_SECRET_KEY muss gesetzt sein}"

need() { command -v "$1" >/dev/null 2>&1 || { echo "FEHLT: $1"; exit 1; }; }

# --- Backend ---------------------------------------------------------------
if [[ "$TARGET" == "all" || "$TARGET" == "backend" ]]; then
  need docker; need scw
  echo "==> Backend-Image bauen (amd64, ohne Cache)"
  docker build --no-cache --pull --platform linux/amd64 \
    --build-arg BUILD="$BUILD" -t "$IMAGE" backend

  echo "==> In die Registry pushen"
  echo "$SCW_SECRET_KEY" | docker login "$REG" -u nologin --password-stdin
  docker push "$IMAGE"

  echo "==> Container neu ausrollen ($CONTAINER_ID)"
  scw container container redeploy "$CONTAINER_ID" >/dev/null
  echo "    Redeploy angestoßen."
fi

# --- Frontend --------------------------------------------------------------
if [[ "$TARGET" == "all" || "$TARGET" == "frontend" ]]; then
  need npm; need aws
  [[ -f frontend/.env ]] || echo "WARN: frontend/.env fehlt – VITE_API_BASE prüfen!"
  echo "==> SPA bauen"
  ( cd frontend && VITE_BUILD="$BUILD" npm run build )

  echo "==> SPA hochladen nach s3://$BUCKET"
  AWS_ACCESS_KEY_ID="$SCW_ACCESS_KEY" AWS_SECRET_ACCESS_KEY="$SCW_SECRET_KEY" \
    aws s3 sync frontend/dist/ "s3://$BUCKET" --endpoint-url "$S3_ENDPOINT" --delete
fi

echo "==> Fertig. Build $BUILD ausgerollt."
echo "    Kontrolle: unten auf der Seite sollte 'Frontend $BUILD · Backend $BUILD' stehen."
echo "    (Backend-Redeploy braucht ~1 Min, bis er 'ready' ist.)"
