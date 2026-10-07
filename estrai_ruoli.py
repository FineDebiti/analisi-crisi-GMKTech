"""Estrae un estratto di ruolo (nativo o scansione) in JSON + rapporto di diagnostica senza valori.

Uso:  $HOME/vm_venv/bin/python estrai_ruoli.py percorso/file.pdf [--bilancio estratti/bilancio.json]
- JSON (con valori) in `_estratti/` accanto al PDF. A video e in `diagnostica/` solo conteggi ed esiti.
"""
import json
import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

import pdfplumber

from analisi_crisi import modello_aziende, ocr_ruoli, parser_ruoli

PROGETTO = Path(__file__).resolve().parent


def _attivo(f_bilancio):
    """Totale attivo dell'ultimo esercizio da un JSON di bilancio (anno -1), oppure None."""
    b = json.loads(Path(f_bilancio).read_text(encoding='utf-8'))
    for d in b.get('dati', []) + b.get('controllo', []):
        if d['chiave'] == 'sp.tot_attivo' and d.get('anno') == -1 and d['valore']:
            return {'valore': d['valore'], 'stato': d['stato']}
    return None


def estrai(pdf, f_bilancio=None):
    pdf = Path(pdf).resolve()
    r = parser_ruoli.analizza(pdf)
    if r["esito"].startswith("FERMATO: SCANSIONE") or not r["documenti"]:
        r = ocr_ruoli.analizza(pdf)
    r["modello_aziende"] = modello_aziende.celle_ruoli(r, _attivo(f_bilancio) if f_bilancio else None)
    cartella = pdf.parent / "_estratti"
    cartella.mkdir(exist_ok=True)
    f_json = cartella / f"{pdf.stem}_ruoli.json"
    f_json.write_text(json.dumps(r, ensure_ascii=False, indent=2), encoding="utf-8")
    docs = r["documenti"]
    righe = [
        "# Rapporto di diagnostica - estratto di ruolo (senza valori)", "",
        f"- Lettura: {r['documento'].get('lettura', 'testo nativo')}", f"- Esito: {r['esito']}",
        f"- Documenti riconosciuti: {len(docs)}", f"- Gruppi con totale debito: {len(r['gruppi'])}",
        f"- Per tipo: {dict(Counter(d.get('tipo_documento') for d in docs))}",
        f"- Per classe di ente: {dict(Counter(d.get('classe') or ','.join(sorted({e['classe'] for e in d.get('enti', [])})) for d in docs))}",
        f"- Stati: {dict(Counter(d['stato'] for d in docs))}", "", "## Controlli aritmetici", "",
    ]
    for (nome, esito), n in sorted(Counter((c["nome"], c["esito"]) for c in r["controlli"]).items()):
        righe.append(f"- {nome}: {esito} (x{n})")
    righe += ["", "## Avvisi", ""] + [f"- {a}" for a in r["avvisi"]]
    cartella_d = PROGETTO / "diagnostica"
    cartella_d.mkdir(exist_ok=True)
    f_diag = cartella_d / f"ruoli_{datetime.now():%Y%m%d-%H%M%S}.md"
    f_diag.write_text("\n".join(righe) + "\n", encoding="utf-8")
    return f_diag, f_json


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    bil = sys.argv[sys.argv.index("--bilancio") + 1] if "--bilancio" in sys.argv else None
    if bil in args:
        args.remove(bil)
    if len(args) != 1:
        print(__doc__)
        sys.exit(2)
    d, j = estrai(args[0], bil)
    print("Diagnostica senza valori:", d)
