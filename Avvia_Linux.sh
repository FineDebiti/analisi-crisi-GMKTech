#!/bin/bash
# Avvia l'interfaccia: locale http://127.0.0.1:8765 (predefinito). Da altro PC della rete privata: bash Avvia_Linux.sh rete IP  (richiede PIN).
cd "$(dirname "$0")" || exit 1
PY=".venv/bin/python"; "$PY" -c 'import reportlab, pdfplumber' 2>/dev/null || { echo "Esegui prima Installa_Linux.sh"; exit 1; }
RADICE="${ANALISI_RADICE:-$HOME/Riservato_AnalisiCrisi/CASI}"; mkdir -p "$RADICE"
if [ "$1" = "rete" ]; then
  [ -z "$2" ] && { echo "Indica l'IP della rete privata/Tailscale: bash Avvia_Linux.sh rete 100.x.y.z"; exit 1; }
  [ -z "$ANALISI_PIN" ] && { printf "PIN (min 6 caratteri): "; read -r -s ANALISI_PIN; echo; }
  [ "${#ANALISI_PIN}" -lt 6 ] && { echo "PIN troppo corto"; exit 1; }
  export ANALISI_PIN; echo "In rete: http://$2:8765 (PIN). Stop: Ctrl+C o bash Arresta_Linux.sh"; exec "$PY" interfaccia_locale.py --radice "$RADICE" --host "$2"
fi
echo "Apri http://127.0.0.1:8765  (stop: Ctrl+C o bash Arresta_Linux.sh)"; exec "$PY" interfaccia_locale.py --radice "$RADICE"
