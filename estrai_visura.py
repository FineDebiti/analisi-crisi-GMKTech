"""Estrae una visura camerale in JSON (con valori, in `_estratti/`) e rapporto di diagnostica senza valori.

Uso:  $HOME/vm_venv/bin/python estrai_visura.py percorso/visura.pdf [--conferma denominazione,forma_giuridica]
"""
import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

from analisi_crisi import modello_aziende, parser_visura
from analisi_crisi.diagnostica import verifica_senza_valori

PROGETTO = Path(__file__).resolve().parent


def estrai(pdf, conferme=()):
    pdf = Path(pdf).resolve()
    r = parser_visura.analizza(pdf)
    for k in conferme:  # voci confermate dall'avvocato: restano tracciate come tali
        if k in r["campi"]:
            r["campi"][k]["stato"] = "FATTO"
            r["campi"][k]["note"].append("Confermato dall'avvocato (trasformazione da S.r.l. a S.n.c. per erosione del capitale).")
    r["modello_aziende"] = modello_aziende.celle_anagrafica(r)
    cartella = pdf.parent / "_estratti"
    cartella.mkdir(exist_ok=True)
    f_json = cartella / f"{pdf.stem}_visura.json"
    f_json.write_text(json.dumps(r, ensure_ascii=False, indent=2), encoding="utf-8")
    righe = ["# Rapporto di diagnostica - visura camerale (senza valori)", "", f"- Esito: {r['esito']}",
             f"- Campi riconosciuti: {sorted(r['campi'])}", f"- Stati: {dict(Counter(c['stato'] for c in r['campi'].values()))}",
             f"- Eventi del Registro riconosciuti: {len(r['eventi'])} (tipi distinti: {len({e['evento'] for e in r['eventi']})})",
             f"- Celle del modello Aziende: {sum(len(x['celle']) for x in r['modello_aziende'])}", "", "## Avvisi", ""]
    righe += [f"- {a}" for a in r["avvisi"]] or ["- nessuno"]
    testo = "\n".join(righe) + "\n"
    verifica_senza_valori(testo, {"modello_aziende": r["modello_aziende"], "documenti": [
        {"numero": c["valore"], "stato": c["stato"]} for c in r["campi"].values()]})
    cartella_d = PROGETTO / "diagnostica"
    cartella_d.mkdir(exist_ok=True)
    f_diag = cartella_d / f"visura_{datetime.now():%Y%m%d-%H%M%S}.md"
    f_diag.write_text(testo, encoding="utf-8")
    return f_diag, f_json


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    conferme = tuple(sys.argv[sys.argv.index("--conferma") + 1].split(",")) if "--conferma" in sys.argv else ()
    if "--conferma" in sys.argv:
        args = [a for a in args if a not in conferme and a != ",".join(conferme)]
    if len(args) != 1:
        print(__doc__)
        sys.exit(2)
    print("Diagnostica senza valori:", estrai(args[0], conferme)[0])
