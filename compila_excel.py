"""Riporta in Excel i dati di un'estrazione (opzione B). Scrive solo su una copia, mai sull'originale.

Uso:  .venv/bin/python compila_excel.py estrazione.json cartella.xlsm            (dry-run: non apre l'Excel)
      .venv/bin/python compila_excel.py estrazione.json cartella.xlsm --scrivi   (scrive <nome>_COMPILATO.xlsm)
      aggiungendo  --modello aziende  si usa il modello Aziende (xlsx) invece del modello Traietti.
      aggiungendo  --approvazioni <file>_approvazioni.json  si scrivono anche le celle DA VERIFICARE approvate in revisione.

A video e nel log (in `diagnostica/`) non compare alcun valore.
"""
import json
import sys
from datetime import datetime
from pathlib import Path

from analisi_crisi.comune import FOGLIO
from analisi_crisi.diagnostica import verifica_senza_valori
from analisi_crisi.excel_scrittura import percorso_copia, piano, scrivi, testo_piano
from analisi_crisi.excel_verifica import confronta, impronta, superato

PROGETTO = Path(__file__).resolve().parent
SCARTO = "_DA_SCARTARE"


def _approvate(f_appr, r):
    if not f_appr:
        return frozenset()
    a = json.loads(Path(f_appr).read_text(encoding="utf-8"))
    if a.get("documento") != r["documento"]["file"]:
        raise ValueError("le approvazioni si riferiscono a un altro documento")
    return frozenset(a.get("approvate", []))


def compila(f_json, f_excel, scrivere=False, f_approvazioni=None, modello="traietti") -> dict:
    r = json.loads(Path(f_json).read_text(encoding="utf-8"))
    f_excel = Path(f_excel).resolve()
    voci = piano(r, _approvate(f_approvazioni, r), modello)
    righe = ["# Scrittura in Excel (senza valori)", "", f"- Tipo di documento: {r['documento']['tipo']}",
             f"- Foglio: {FOGLIO if modello == 'traietti' else 'bilancio_ce, bilancio_sp (modello aziende)'}", f"- Modalità: {'SCRITTURA su copia' if scrivere else 'DRY-RUN (nulla è stato scritto)'}", ""]
    esito = {"scritte": 0, "superato": None, "copia": None}
    if scrivere:
        copia = percorso_copia(f_excel)
        prima = impronta(f_excel)
        scritte = scrivi(voci, f_excel, copia)
        controlli = confronta(f_excel, copia, FOGLIO, scritte)
        controlli.append({"controllo": "Originale intatto (stesso hash prima e dopo)",
                          "esito": "OK" if impronta(f_excel) == prima else "KO", "dettaglio": ""})
        esito.update(scritte=len(scritte), superato=superato(controlli), copia=copia)
        if not esito["superato"]:
            # La copia non valida cambia nome, così non viene usata per errore.
            esito["copia"] = copia.replace(copia.with_name(copia.stem + SCARTO + copia.suffix))
        righe += ["## Controlli dopo la scrittura", "", "| Controllo | Esito | Dettaglio |", "|---|---|---|"]
        righe += [f"| {c['controllo']} | {c['esito']} | {c['dettaglio']} |" for c in controlli]
        righe += ["", f"**Esito: {'copia valida' if esito['superato'] else 'COPIA DA SCARTARE, non usarla'}**", ""]
    righe += ["## Celle", "", testo_piano(voci)]
    testo = "\n".join(righe)
    verifica_senza_valori(testo, r)
    cartella = PROGETTO / "diagnostica"
    cartella.mkdir(exist_ok=True)
    base = "scrittura_" + datetime.now().strftime("%Y%m%d-%H%M%S")
    log, n = cartella / f"{base}.md", 1
    while log.exists():
        n += 1
        log = cartella / f"{base}_{n}.md"
    log.write_text(testo, encoding="utf-8")
    esito.update(voci=voci, log=log, testo=testo)
    return esito


def main(argv):
    args = [a for a in argv[1:] if a != "--scrivi"]
    appr, modello = None, "traietti"
    if "--modello" in args:
        i = args.index("--modello")
        modello = args[i + 1] if i + 1 < len(args) else modello
        del args[i:i + 2]
    if "--approvazioni" in args:
        i = args.index("--approvazioni")
        appr = args[i + 1] if i + 1 < len(args) else None
        del args[i:i + 2]
    if len(args) != 2:
        print(__doc__)
        return 2
    esito = compila(args[0], args[1], scrivere="--scrivi" in argv, f_approvazioni=appr, modello=modello)
    print(esito["testo"])
    print("Log senza valori:", esito["log"])
    if esito["copia"]:
        print("Copia:", esito["copia"].name)
    return 0 if esito["superato"] in (None, True) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
