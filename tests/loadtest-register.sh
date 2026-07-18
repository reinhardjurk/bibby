#!/usr/bin/env bash
# Testfall: Anmelde-Lasttest über die echte API (POST /registrations).
# Prüft die Startnummernvergabe unter Nebenläufigkeit (eindeutig + lückenlos).
#
# Argumente (optional):  ANZAHL PARALLEL   (Default 100 10)
#
# Setzt den Mailversand für die Dauer des Tests auf 'off' (sonst würde jede
# Testanmeldung eine echte Bestätigungsmail auslösen), räumt die Testdaten
# hinterher wieder ab und stellt den Mailmodus zurück – egal ob Erfolg oder Fehler.
source "$(dirname "$0")/_common.sh"

COUNT="${1:-100}"
PARALLEL="${2:-10}"

head "Anmelde-Lasttest ($COUNT Anmeldungen, $PARALLEL parallel) gegen $API"
login

prev=$(mail_mode_get)
info "Mailversand: $prev -> 'off' für die Dauer des Tests"

cleanup() {
  info "räume Lasttest-Daten auf"
  loadtest_api api-clear >/dev/null 2>&1 || true
  mail_mode_set "$prev" >/dev/null 2>&1 || true
  info "Mailversand auf '$prev' zurückgesetzt"
}
trap cleanup EXIT

mail_mode_set off
loadtest_api api-register "$COUNT" "$PARALLEL"   # exitet ≠ 0, wenn eine Prüfung scheitert

head "Anmelde-Lasttest bestanden"
