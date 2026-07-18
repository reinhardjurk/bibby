#!/usr/bin/env bash
# Führt alle Testfälle nacheinander aus und bricht beim ersten Fehler ab.
# Argumente werden NICHT durchgereicht – die Lasttests laufen mit ihren Defaults.
set -euo pipefail
DIR="$(dirname "$0")"

for t in smoke.sh mail-mode.sh loadtest-timing.sh loadtest-register.sh; do
  bash "$DIR/$t"
done

printf '\n\033[1m== Alle Testfälle bestanden ==\033[0m\n'
