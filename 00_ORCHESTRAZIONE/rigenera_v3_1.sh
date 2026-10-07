#!/bin/bash
# Rigenera le relazioni v3.1 (la v3 resta conservata) (riservata + anonimizzata + PDF) per i casi indicati, sovrascrivendo i file esistenti.
# Uso: rigenera_v3.sh Eurocasa Mercurio     (esegue il costruttore del caso, poi la relazione)
set -e
RAD="$HOME/mnt/ANALISI CRISI"; ROOT="$HOME/mnt/DATI_REALI_LOCALI/NUOVI_CASI"; PY="$HOME/vm_venv/bin/python"; T=$(mktemp -d)
for c in "$@"; do
  D="$ROOT/$c/CASO"
  (cd "$D" && $PY costruisci_caso_v3.py >/dev/null)
  (cd "$RAD" && $PY relazione_v3.py --caso "$D/caso_v3.json" --out "$T/Relazione_${c}_preanalisi_v3.1.docx" \
   && $PY relazione_v3.py --caso "$D/caso_v3.json" --out "$T/Relazione_${c}_v3.1_ANONIMIZZATA.docx" --anonimizza --legenda "$T/legenda.json")
  (cd "$T" && timeout 150 soffice --headless --convert-to pdf Relazione_${c}_preanalisi_v3.1.docx Relazione_${c}_v3.1_ANONIMIZZATA.docx >/dev/null 2>&1)
  cp "$T"/Relazione_${c}_*.docx "$T"/Relazione_${c}_*.pdf "$D"/ && cp "$T/legenda.json" "$D/Relazione_${c}_v3.1_ANONIMIZZATA_legenda.json"
  rm -f "$T"/*
done
