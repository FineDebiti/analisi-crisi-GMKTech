"""Unisce più estrazioni (bilancio, estratti di ruolo, ...) in un solo file per compilare UNA copia del modello Aziende.

Uso:  python assembla_caso.py uscita_caso.json estrazione1.json estrazione2.json ...
Le righe del modello Aziende sono concatenate; se due estrazioni scrivono la stessa cella vince la prima e si segnala.
Il file di uscita contiene valori: va tenuto nella cartella riservata, mai in diagnostica/.
"""
import json
import sys
from pathlib import Path


def assembla(uscita, ingressi):
    unito = {"schema": "caso/1", "documento": {"tipo": "caso", "fonti": [Path(i).name for i in ingressi]},
             "modello_aziende": [], "dati": [], "residui": [], "controllo": [], "controlli": [], "documenti": [],
             "foglio": [], "righe_non_mappate": [], "avvisi": []}
    viste, doppie = set(), []
    for f in ingressi:
        r = json.loads(Path(f).read_text(encoding="utf-8"))
        for riga in r.get("modello_aziende", []):
            for col in list(riga["celle"]):
                chiave = (riga["foglio"], riga["riga"], col)
                if chiave in viste:
                    doppie.append(chiave)
                    del riga["celle"][col]
                else:
                    viste.add(chiave)
            if riga["celle"]:
                unito["modello_aziende"].append(riga)
        for k in ("dati", "residui", "controllo", "controlli", "documenti", "avvisi"):
            unito[k] += r.get(k, [])
    unito["celle_doppie"] = [list(d) for d in doppie]
    Path(uscita).write_text(json.dumps(unito, ensure_ascii=False, indent=2), encoding="utf-8")
    return len(unito["modello_aziende"]), len(doppie)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(2)
    n, d = assembla(sys.argv[1], sys.argv[2:])
    print(f"Righe del modello: {n}; celle duplicate scartate: {d}")
