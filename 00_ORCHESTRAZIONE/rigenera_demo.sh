#!/bin/bash
# Rigenera la DEMO v3.1 (json, csv, tabella dati ideali, relazione) senza toccare le versioni precedenti.
set -e
RAD="$HOME/mnt/ANALISI CRISI"; D="$RAD/DEMO"; PY="$HOME/vm_venv/bin/python"; T=$(mktemp -d)
(cd "$D" && DEMO_TMP="$T" $PY costruisci_caso_demo.py)
(cd "$RAD" && $PY relazione_v3.py --caso "$D/caso_v3_DEMO.json" --out "$T/Relazione_DEMO_preanalisi_v3.1.docx")
(cd "$T" && timeout 150 soffice --headless --convert-to pdf Relazione_DEMO_preanalisi_v3.1.docx Tabella_DEMO_dati_ideali_v3.1.docx >/dev/null 2>&1)
cp "$T"/*.docx "$T"/*.pdf "$D"/
