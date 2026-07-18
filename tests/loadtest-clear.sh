#!/usr/bin/env bash
# Testfall / Werkzeug: alle Lasttest-Daten wieder entfernen.
# Löscht ausschließlich markierte Daten (Anmeldungen @loadtest.*, deren
# Erfassungen, API-Lasttest-Erfassungen und -Geräte-Tokens). Echte Daten bleiben.
source "$(dirname "$0")/_common.sh"

head "Lasttest-Daten aufräumen gegen $API"
loadtest_api api-clear
head "Aufräumen abgeschlossen"
