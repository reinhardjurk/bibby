#!/usr/bin/env bash
# Testfall: Mailversand-Schalter (live | test | off).
# Prüft, dass sich der Modus setzen und wieder auslesen lässt. Setzt NIE auf
# 'live' und stellt den ursprünglichen Modus am Ende wieder her.
source "$(dirname "$0")/_common.sh"

head "Mailversand-Schalter"
login

prev=$(mail_mode_get)
info "aktueller Modus: $prev"
restore() { mail_mode_set "$prev" >/dev/null 2>&1 || true; info "Modus auf '$prev' zurückgesetzt"; }
trap restore EXIT

mail_mode_set off
[ "$(mail_mode_get)" = "off" ] && pass "auf 'off' geschaltet" || fail "'off' nicht übernommen"

mail_mode_set test
[ "$(mail_mode_get)" = "test" ] && pass "auf 'test' geschaltet" || fail "'test' nicht übernommen"

head "Mailversand-Schalter OK"
