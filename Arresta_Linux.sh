#!/bin/bash
# Arresta SOLO interfaccia_locale.py in ascolto sulla porta 8765.
PID="$( (lsof -ti tcp:8765 -sTCP:LISTEN 2>/dev/null || ss -ltnp 2>/dev/null | grep ':8765 ' | sed 's/.*pid=\([0-9]*\).*/\1/') | head -n1)"
[ -z "$PID" ] && { echo "ANALISI CRISI non è in esecuzione."; exit 0; }
case "$(ps -p "$PID" -o args= 2>/dev/null)" in *interfaccia_locale.py*) kill "$PID" && echo "Fermata. I dati restano salvati.";; *) echo "Sulla porta 8765 c'è un altro programma: non lo chiudo."; exit 1;; esac
