"""Estrae un documento contabile da un PDF: bilancio depositato (parser a) o dichiarazione dei redditi (parser c).

Uso:  .venv/bin/python estrai.py percorso/del/file.pdf [bilancio|dichiarazione]

- JSON, tabella di revisione e foglio_incolla.csv (contengono i valori) vanno in `_estratti/` accanto al PDF.
- Il rapporto di diagnostica e il CSV senza valori vanno in `diagnostica/` nella cartella del progetto.
- A video non viene stampato alcun valore. L'xlsm non viene mai aperto né scritto.
"""
import json
import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

import pdfplumber

from analisi_crisi import parser_bilancio, parser_dichiarazione
from analisi_crisi.diagnostica import rapporto, verifica_senza_valori
from analisi_crisi.foglio import csv_incolla, csv_senza_valori
from analisi_crisi.revisione import html_revisione

PROGETTO = Path(__file__).resolve().parent
SINTETICI = PROGETTO / "test_sintetici"
PARSER = {"bilancio": parser_bilancio, "dichiarazione": parser_dichiarazione}


def riconosci_tipo(pdf) -> str:
    """Tipo di documento dal testo. Una scansione va al parser del bilancio, che si ferma e la segnala."""
    with pdfplumber.open(pdf) as doc:
        testo = " ".join((p.extract_text() or "") for p in doc.pages).lower()
    if re.search(r"periodo d'imposta|quadro (re|rg|lm)\b|modello redditi", testo.replace("’", "'")):
        return "dichiarazione"
    if "conto economico" in testo or not testo.strip():
        return "bilancio"
    raise SystemExit("Tipo di documento non riconosciuto: indicarlo dopo il percorso (bilancio oppure dichiarazione).")


def estrai(pdf, tipo=None) -> dict:
    """Esegue il parser e scrive i file. Restituisce i percorsi e il conteggio degli stati."""
    pdf = Path(pdf).resolve()
    tipo = tipo or riconosci_tipo(pdf)
    r = PARSER[tipo].analizza(pdf)

    estratti = pdf.parent / "_estratti"
    estratti.mkdir(exist_ok=True)
    f_json = estratti / f"{pdf.stem}.json"
    f_html = estratti / f"{pdf.stem}_revisione.html"
    f_csv = estratti / f"{pdf.stem}_foglio_incolla.csv"
    f_json.write_text(json.dumps(r, ensure_ascii=False, indent=2), encoding="utf-8")
    f_html.write_text(html_revisione(r), encoding="utf-8")
    f_csv.write_text(csv_incolla(r), encoding="utf-8-sig")  # con BOM: Excel legge bene gli accenti

    # Il nome del file compare nel rapporto solo per i PDF sintetici: quello reale può contenere un nome.
    nome = pdf.name if pdf.is_relative_to(SINTETICI) else None
    testo = rapporto(r, nome)
    foglio = csv_senza_valori(r)
    verifica_senza_valori(foglio, r)
    cartella = PROGETTO / "diagnostica"
    cartella.mkdir(exist_ok=True)
    base = "diagnostica_" + datetime.now().strftime("%Y%m%d-%H%M%S")
    f_diag, n = cartella / f"{base}.md", 1
    while f_diag.exists():
        n += 1
        f_diag = cartella / f"{base}_{n}.md"
    f_diag.write_text(testo, encoding="utf-8")
    f_diag.with_name(f_diag.stem + "_foglio.csv").write_text(foglio, encoding="utf-8-sig")

    stati = Counter(c["stato"] for riga in r["foglio"] for c in riga["celle"].values())
    return {"tipo": tipo, "esito": r["esito"], "stati": dict(stati), "json": f_json, "html": f_html, "csv": f_csv, "diagnostica": f_diag}


def main(argv):
    if len(argv) not in (2, 3) or (len(argv) == 3 and argv[2] not in PARSER):
        print(__doc__)
        return 2
    esito = estrai(argv[1], argv[2] if len(argv) == 3 else None)
    print("Tipo:", esito["tipo"], "- Esito:", esito["esito"])
    print("Celle:", ", ".join(f"{k} = {v}" for k, v in sorted(esito["stati"].items())) or "nessuna")
    print("JSON, revisione e foglio_incolla.csv in:", esito["json"].parent)
    print("Diagnostica senza valori:", esito["diagnostica"])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
