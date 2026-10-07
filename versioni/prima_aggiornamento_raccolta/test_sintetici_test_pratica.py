"""Test del modulo pratica (registro, gate, verbale a catena di hash, prospetto) su dati SINTETICI. python test_sintetici/test_pratica.py"""
import json
import re
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

QUI = Path(__file__).resolve().parent
RADICE = QUI.parent
sys.path.insert(0, str(RADICE))

from analisi_crisi import pratica as pr  # noqa: E402
from analisi_crisi import versione  # noqa: E402

METRICHE = {"margine": 0.10, "rapporti": {"a": 2.0}, "pn_su_attivo": 0.2, "pubblici_su_attivo": 0.03, "cassa_verificata": True}


def nuova(tmp, simulato=True):
    """Pratica sintetica fino a NUMERI_IN_VERIFICA, con due numeri decisivi non confermati."""
    doc = Path(tmp) / "bilancio_sint.txt"
    doc.write_bytes(b"documento sintetico " + str(Path(tmp)).encode())
    p = pr.apri_pratica(Path(tmp) / "PRATICA", "CasoSint", "Tester", dataset_simulato=simulato)
    d = pr.registra_documento(p, "bilancio_sint.pdf", doc, "bilancio", "2025-12-31", "2025", "STORICO")
    pr.registra_documento(p, "tesoreria", None, "movimenti", decisivo=True)
    pr.aggiungi_dato(p, "Ricavi", 1000, "EUR", "FATTO", d["id"], 3)
    pr.proponi_numeri_decisivi(p, [{"nome": "EBITDA", "valore": 100, "unita": "EUR", "fonte": "doc 1 p.3"}, {"nome": "Debito netto", "valore": 200, "unita": "EUR", "fonte": "doc 1 p.4"}])
    pr.avanza(p, "REGISTRO_PRONTO")
    pr.avanza(p, "NUMERI_IN_VERIFICA")
    return p


def verificata(tmp):
    p = nuova(tmp)
    pr.conferma_numero(p, 1, "Avv. Prova")
    pr.conferma_numero(p, 2, "Avv. Prova", corretto_a=210)
    pr.avanza(p, "NUMERI_VERIFICATI")
    return p


def test_gate():
    with tempfile.TemporaryDirectory() as t:
        p = nuova(t)
        try:
            pr.valuta(p, METRICHE)
            raise SystemExit("FALLITO: valutazione prodotta prima della conferma")
        except pr.GateNonSuperato:
            pass
        assert not (p / "valutazione_v3.json").exists() and not (p / "parametri_usati.json").exists()
        pr.conferma_numero(p, 1, "Avv. Prova")
        pr.conferma_numero(p, 2, "Avv. Prova", corretto_a=210)
        try:   # stato non ancora NUMERI_VERIFICATI
            pr.valuta(p, METRICHE)
            raise SystemExit("FALLITO: valutazione a stato insufficiente")
        except pr.GateNonSuperato as e:
            assert "stato" in str(e)
        # incongruenza sostanziale aperta blocca l'avanzamento e la valutazione
        inc = pr.aggiungi_incongruenza(p, "Totali non quadrano", ["Ricavi"], "SOSTANZIALE")
        try:
            pr.avanza(p)
            raise SystemExit("FALLITO: avanzamento con incongruenza sostanziale")
        except pr.ErrorePratica:
            pass
        pr.risolvi_incongruenza(p, inc["id"], "Avv. Prova", "verificato sul documento")
        pr.aggiungi_incongruenza(p, "Arrotondamento", [], "MINORE")   # una minore aperta non blocca
        pr.avanza(p)
        r = pr.valuta(p, METRICHE)
        assert r["sostenibilita"]["colore"] == "VERDE"
        assert "NON DEFINITIVA" in r["stato"]   # tesoreria (decisivo) non disponibile
        assert (p / "valutazione_v3.json").exists()
        par = json.loads((p / "parametri_usati.json").read_text(encoding="utf-8"))
        assert par["versione_motore"] == versione.MOTORE and par["impronta"] == versione.impronta() and "SOGLIE_V3" in par["parametri"]
        # un nuovo numero non confermato (dopo riapertura) richiude il gate
        pr.riapri(p, "NUMERI_IN_VERIFICA", "nuovo dato", "Avv. Prova")
        pr.proponi_numeri_decisivi(p, [{"nome": "Cassa", "valore": 5}])
        assert pr.valutazione_prodotta(p) is None
        assert pr.verifica_verbale(p)["ok"]


def test_dataset_simulato_e_definitiva():
    with tempfile.TemporaryDirectory() as t:
        p = verificata(t)
        docs = [{"nome": "d", "disponibile": True, "aggiornato": True}]
        r = pr.valuta(p, METRICHE, docs, [{"nome": "x", "disponibile": True}], scenari_tutti_valutabili=True, esito_scenari="sufficiente")
        assert r["stato"] == "VALUTAZIONE COMPLETA sul dataset simulato"


def test_nessun_salto_e_riapri():
    with tempfile.TemporaryDirectory() as t:
        p = pr.apri_pratica(Path(t) / "P", "X", "Tester")
        assert pr.stato(p) == "APERTA"
        for bersaglio in ("NUMERI_VERIFICATI", "CONSOLIDATA", "NUMERI_IN_VERIFICA"):
            try:
                pr.avanza(p, bersaglio)
                raise SystemExit("FALLITO: salto ammesso")
            except pr.ErrorePratica:
                pass
        assert pr.stato(p) == "APERTA"
        try:   # registro vuoto: nemmeno il passo successivo
            pr.avanza(p)
            raise SystemExit("FALLITO: avanzamento senza registro")
        except pr.ErrorePratica:
            pass
        (Path(t) / "b").mkdir()
        p2 = verificata(Path(t) / "b")
        # ritorno indietro solo con riapri (nome e motivo obbligatori, traccia nel verbale)
        for args in (("NUMERI_IN_VERIFICA", "", "Avv"), ("NUMERI_IN_VERIFICA", "motivo", " "), ("CONSOLIDATA", "motivo", "Avv")):
            try:
                pr.riapri(p2, *args)
                raise SystemExit("FALLITO: riapri non valido accettato")
            except pr.ErrorePratica:
                pass
        pr.riapri(p2, "REGISTRO_PRONTO", "correzione registro", "Avv. Prova")
        assert pr.stato(p2) == "REGISTRO_PRONTO"
        v = json.loads((p2 / "verbale.json").read_text(encoding="utf-8"))
        assert v[-1]["controllo"] == "RIAPERTURA" and "correzione registro" in v[-1]["dettaglio"] and "Avv. Prova" in v[-1]["dettaglio"]


def test_conferma_richiede_nome():
    with tempfile.TemporaryDirectory() as t:
        p = nuova(t)
        for nome in ("", "   ", None):
            try:
                pr.conferma_numero(p, 1, nome)
                raise SystemExit("FALLITO: conferma senza nome")
            except pr.ErrorePratica:
                pass
        n = json.loads((p / "numeri_decisivi.json").read_text(encoding="utf-8"))
        assert not n[0]["confermato_da"]
        pr.conferma_numero(p, 1, "Avv. Prova")
        n = json.loads((p / "numeri_decisivi.json").read_text(encoding="utf-8"))
        assert n[0]["confermato_da"] == "Avv. Prova" and n[0]["data_conferma"]


def test_verbale_append_only_e_catena():
    with tempfile.TemporaryDirectory() as t:
        p = verificata(t)
        pr.valuta(p, METRICHE)
        assert pr.verifica_verbale(p) == {"ok": True, "n": len(json.loads((p / "verbale.json").read_text(encoding="utf-8"))), "errore": None}
        assert not [f for f in dir(pr) if f.lower() in ("cancella_verbale", "modifica_verbale")]
        orig = (p / "verbale.json").read_text(encoding="utf-8")
        v = json.loads(orig)
        assert all(r["versione_motore"] == versione.MOTORE and r["impronta"] and r["hash"] for r in v)
        assert v[0]["prec"] == "0" * 64 and all(v[i]["prec"] == v[i - 1]["hash"] for i in range(1, len(v)))
        # manomissioni: modifica di un record, cancellazione intermedia, troncamento in coda, inserimento
        casi = {}
        m = json.loads(orig); m[2]["esito"] = "OK-MODIFICATO"; casi["modifica"] = m
        m = json.loads(orig); del m[3]; casi["cancellazione"] = m
        m = json.loads(orig); casi["troncamento"] = m[:-1]
        m = json.loads(orig); m.insert(2, dict(m[2])); casi["inserimento"] = m
        for nome, dati in casi.items():
            (p / "verbale.json").write_text(json.dumps(dati), encoding="utf-8")
            r = pr.verifica_verbale(p)
            assert not r["ok"] and r["errore"], nome
        (p / "verbale.json").write_text(orig, encoding="utf-8")
        assert pr.verifica_verbale(p)["ok"]


def test_prospetto_senza_colori_ne_giudizi():
    with tempfile.TemporaryDirectory() as t:
        p = nuova(t)
        pr.aggiungi_incongruenza(p, "Totale attivo diverso dalla somma", ["Ricavi"], "SOSTANZIALE")
        pr.aggiungi_richiesta(p, "Estratti conto 2025", "serve la tesoreria", 1, "Cliente")
        d = pr.prospetto_preconclusivo(p)
        assert d["dicitura"] == pr.DICITURA and d["versione_motore"] == versione.MOTORE and d["impronta"] == versione.impronta()
        out = pr.genera_prospetto_word(p)
        xml = zipfile.ZipFile(out).read("word/document.xml").decode("utf-8")
        testo = re.sub(r"<[^>]+>", " ", xml)
        assert pr.DICITURA in testo and versione.MOTORE in testo and versione.impronta() in testo
        for fill in ("C6EFCE", "FFEB9C", "FFC7CE", "EDEDED", "9C0006", "006100", "7F6000"):
            assert fill not in xml, fill
        for parola in ("VERDE", "GIALLO", "ROSSO", "PERCORRIBILE", "CONDIZIONATA", "NON CONCLUDENTE", "DEFINITIVA", "ALLERTA"):
            assert parola not in testo.replace("NON DEFINITIVA", ""), parola
        for sezione in ("Registro documentale", "Dati estratti", "Incongruenze", "Richieste prioritarie", "Numeri decisivi"):
            assert sezione in testo
        out2 = pr.genera_prospetto_word(p)   # non sovrascrive
        assert out2 != out and out.exists() and out2.exists()


def test_registro_e_dati():
    with tempfile.TemporaryDirectory() as t:
        p = nuova(t)
        reg = json.loads((p / "registro_documentale.json").read_text(encoding="utf-8"))
        assert reg[0]["id"] == 1 and len(reg[0]["sha256"]) == 64 and reg[0]["data_acquisizione"] and reg[0]["natura"] == "STORICO"
        assert reg[1]["natura"] == "NON DISPONIBILE" and reg[1]["sha256"] is None and reg[1]["decisivo"]
        try:
            pr.registra_documento(p, "copia", Path(t) / "bilancio_sint.txt", "x", natura="STORICO")
            raise SystemExit("FALLITO: duplicato")
        except pr.ErrorePratica:
            pass
        for args in (("D", 1, "x", "INVENTATA"), ("D", 1, "x", "FATTO", 99), ("D", 1, "x", "FATTO", None)):
            try:
                pr.aggiungi_dato(p, *args)
                raise SystemExit("FALLITO: dato non valido accettato")
            except pr.ErrorePratica:
                pass


def test_persistenza_dopo_riavvio():
    with tempfile.TemporaryDirectory() as t:
        p = verificata(t)
        codice = ("import sys, json; sys.path.insert(0, %r); from analisi_crisi import pratica as pr; p=%r; "
                  "print(json.dumps([pr.stato(p), pr.gate_superato(p), pr.verifica_verbale(p)['ok']]))") % (str(RADICE), str(p))
        out = subprocess.run([sys.executable, "-c", codice], capture_output=True, text=True, check=True).stdout
        assert json.loads(out) == ["NUMERI_VERIFICATI", True, True]


def test_versione_e_config():
    assert versione.MOTORE == "Preanalisi Crisi v1.0-pilota"
    par = versione.parametri()
    assert par["riferimento_normativo"] == "decreto dirigenziale 23/04/2026" and "rapporto_fasce" in par["SOGLIE_V3"]
    assert len(versione.impronta()) == 64 and versione.impronta() == versione.impronta()
    with tempfile.TemporaryDirectory() as t:
        c = Path(t) / "c.json"
        assert versione.semaforo_attivo(c) == "v3"           # assente = v3
        c.write_text('{"semaforo": "v2"}'); assert versione.semaforo_attivo(c) == "v2"
        c.write_text('{"semaforo": "v3"}'); assert versione.semaforo_attivo(c) == "v3"
    assert json.loads((RADICE / "config_motore.json").read_text()) == {"semaforo": "v3"}


def prova():
    for nome, f in sorted(globals().items()):
        if nome.startswith("test_"):
            f()
            print("OK", nome)


if __name__ == "__main__":
    prova()
