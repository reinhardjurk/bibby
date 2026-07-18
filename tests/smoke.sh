#!/usr/bin/env bash
# Testfall: Grundfunktionen erreichbar (Health, Version, öffentliche Events, Admin-Login).
# Ändert nichts – ungefährlich auch gegen Production.
source "$(dirname "$0")/_common.sh"

head "Smoke-Test gegen $API"

info "GET /health"
curl -sf "$API/health" | grep -q '"ok"' && pass "Health OK" || fail "Health antwortet nicht wie erwartet"

info "GET /version"
ver=$(curl -sf "$API/version") || fail "/version nicht erreichbar"
echo "   $ver"
pass "Version erreichbar"

info "GET /events (öffentlich)"
n=$(curl -sf "$API/events" | python3 -c 'import sys,json;print(len(json.load(sys.stdin)))') \
  || fail "/events nicht erreichbar"
pass "$n Event(s) sichtbar"

info "Admin-Login"
login
roles=$(admin_get /admin/me | python3 -c 'import sys,json;print(",".join(json.load(sys.stdin)["roles"]))')
pass "Login OK, Rollen: $roles"

head "Smoke-Test bestanden"
