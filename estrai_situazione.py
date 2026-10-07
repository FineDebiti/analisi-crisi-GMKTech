"""Estrae una situazione contabile / bilancio provvisorio in JSON (con valori, in `_estratti/`) + diagnostica senza valori.

Uso:  $HOME/vm_venv/bin/python estrai_situazione.py percorso/file.pdf [C|D]     (colonna del modello: D = Anno-1, predefinita)
"""
import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

from analisi_crisi import modello_aziende, parser_situazione
from analisi_crisi.diagnostica import verifica_senza_valori

PROGETTO = Path(__file__).resolve().parent


def estrai(pdf, colonna="D"):
    pdf = Path(pdf).resolve()
    r = parser_situazione.analizza(pdf)
    r["modello_aziende"] = modello_aziende.celle_situazione(r, colonna) if r["mastri"] else []
    cartella = pdf.parent / "_estratti"
    cartella.mkdir(exist_ok=True)
    f_json = cartella / f"{pdf.stem}_situazione.json"
    f_json.write_text(json.dumps(r, ensure_ascii=False, indent=2), encoding="utf-8")
    celle = [c for x in r["modello_aziende"] for c in x["celle"].values()]
    righe = ["# Rapporto di diagnostica - situazione contabile (senza valori)", "", f"- Esito: {r['esito']}",
             f"- Sezioni lette: {sorted(r['date'])}", f"- Mastri riconosciuti: {len(r['mastri'])}; non mappati nel modello: {r['non_mappati']}",
             f"- Celle del modello Aziende: {len(celle)} ({dict(Counter(c['stato'] for c in celle))})", "", "## Controlli aritmetici", ""]
    righe += [f"- {c['nome']}: {c['esito']}" for c in r["controlli"]] + ["", "## Avvisi", ""] + [f"- {a}" for a in r["avvisi"]]
    testo = "\n".join(righe) + "\n"
    verifica_senza_valori(testo, {"modello_aziende": r["modello_aziende"], "controlli": r["controlli"]})
    cartella_d = PROGETTO / "diagnostica"
    cartella_d.mkdir(exist_ok=True)
    f_diag = cartella_d / f"situazione_{datetime.now():%Y%m%d-%H%M%S}.md"
    f_diag.write_text(testo, encoding="utf-8")
    return f_diag, f_json


if __name__ == "__main__":
    if len(sys.argv) not in (2, 3):
        print(__doc__)
        sys.exit(2)
    print("Diagnostica senza valori:", estrai(sys.argv[1], sys.argv[2] if len(sys.argv) == 3 else "D")[0])
