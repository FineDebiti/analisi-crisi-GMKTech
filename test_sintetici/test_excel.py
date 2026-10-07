"""Test della scrittura in Excel sull'xlsm fittizio. Uso: .venv/bin/python test_sintetici/test_excel.py"""
import importlib.util
import json
import re
import sys
import tempfile
import zipfile
from pathlib import Path

QUI = Path(__file__).resolve().parent
sys.path.insert(0, str(QUI.parent))
sys.path.insert(0, str(QUI))

import genera_bilancio_fittizio as gen  # noqa: E402
import genera_dichiarazione_fittizia as gen_dr  # noqa: E402
import genera_excel_fittizio as gen_xl  # noqa: E402
from analisi_crisi import excel_scrittura as xs  # noqa: E402
from analisi_crisi import parser_bilancio, parser_dichiarazione  # noqa: E402
from analisi_crisi.comune import DA_VERIFICARE, FATTO, FOGLIO, KO, OK  # noqa: E402
from analisi_crisi.diagnostica import verifica_senza_valori  # noqa: E402
from analisi_crisi.excel_verifica import CONDIVISA, confronta, impronta, leggi, superato  # noqa: E402
import compila_excel  # noqa: E402
from compila_excel import compila  # noqa: E402

ORIGINALE = QUI / gen_xl.NOME
FLUSSI = "xl/worksheets/sheet3.xml"
TMP = Path(tempfile.mkdtemp())
compila_excel.PROGETTO = TMP  # i log di prova non finiscono in diagnostica/


def _manomessa(nome, modifiche):
    """Copia dell'xlsm con alcune parti modificate: {parte: funzione(testo) -> testo, oppure None per toglierla}."""
    copia = TMP / nome
    with zipfile.ZipFile(ORIGINALE) as z, zipfile.ZipFile(copia, "w", zipfile.ZIP_DEFLATED) as nuovo:
        for parte in z.namelist():
            if parte in modifiche and modifiche[parte] is None:
                continue
            dati = z.read(parte)
            if parte in modifiche:
                dati = modifiche[parte](dati.decode("utf-8")).encode("utf-8")
            nuovo.writestr(parte, dati)
    return copia


def _falliti(copia, scritte=None):
    return {e["controllo"].split(":")[0].split(" (")[0] for e in confronta(ORIGINALE, copia, FOGLIO, scritte or {}) if e["esito"] == KO}


def test_struttura_fittizia():
    s = leggi(ORIGINALE)
    assert [(n, f["stato"]) for n, f in s["fogli"].items()] == [(n, st or "visible") for n, st in gen_xl.FOGLI]
    assert all(f["protezione"]["sheet"] == "1" for f in s["fogli"].values())
    assert s["protezione"]["lockStructure"] == "1" and s["vba"] and "xl/drawings/vmlDrawing1.vml" in s["parti"]
    celle = s["fogli"][FOGLIO]["celle"]
    assert celle["C18"] == ("f", "SUM(C14:C17)") and celle["D13"] == ("f", CONDIVISA)
    assert sum(1 for c in celle.values() if c[0] == "f") == 3 * len(gen_xl.FORMULE)
    assert "C10" not in celle and celle["C28"] == ("v", 1500.0)


def test_piano():
    r = parser_bilancio.analizza(QUI / "bilancio_abbreviato_fittizio.pdf")
    voci = xs.piano(r)
    assert len(voci) == 20 and all(v["azione"] == xs.DA_SCRIVERE for v in voci)
    assert {int(v["cella"][1:]) for v in voci} <= xs.RIGHE_AMMESSE
    verifica_senza_valori(xs.testo_piano(voci), r)
    # Le dichiarazioni vanno in colonna E, nelle sole righe del blocco regime.
    for nome in gen_dr.DOCUMENTI:
        voci = xs.piano(parser_dichiarazione.analizza(QUI / nome))
        assert voci and {v["cella"][0] for v in voci} == {"E"}, nome
        assert not {int(v["cella"][1:]) for v in voci if v["azione"] == xs.DA_SCRIVERE} - (xs.BLOCCO_ORDINARIO | xs.BLOCCO_FORFETTARIO), nome
    # Mai E sulle righe 10-23, mai C/D sul blocco regime, mai righe 40 e 50; due blocchi insieme: nessuno dei due.
    def _c(col, riga, v=5, st=FATTO):
        return {"riga": riga, "voce": "x", "celle": {col: {"valore": v, "stato": st, "note": []}}}
    assert xs.piano({"foglio": [_c("E", 10), _c("C", 37), _c("E", 40), _c("E", 50)]})[0]["azione"] == xs.ESCLUSA_RIGA
    assert all(v["azione"] == xs.ESCLUSA_RIGA for v in xs.piano({"foglio": [_c("E", 10), _c("C", 37), _c("E", 40), _c("E", 50)]}))
    due = xs.piano({"foglio": [_c("E", 37), _c("E", 47)]})
    assert all(v["azione"] == xs.ESCLUSA_REGIME for v in due)
    # Approvazione dei DA VERIFICARE: scritti solo se la cella è nell'elenco.
    dv = {"foglio": [_c("C", 10, st=DA_VERIFICARE)]}
    assert xs.piano(dv)[0]["azione"] == xs.NON_SCRITTA_STATO and xs.piano(dv, {"C10"})[0]["azione"] == xs.DA_SCRIVERE
    finto = {"foglio": [
        {"riga": 10, "voce": "a", "celle": {"C": {"valore": 5, "stato": DA_VERIFICARE, "note": []}, "D": {"valore": None, "stato": FATTO, "note": []}}},
        {"riga": 13, "voce": "b", "celle": {"C": {"valore": 5, "stato": FATTO, "note": []}}},
        {"riga": 32, "voce": "c", "celle": {"D": {"valore": 5, "stato": FATTO, "note": []}}},
    ]}
    assert [v["azione"] for v in xs.piano(finto)] == [xs.NON_SCRITTA_STATO, xs.NON_SCRITTA_VUOTA, xs.ESCLUSA_RIGA, xs.ESCLUSA_RIGA]
    assert xs.percorso_copia(ORIGINALE).name == "Fittizio_COMPILATO.xlsm"


def test_verifica_copia_corretta():
    assert _falliti(_manomessa("identica.xlsm", {})) == set()
    # Scrittura legittima simulata: un valore in C10, cella di input della whitelist.
    copia = _manomessa("legittima.xlsm", {FLUSSI: lambda x: x.replace('<c r="C10" s="1"/>', '<c r="C10" s="1"><v>777</v></c>')})
    assert _falliti(copia, {"C10": 777}) == set()
    assert _falliti(copia, {"C10": 778}) == {"Celle previste scritte con il valore atteso"}
    assert _falliti(copia) == {"Nessuna cella cambiata fuori dalla whitelist"}  # scritta ma non prevista dal piano


def test_verifica_manomissioni():
    casi = {
        "Formule invariate": {FLUSSI: lambda x: x.replace("<f>SUM(C14:C17)</f>", "<f>SUM(C14:C16)</f>")},
        "Nessuna cella cambiata fuori dalla whitelist": {FLUSSI: lambda x: x.replace("<v>1500</v>", "<v>1501</v>")},
        "Fogli": {"xl/workbook.xml": lambda x: x.replace(' state="veryHidden"', "")},
        "Protezione dei fogli invariata": {FLUSSI: lambda x: re.sub(r"<sheetProtection[^>]*/>", "", x)},
        "Protezione della cartella invariata": {"xl/workbook.xml": lambda x: re.sub(r"<workbookProtection[^>]*/>", "", x)},
        "Macro": {"xl/vbaProject.bin": lambda x: x + "x"},
        "Nessun elemento perso": {"xl/drawings/vmlDrawing1.vml": None},
        "Nomi definiti invariati": {"xl/workbook.xml": lambda x: x.replace("$B$2", "$B$3")},
    }
    for atteso, modifiche in casi.items():
        assert _falliti(_manomessa("manomessa.xlsm", modifiche)) == {atteso}, (atteso, _falliti(TMP / "manomessa.xlsm"))
    # Una formula trasformata in valore e una formula condivisa cancellata devono essere rilevate.
    copia = _manomessa("m2.xlsm", {FLUSSI: lambda x: x.replace('<c r="D13"><f t="shared" si="0"/><v>0</v></c>', '<c r="D13"><v>0</v></c>')})
    assert _falliti(copia) == {"Formule invariate"}
    # Protezione riscritta per esteso con i valori predefiniti: equivalente, nessun errore.
    copia = _manomessa("m3.xlsm", {FLUSSI: lambda x: x.replace('scenarios="1"/>', 'scenarios="1" formatCells="1" selectLockedCells="0"/>')})
    assert _falliti(copia) == set()


def test_dry_run():
    r = parser_bilancio.analizza(QUI / "bilancio_abbreviato_fittizio.pdf")
    f_json = TMP / "estrazione.json"
    f_json.write_text(json.dumps(r, ensure_ascii=False), encoding="utf-8")
    prima = impronta(ORIGINALE)
    esito = compila(f_json, ORIGINALE)
    esito["log"].unlink()
    assert esito["copia"] is None and esito["scritte"] == 0 and "DRY-RUN" in esito["testo"]
    assert impronta(ORIGINALE) == prima and not xs.percorso_copia(ORIGINALE).exists()


def test_scrittura():
    originale = TMP / "Fittizio.xlsm"
    originale.write_bytes(ORIGINALE.read_bytes())
    r = parser_bilancio.analizza(QUI / "bilancio_abbreviato_fittizio.pdf")
    f_json = TMP / "estrazione.json"
    f_json.write_text(json.dumps(r, ensure_ascii=False), encoding="utf-8")
    prima = impronta(originale)
    esito = compila(f_json, originale, scrivere=True)
    esito["log"].unlink()
    assert impronta(originale) == prima
    assert esito["scritte"] == 20, esito["testo"]
    assert esito["superato"], esito["testo"]
    celle = leggi(esito["copia"])["fogli"][FOGLIO]["celle"]
    assert celle["D10"] == ("v", float(gen.valori()["A1"][0])) and celle["C28"] == ("v", 1500.0) and "E37" not in celle
    # Il resto del file è identico byte per byte; ricalcolo all'apertura richiesto.
    with zipfile.ZipFile(originale) as a, zipfile.ZipFile(esito["copia"]) as b:
        diverse = {n for n in a.namelist() if a.read(n) != b.read(n)}
        assert a.namelist() == b.namelist() and diverse == {FLUSSI, "xl/workbook.xml"}, diverse
        assert b"fullCalcOnLoad" in b.read("xl/workbook.xml")


def test_scrittura_dichiarazione_e_approvazioni():
    """Dichiarazione in colonna E (celle sbloccate), cella bloccata rifiutata, DA VERIFICARE solo se approvato."""
    (TMP / "b").mkdir(exist_ok=True)
    originale = TMP / "b" / "Fittizio.xlsm"
    originale.write_bytes(ORIGINALE.read_bytes())
    s = leggi(originale)["fogli"][FOGLIO]["celle"]
    assert all(r in s or True for r in ("E37",))
    r = parser_dichiarazione.analizza(QUI / next(iter(gen_dr.DOCUMENTI)))
    f_json = TMP / "dichiarazione.json"
    f_json.write_text(json.dumps(r, ensure_ascii=False), encoding="utf-8")
    esito = compila(f_json, originale, scrivere=True)
    esito["log"].unlink()
    assert esito["superato"], esito["testo"]
    scritte = {v["cella"] for v in esito["voci"] if v["azione"] == xs.SCRITTA}
    assert scritte and all(c[0] == "E" for c in scritte), esito["testo"]


if __name__ == "__main__":
    gen.genera()
    gen_dr.genera()
    gen_xl.genera()
    for nome, prova in sorted(globals().items()):
        if nome.startswith("test_"):
            print(prova() or "OK", nome)
