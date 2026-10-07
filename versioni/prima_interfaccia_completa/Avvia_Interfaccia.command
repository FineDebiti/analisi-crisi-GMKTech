#!/bin/bash
# Avvia l'interfaccia ANALISI CRISI. Solo sul tuo Mac: http://127.0.0.1:8765
# Per usarla dal Mac mini via Tailscale: ANALISI_PIN=<pin> ./Avvia_Interfaccia.command rete <IP-Tailscale>
cd "$(dirname "$0")"
PY=".venv/bin/python"; [ -x "$PY" ] || PY="python3"
RADICE="$HOME/Riservato_AnalisiCrisi/CASI"
if [ "$1" = "rete" ] && [ -n "$2" ]; then exec "$PY" interfaccia_locale.py --radice "$RADICE" --host "$2"; fi
open "http://127.0.0.1:8765" &
exec "$PY" interfaccia_locale.py --radice "$RADICE"
