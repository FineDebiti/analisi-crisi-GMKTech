#!/usr/bin/env python3
"""Prepara la pratica DEMO con le STESSE funzioni usate dall'interfaccia (nessuna modifica manuale ai JSON) e scrive la verita' di riferimento.
  python3 ab/prepara_demo.py --radice /percorso/CASI_PROVA
Crea <radice>/DEMO con i 3 PDF fittizi, i dati verificati dal titolare (illustrativi), gli stati documentali, la preanalisi del motore e ab/DEMO_verita.json
(se non esiste). Non e' una pratica reale: i valori di liquidita' utilizzabile e debiti bancari/pubblici sono inventati per la prova A."""
import argparse
import json
import shutil
import sys
from pathlib import Path

QUI = Path(__file__).resolve().parent
sys.path.insert(0, str(QUI.parent))
from analisi_crisi import checklist as ck  # noqa: E402
from analisi_crisi import dati_pratica as dp  # noqa: E402
from analisi_crisi import pratica as pr  # noqa: E402
from analisi_crisi import ui_pratica as ui  # noqa: E402

OP = "Operatore DEMO"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--radice", required=True)
    a = ap.parse_args()
    radice = Path(a.radice)
    radice.mkdir(parents=True, exist_ok=True)
    cart_nome, _ = dp.crea_pratica(radice, "DEMO", "CNC", OP)
    cart = radice / cart_nome
    pc = cart / "PRATICA"
    files = [(f.name, f.read_bytes()) for f in sorted((QUI.parent / "DEMO_PDF").glob("*.pdf"))]
    print(ui._carica(cart, pc, files))
    # dati inseriti e VERIFICATI dal titolare (illustrativi): stato FATTO con fonte
    reg = {r["nome"]: r["id"] for r in pr._leggi(pc, "registro", [])}
    b = str(reg["bilancio_demo.pdf"])
    dp.salva_valori(pc, {"liquidita_utilizzabile": {"valore": "20000", "id_documento": b, "pagina": "1", "stato": "FATTO", "note": "Quota libera da vincoli (illustrativa)"},
                         "debiti_bancari": {"valore": "215000", "id_documento": b, "pagina": "2", "stato": "FATTO", "note": "Illustrativo"},
                         "debiti_pubblici": {"valore": "110000", "id_documento": str(reg["altro_demo.pdf"]), "pagina": "1", "stato": "FATTO", "note": "Illustrativo"}}, OP)
    # i dati letti dal parser sono confermati dal titolare (stato FATTO gia' impostato dal parser)
    with dp.modifica(pc, "stati documentali"):
        for vid in ("B4", "B9"):
            pr.imposta_stato_voce(pc, vid, "inesistente", OP)
    d = dp.avvia_preanalisi(pc, OP)
    verita = {
        "descrizione": "Verita' di riferimento DEMO. 'dati' = valori presenti nei PDF (prova B). 'mancanti' = non presenti nei PDF: devono restare non disponibili. 'scenari_motore' = stato calcolato dal motore deterministico (riferimento, non verita' sul mondo).",
        "dati": [
            {"campo": "ricavi", "valore": 1250000, "documento": int(b), "pagina": 3, "periodo": "2025"},
            {"campo": "valore_produzione", "valore": 1274500, "documento": int(b), "pagina": 3, "periodo": "2025"},
            {"campo": "costi_produzione", "valore": 1169000, "documento": int(b), "pagina": 3, "periodo": "2025"},
            {"campo": "ammortamenti", "valore": 40500, "documento": int(b), "pagina": 3, "periodo": "2025"},
            {"campo": "ricavi_prec", "valore": 1120000, "documento": int(b), "pagina": 3, "periodo": "2024"},
            {"campo": "totale_attivo", "valore": 806500, "documento": int(b), "pagina": 1, "periodo": "2025"},
            {"campo": "patrimonio_netto", "valore": 206300, "documento": int(b), "pagina": 2, "periodo": "2025"},
            {"campo": "debiti_totali", "valore": 497000, "documento": int(b), "pagina": 2, "periodo": "2025"},
            {"campo": "disponibilita_liquide", "valore": 61300, "documento": int(b), "pagina": 1, "periodo": "2025"}],
        "mancanti": ["debiti_bancari", "debiti_pubblici", "crediti_soci", "liquidita_utilizzabile"],
        "incongruenze_attese": [{"descrizione": "Roll-forward del patrimonio netto 2024->2025: le riserve crescono di 10.400 (legale +4.000, altre +6.400) a fronte di un utile 2024 di 7.900; differenza di 2.500 non spiegata dai documenti", "origine": "individuata durante la verifica della DEMO; non intenzionale nei dati sintetici; verosimilmente MINORE"}],
        "nota_incongruenze": "Per il resto la DEMO e' coerente (attivo = passivo, A-B = 105.500, somme delle parti). Ogni altra incongruenza proposta e' un possibile falso positivo da giudicare. L'utile 59.900 compare in due prospetti ed e' coerente.",
        "scenari_motore": {x["scenario"]: x["stato"] for x in d["scenari"]},
        "richieste_utili": {"tesoreria": ["tesoreria", "flussi di cassa", "scadenzario"], "elenco creditori": ["creditori"], "estratto di ruolo": ["ruolo", "riscossione"], "centrale rischi": ["centrale", "rischi"]},
    }
    dest = QUI / "DEMO_verita.json"
    if dest.exists():
        print("DEMO_verita.json esiste gia' (non sovrascritto)")
    else:
        dest.write_text(json.dumps(verita, ensure_ascii=False, indent=1), encoding="utf-8")
        print("Scritto", dest)
    print("Scenari del motore:", json.dumps(verita["scenari_motore"], ensure_ascii=False))
    print("DEMO pronta in", cart)


if __name__ == "__main__":
    main()
