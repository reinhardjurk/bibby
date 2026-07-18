#!/usr/bin/env bash
# Gemeinsame Helfer für die Bibby-Testskripte.
# Wird von jedem Testfall gesourct – nicht direkt ausführen.
#
# Erwartete Umgebungsvariablen:
#   BIBBY_ADMIN_EMAIL       Admin-Login (Pflicht)
#   BIBBY_ADMIN_PASSWORD    Admin-Passwort (Pflicht)
#   BIBBY_API_BASE          API-URL (optional, Default http://localhost:8000)
#   BIBBY_LOADTEST_CMD      wie 'python -m app.loadtest' aufgerufen wird
#                           (optional; Default: python3 -m app.loadtest aus backend/).
#                           Für Docker z. B.:
#                             export BIBBY_LOADTEST_CMD="docker compose exec -T api python -m app.loadtest"

set -euo pipefail

: "${BIBBY_ADMIN_EMAIL:?BIBBY_ADMIN_EMAIL setzen (Admin-Login)}"
: "${BIBBY_ADMIN_PASSWORD:?BIBBY_ADMIN_PASSWORD setzen (Admin-Passwort)}"

API="${BIBBY_API_BASE:-http://localhost:8000}"
API="${API%/}"
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# --- Ausgabe --------------------------------------------------------------
if [ -t 1 ]; then G='\033[32m'; R='\033[31m'; B='\033[1m'; N='\033[0m'; else G=''; R=''; B=''; N=''; fi
info() { printf '»  %s\n' "$*"; }
pass() { printf "   ${G}OK${N}     %s\n" "$*"; }
fail() { printf "   ${R}FEHLER${N} %s\n" "$*"; exit 1; }
head() { printf "\n${B}== %s ==${N}\n" "$*"; }

# --- kleine JSON-Feldextraktion (ohne jq-Zwang) ---------------------------
json_field() { python3 -c 'import sys,json;print(json.load(sys.stdin)[sys.argv[1]])' "$1"; }

# --- Auth -----------------------------------------------------------------
TOKEN=""
login() {
  local body resp
  body=$(printf '{"email":"%s","password":"%s"}' "$BIBBY_ADMIN_EMAIL" "$BIBBY_ADMIN_PASSWORD")
  resp=$(curl -sf -X POST "$API/admin/auth/login" -H 'Content-Type: application/json' -d "$body") \
    || fail "Login fehlgeschlagen – BIBBY_ADMIN_EMAIL/PASSWORD und BIBBY_API_BASE prüfen ($API)."
  TOKEN=$(printf '%s' "$resp" | json_field token)
}
admin_get()   { curl -sf -H "Authorization: Bearer $TOKEN" "$API$1"; }
admin_patch() { curl -sf -X PATCH -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d "$2" "$API$1"; }
admin_post()  { curl -sf -X POST  -H "Authorization: Bearer $TOKEN" "$API$1"; }

# --- Mailversand-Schalter (live | test | off) -----------------------------
mail_mode_get() { admin_get /admin/mail-settings | json_field mode; }
mail_mode_set() { admin_patch /admin/mail-settings "{\"mode\":\"$1\"}" >/dev/null; }

# --- Lasttest-CLI ---------------------------------------------------------
# Standard: python3 -m app.loadtest aus backend/. Override via BIBBY_LOADTEST_CMD.
loadtest() {
  if [ -n "${BIBBY_LOADTEST_CMD:-}" ]; then
    $BIBBY_LOADTEST_CMD "$@"
  else
    ( cd "$REPO/backend" && python3 -m app.loadtest "$@" )
  fi
}
# Bequemer Wrapper: hängt URL + Zugangsdaten an einen api-*-Befehl an.
loadtest_api() {
  local cmd="$1"; shift
  loadtest "$cmd" "$API" "$BIBBY_ADMIN_EMAIL" "$BIBBY_ADMIN_PASSWORD" "$@"
}
