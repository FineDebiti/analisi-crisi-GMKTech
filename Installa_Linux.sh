#!/bin/bash
# Installa ANALISI CRISI (copia GMKtec) su Linux o WSL: .venv LOCALE, dipendenze, prove automatiche. Rilanciabile. Non installa modelli e non tocca le pratiche.
cd "$(dirname "$0")" || exit 1
chmod +x ./*.sh 2>/dev/null
echo "=== ANALISI CRISI (GMKtec) - installazione ==="
PYS=""
for c in python3.14 python3.13 python3.12 python3.11 python3.10 python3; do
  P="$(command -v "$c" 2>/dev/null)"; [ -n "$P" ] && "$P" -c 'import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)' 2>/dev/null && { PYS="$P"; break; }
done
[ -z "$PYS" ] && { echo "ERRORE: serve Python 3.10 o superiore (Ubuntu/Debian: sudo apt install python3 python3-venv)."; exit 1; }
echo "Python: $PYS ($("$PYS" --version 2>&1))"
if [ -x .venv/bin/python ] && .venv/bin/python -c 'import reportlab, pdfplumber, PIL' 2>/dev/null; then echo "Ambiente .venv già funzionante."
else
  echo "Creo l'ambiente locale .venv..."; rm -rf .venv
  "$PYS" -m venv .venv || { echo "ERRORE: venv non disponibile (Ubuntu/Debian: sudo apt install python3-venv)."; exit 1; }
  .venv/bin/python -m pip install --quiet --upgrade pip && .venv/bin/python -m pip install --quiet -r requirements.txt || { echo "ERRORE: installazione dipendenze (internet attivo? proxy?)."; exit 1; }
fi
.venv/bin/python -c 'import reportlab, pdfplumber, PIL; print("Dipendenze: reportlab", reportlab.Version, "- pdfplumber", pdfplumber.__version__, "- pillow", PIL.__version__)' || exit 1
KO=0
for t in test_pratica test_correzioni_rev3 test_percorso_interfaccia test_llm_locale; do
  if .venv/bin/python "test_sintetici/$t.py" >"/tmp/analisi_crisi_$t.log" 2>&1; then echo "Prova $t: OK"; else echo "Prova $t: FALLITA (vedi /tmp/analisi_crisi_$t.log)"; KO=1; fi
done
echo "--- OCR locale (facoltativo, per PDF scansionati):"
for c in tesseract pdftoppm; do command -v $c >/dev/null && echo "  $c: ok" || echo "  $c: MANCANTE (Ubuntu/Debian: sudo apt install tesseract-ocr tesseract-ocr-ita poppler-utils)"; done
mkdir -p "$HOME/Riservato_AnalisiCrisi/CASI" && chmod 700 "$HOME/Riservato_AnalisiCrisi" "$HOME/Riservato_AnalisiCrisi/CASI"
[ "$KO" = 0 ] && echo "=== INSTALLAZIONE COMPLETATA. Poi: bash verifica_ambiente.sh, configura llm_config.json, bash Avvia_Linux.sh ===" || { echo "=== INSTALLAZIONE CON ERRORI: non usare l'app; manda i log a Claude ==="; exit 1; }
