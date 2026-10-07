"""Test del parser degli estratti di ruolo e del collegamento al modello Aziende (solo file fittizi)."""
import json
import shutil
import sys
import tempfile
from pathlib import Path

QUI = Path(__file__).resolve().parent
sys.path.insert(0, str(QUI.parent))
sys.path.insert(0, str(QUI))

import compila_excel  # noqa: E402
import estrai_ruoli  # noqa: E402
import genera_ruoli_fittizio as gen  # noqa: E402
from analisi_crisi import modello_aziende, parser_ruoli  # noqa: E402

MODELLO = QUI.parent / "modelli" / "Modello_Aziende_Valutazione_Crisi_Template.xlsx"


def _pdf(tmp):
    pdf = Path(tmp) / "ruolo_fittizio.pdf"
    gen.genera(pdf)
    return pdf


def test_parser():
    with tempfile.TemporaryDirectory() as tmp:
        r = parser_ruoli.analizza(_pdf(tmp))
    assert len(r["documenti"]) == 3 and len(r["gruppi"]) == 1
    assert [d["tipo_documento"] for d in r["documenti"]] == ["cartella", "avviso_di_addebito", "cartella"]
    assert all(c["esito"] == "OK" for c in r["controlli"]), r["controlli"]
    assert parser_ruoli.riepilogo(r) == {"erariale": 1185, "previdenziale": 535.5, "enti_locali": 320}
    assert sum(d["totali"]["totale_documento"] for d in r["documenti"]) == r["gruppi"][0]["totale_debito"]


def test_controllo_ko():
    with tempfile.TemporaryDirectory() as tmp:
        r = parser_ruoli.analizza(_pdf(tmp))
        r["gruppi"][0]["totale_debito"] += 1
        assert r["gruppi"][0]["totale_debito"] != sum(d["totali"]["totale_documento"] for d in r["documenti"])


def test_celle_e_scrittura():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        r = parser_ruoli.analizza(_pdf(tmp))
        r["modello_aziende"] = modello_aziende.celle_ruoli(r, {"valore": 10000, "stato": "FATTO"})
        f_json = tmp / "ruoli.json"
        f_json.write_text(json.dumps(r), encoding="utf-8")
        excel = tmp / "Az.xlsx"
        shutil.copy(MODELLO, excel)
        compila_excel.PROGETTO = tmp
        esito = compila_excel.compila(f_json, excel, scrivere=True, modello="aziende")
        assert esito["superato"], esito["testo"]
        scritte = {v["cella"] for v in esito["voci"] if v["azione"] == "SCRITTA"}
        assert {"passivo_creditori!B17", "passivo_creditori!C17", "passivo_creditori!F17", "passivo_creditori!F20", "allerta_ccii!C22"} <= scritte
        # Classe in via generale: INFERENZA, scritta; classe dell'aggio: DA VERIFICARE, non scritta senza approvazione.
        assert any(v["cella"] == "passivo_creditori!B20" and v["azione"].startswith("NON SCRITTA") for v in esito["voci"])
        # Seconda scrittura sulla copia: non si sovrascrive nulla.
        copia = esito["copia"]
        esito2 = compila_excel.compila(f_json, copia, scrivere=True, modello="aziende")
        assert not any(v["azione"] == "SCRITTA" for v in esito2["voci"])
        assert any(v["azione"].startswith("RIFIUTATA: la cella contiene già") for v in esito2["voci"])
        assert "AMMINISTRAZIONE" not in esito["testo"] and "FANTASIA" not in esito["testo"]


def test_diagnostica_senza_valori():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        estrai_ruoli.PROGETTO = tmp
        d, j = estrai_ruoli.estrai(_pdf(tmp))
        testo = d.read_text(encoding="utf-8")
        assert "Documenti riconosciuti: 3" in testo
        for proibito in ("1185", "1.185", "FANTASIA", "INPS TEST", "0972020"):
            assert proibito not in testo


def prova():
    for nome, f in sorted(globals().items()):
        if nome.startswith("test_"):
            f()
            print("OK", nome)


if __name__ == "__main__":
    prova()
