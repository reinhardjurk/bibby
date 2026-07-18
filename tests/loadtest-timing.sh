#!/usr/bin/env bash
# Testfall: Zeiterfassungs-Lasttest über die echte Ingestion-API.
# Mehrere Zeitnehmer erfassen dieselben Startnummern; die Wiederholung (Offline-
# Queue) muss vollständig als Duplikat verworfen werden.
#
# Argumente (optional):  ZEITNEHMER BATCH STARTNUMMERN   (Default 4 25 200)
#
# Nutzt Startnummern ab 90001 – echte Anmeldungen werden nie berührt. Räumt die
# eigenen Erfassungen und Geräte-Tokens hinterher wieder ab.
source "$(dirname "$0")/_common.sh"

SENDERS="${1:-4}"
BATCH="${2:-25}"
BIBS="${3:-200}"

head "Zeiterfassungs-Lasttest ($SENDERS Zeitnehmer, Batch $BATCH, $BIBS Startnummern) gegen $API"
login

cleanup() {
  info "räume Lasttest-Daten auf"
  loadtest_api api-clear >/dev/null 2>&1 || true
}
trap cleanup EXIT

loadtest_api api-timing "$SENDERS" "$BATCH" "$BIBS"   # exitet ≠ 0 bei Fehlern

head "Zeiterfassungs-Lasttest bestanden"
