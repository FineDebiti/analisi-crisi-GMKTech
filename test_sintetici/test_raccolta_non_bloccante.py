"""Test della raccolta documentale NON BLOCCANTE (checklist A/B, preanalisi provvisoria, approvazione come provvisoria). Solo dati SINTETICI."""
import json
import re
import sys
import tempfile
import zipfile
from pathlib import Path

QUI = Path(__file__).resolve().parent
sys.path.insert(0, str(QUI.parent))
sys.path.insert(0, str(QUI))

from analisi_crisi import checklist as ck  # noqa: E402
from analisi_crisi import pratica as pr  # noqa: E402

BUONE = {"margine": 0.10, "rapporti": {"a": 2.0}, "pn_su_attivo": 0.2, "pubblici_su_attivo": 0.03, "cassa_verificata": True}
PARZIALI = {"margine": 0.10, "rapporti": {"a": 2.0}}     # patrimonio e debiti pubblici mancanti
POVERE = {"margine": 0.02, "rapporti": {"a": 4.0}, "pn_su_attivo": -0.05, "pubblici_su_attivo": 0.30, "crediti_soci_su_attivo": 0.2}


def nuova(tmp):
    return pr.apri_pratica(Path(tmp) / "PRATICA", "CasoSint", "Tester")


def doc(tmp, p, nome, tipo, contenuto=None):
    f = Path(tmp) / (nome + ".txt")
    f.write_bytes((contenuto or nome).encode() + b" " + str(tmp).encode())
    return pr.registra_documento(p, nome, f, tipo, natura="STORICO")


def testo_word(out):
    xml = zipfile.ZipFile(out).read("word/document.xml").decode("utf-8")
    return re.sub(r"<[^>]+>", " ", xml), xml


def pulito(testo):
    assert not re.search(r"\bNone\b|\bnan\b|[{}]", testo), re.findall(r"\bNone\b|\bnan\b|[{}]", testo)


def nessun_rosso(d, out):
    assert "ROSSO" not in json.dumps(d, ensure_ascii=False)
    t, xml = testo_word(out)
    assert "ROSSO" not in t and "FFC7CE" not in xml


def test_registro_vuoto_ricognizione():
    with tempfile.TemporaryDirectory() as t:
        p = nuova(t)
        d = pr.avvia_preanalisi(p)          # nessun blocco
        assert d["tipo"] == "RICOGNIZIONE_FASCICOLO" and (p / "ricognizione_fascicolo.json").exists() and not (p / "preanalisi_provvisoria.json").exists()
        assert 1 <= len(d["richieste_prioritarie"]) <= 5 and all(r["permette_di_verificare"] for r in d["richieste_prioritarie"])
        assert d["sufficienza"]["per_iniziare"]["ok"] is True and d["sufficienza"]["per_concludere"]["ok"] is False
        out = p / d["documento_word"]
        txt, _ = testo_word(out)
        assert out.name.startswith("Ricognizione_fascicolo") and pr.DICITURA_PROVVISORIA in txt and "Ricognizione del fascicolo" in txt
        for sez in ("Sintesi dei limiti informativi", "Checklist documentale", "Dati estratti", "Criticità e incongruenze", "Calcoli eseguibili",
                    "Giudizi preliminari", "Sezioni non valutabili", "Richieste documentali prioritarie", "Versione del motore", "INIZIARE", "CONCLUDERE"):
            assert sez in txt, sez
        assert pr.ND in txt and "provvisori e da riconciliare" in txt and "esposizione non verificata" in txt
        pulito(txt)
        nessun_rosso(d, out)
        assert all(s["valore"] == pr.ND for s in d["sezioni"])
        v = json.loads((p / "verbale.json").read_text(encoding="utf-8"))
        assert v[1]["controllo"] == "AVVIO PREANALISI" and "limiti" in v[1]["dettaglio"] and v[1]["versione_motore"] and pr.verifica_verbale(p)["ok"]
        assert pr.stato(p) == "APERTA"


def test_solo_visura():
    with tempfile.TemporaryDirectory() as t:
        p = nuova(t)
        doc(t, p, "visura_camerale", "visura")
        d = pr.avvia_preanalisi(p)
        assert d["tipo"] == "RICOGNIZIONE_FASCICOLO"
        a = {v["id"]: v for v in d["checklist"]["A"]}
        assert a["A1"]["stato"] == "ricevuto" and a["A2"]["stato"] == "mancante"
        assert not any(r["voce"] == "A1" for r in d["richieste_prioritarie"]) and d["richieste_prioritarie"][0]["voce"] == "A2"
        nessun_rosso(d, p / d["documento_word"])


def test_solo_bilanci_con_calcoli_parziali():
    with tempfile.TemporaryDirectory() as t:
        p = nuova(t)
        doc(t, p, "bilancio_2024", "bilancio")
        d = pr.avvia_preanalisi(p, PARZIALI)
        assert d["tipo"] == "PREANALISI_PROVVISORIA" and (p / "preanalisi_provvisoria.json").exists()
        s = {x["sezione"]: x for x in d["sezioni"]}
        nd = [x for x in d["sezioni"] if x["stato"] == "NON CALCOLABILE"]
        assert len(nd) >= 3 and all(x["valore"] == pr.ND for x in nd)               # nessuno zero al posto del dato mancante
        assert not any(x["valore"] in ("0", "0,0%", "0,00", 0) for x in d["sezioni"])
        assert s["Margine EBITDA"]["stato"] == "CALCOLABILE" and s["Patrimonio netto / attivo"]["stato"] == "NON CALCOLABILE"
        assert d["giudizi_preliminari"] and all(g["etichetta"] == "PRELIMINARE / PROVVISORIO" for g in d["giudizi_preliminari"])
        assert not any("Patrimonio" in g["giudizio"] for g in d["giudizi_preliminari"])  # criterio senza dato: nessun giudizio
        assert "provvisori e da riconciliare" in " ".join(d["fallback"]) and "esposizione non verificata" in " ".join(d["fallback"])
        out = p / d["documento_word"]
        txt, _ = testo_word(out)
        assert out.name.startswith("Preanalisi_provvisoria") and pr.DICITURA_PROVVISORIA in txt and "PRELIMINARE / PROVVISORIO" in txt
        pulito(txt)
        nessun_rosso(d, out)
        assert d["riquadri"]["fattibilita"]["esito"] in ("CONDIZIONATA", "NON CONCLUDENTE")
        assert d["sufficienza"]["per_iniziare"]["ok"] and not d["sufficienza"]["per_concludere"]["ok"]


def test_rosso_solo_per_dati_non_per_assenza():
    with tempfile.TemporaryDirectory() as t:
        p = nuova(t)
        doc(t, p, "bilancio_2024", "bilancio")
        d = pr.avvia_preanalisi(p, {"margine": -0.05, "rapporti": {"a": 2.0}})   # rosso legittimo: dato reale
        assert d["riquadri"]["sostenibilita"]["esito"] == "ROSSO"
        assert d["riquadri"]["qualita_dati"]["colore"] != "ROSSO" and d["riquadri"]["fattibilita"]["esito"] != "NON PERCORRIBILE"
        p2 = nuova(Path(t) / "x") if (Path(t) / "x").mkdir() is None else None
        doc(Path(t) / "x", p2, "bilancio_2024", "bilancio")
        d2 = pr.avvia_preanalisi(p2, {"rapporti": {"a": 2.0}})                   # un solo dato, gli altri assenti
        assert d2["riquadri"]["sostenibilita"]["esito"] != "ROSSO" and d2["riquadri"]["qualita_dati"]["colore"] != "ROSSO"


def test_massimo_cinque_richieste():
    with tempfile.TemporaryDirectory() as t:
        p = nuova(t)
        doc(t, p, "bilancio_2024", "bilancio")
        d = pr.avvia_preanalisi(p, POVERE)
        sugg = [v for v in d["checklist"]["B"] if v["suggerita"]]
        assert len(sugg) + 3 > 5                       # molte voci mancanti...
        assert len(d["richieste_prioritarie"]) == 5   # ...ma al massimo cinque
        assert [r["ordine"] for r in d["richieste_prioritarie"]] == [1, 2, 3, 4, 5] and all(r["permette_di_verificare"] for r in d["richieste_prioritarie"])


def test_sospensione_del_solo_scenario_interessato():
    with tempfile.TemporaryDirectory() as t:
        p = nuova(t)
        doc(t, p, "bilancio_2024", "bilancio")
        m = dict(BUONE, crediti_soci_su_attivo=0.2)    # unica criticità: crediti verso soci (B10 -> liquidazione, ristrutturazione)
        d = pr.avvia_preanalisi(p, m)
        sc = {x["scenario"]: x for x in d["scenari"]}
        assert sc[ck.SCENARI["liquidazione"]]["stato"] == "GIUDIZIO SOSPESO" and sc[ck.SCENARI["ristrutturazione"]]["stato"] == "GIUDIZIO SOSPESO"
        assert "crediti verso soci" in " ".join(sc[ck.SCENARI["liquidazione"]]["motivo"])
        assert sc[ck.SCENARI["continuita"]]["stato"] == "VALUTABILE IN VIA PRELIMINARE" and sc[ck.SCENARI["transazione_fiscale"]]["stato"] == "VALUTABILE IN VIA PRELIMINARE"
        assert any(g["esito"] for g in d["giudizi_preliminari"])      # il resto prosegue
        pr.imposta_stato_voce(p, "B10", "ricevuto", "Tester")
        d = pr.avvia_preanalisi(p, m)
        assert all(x["stato"] == "VALUTABILE IN VIA PRELIMINARE" for x in d["scenari"])
        pr.imposta_stato_voce(p, "B10", "non pertinente", "Tester")
        assert all(x["stato"] != "GIUDIZIO SOSPESO" for x in pr.avvia_preanalisi(p, m)["scenari"])


def test_fallback_ruoli_e_cr():
    with tempfile.TemporaryDirectory() as t:
        p = nuova(t)
        doc(t, p, "bilancio_2024", "bilancio")
        d = pr.avvia_preanalisi(p, PARZIALI)
        assert any("provvisori e da riconciliare" in x for x in d["fallback"]) and any("esposizione non verificata" in x for x in d["fallback"])
        doc(t, p, "estratto_ruolo", "ruolo")
        doc(t, p, "cr_banca_italia", "centrale rischi")
        d = pr.avvia_preanalisi(p, PARZIALI)
        assert d["fallback"] == [] and not any("riconciliare" in x or "non verificata" in x for x in d["limiti_informativi"])


def test_checklist_stati_e_sicurezza():
    with tempfile.TemporaryDirectory() as t:
        p = nuova(t)
        assert ck.STATI_VOCE == ("ricevuto", "mancante", "da aggiornare", "illeggibile", "non pertinente", "inesistente")
        c = ck.stato_checklist(p)
        assert [v["id"] for v in c["A"]] == ["A1", "A2", "A3", "A4"] and len(c["B"]) == 10 and all(v["stato"] == "mancante" for g in c.values() for v in g)
        assert all(v["trigger"] and v["scenari"] for v in c["B"]) and not any(v["suggerita"] for v in c["B"])
        for st in ck.STATI_VOCE:
            pr.imposta_stato_voce(p, "A3", st, "Tester")
            assert {v["id"]: v for v in ck.stato_checklist(p)["A"]}["A3"]["stato"] == st
        for args in (("A3", "inventato", "Tester"), ("ZZ", "ricevuto", "Tester"), ("A3", "ricevuto", "  ")):
            try:
                pr.imposta_stato_voce(p, *args)
                raise SystemExit("FALLITO: valore non valido accettato")
            except pr.ErrorePratica:
                pass
        assert (p / "checklist.json").exists() and pr.verifica_verbale(p)["ok"]
        assert ck.sufficienza_per_iniziare(p)["ok"] is True and ck.sufficienza_per_concludere(p)["ok"] is False


def test_consolidamento_ancora_vincolato_e_approvazione_provvisoria():
    with tempfile.TemporaryDirectory() as t:
        p = nuova(t)
        doc(t, p, "bilancio_2024", "bilancio")
        try:
            pr.approva_come_provvisoria(p, "Avv. Prova")
            raise SystemExit("FALLITO: approvazione senza preanalisi")
        except pr.ErrorePratica:
            pass
        pr.avvia_preanalisi(p, BUONE)
        try:
            pr.valuta(p, BUONE)
            raise SystemExit("FALLITO: valuta() senza gate")
        except pr.GateNonSuperato:
            pass
        assert not (p / "valutazione_v3.json").exists()
        for nome in ("", "  ", None):
            try:
                pr.approva_come_provvisoria(p, nome)
                raise SystemExit("FALLITO: approvazione senza nome")
            except pr.ErrorePratica:
                pass
        assert pr.stato_approvazione(p) is None
        a = pr.approva_come_provvisoria(p, "Avv. Prova")
        assert a["stato"] == "APPROVATA COME PROVVISORIA" and pr.stato_approvazione(p)["valida"]
        v = json.loads((p / "verbale.json").read_text(encoding="utf-8"))
        r = [x for x in v if x["controllo"] == "APPROVAZIONE PROVVISORIA" and x["esito"] == "OK"][-1]
        assert "Avv. Prova" in r["dettaglio"] and re.search(r"20\d\d-\d\d-\d\dT", r["dettaglio"]) and "APPROVATA COME PROVVISORIA" in r["dettaglio"]
        assert pr.verifica_verbale(p)["ok"] and pr.stato(p) == "APERTA"
        txt, _ = testo_word(p / a["documento_word"])
        assert "APPROVATA COME PROVVISORIA da Avv. Prova" in txt and "PREANALISI PROVVISORIA" in txt
        pulito(txt)
        pr.avvia_preanalisi(p, BUONE)       # rigenerata: l'approvazione precedente non vale piu'
        assert pr.stato_approvazione(p)["valida"] is False


def test_nessun_blocco_su_creazione_e_documenti():
    with tempfile.TemporaryDirectory() as t:
        p = nuova(t)
        pr.registra_documento(p, "atteso_ma_mancante", None, "tesoreria", decisivo=True)   # registro con solo un mancante
        d = pr.avvia_preanalisi(p)
        assert d["tipo"] == "RICOGNIZIONE_FASCICOLO"
        doc(t, p, "bilancio", "bilancio")             # si possono caricare documenti dopo l'avvio
        assert pr.avvia_preanalisi(p, PARZIALI)["tipo"] == "PREANALISI_PROVVISORIA"
        assert pr.verifica_verbale(p)["ok"]


# ---------------------------------------------------------------- interfaccia
def test_interfaccia_raccolta():
    import test_interfaccia as ti
    il = ti.il
    with tempfile.TemporaryDirectory() as tmp:
        c = Path(tmp) / "cfg.json"
        c.write_text('{"semaforo": "v3"}')
        il.CONFIG = c
        (Path(tmp) / "casi").mkdir()
        srv, base = ti._avvia(Path(tmp) / "casi")
        try:
            assert ti._post(base + "/nuovo", {"nome": "CasoRac"})[0] == 200
            pag = ti._get(base + "/caso/CasoRac")[1].decode()
            assert "A. Documenti di partenza" in pag and "B. Approfondimenti suggeriti dall&#x27;analisi" in pag or "B. Approfondimenti suggeriti dall'analisi" in pag
            assert "Avvia preanalisi" in pag and "disabled" not in pag and "confirm(" not in pag and pag.count("Limiti informativi") == 1
            for st in ck.STATI_VOCE:
                assert "<option>%s</option>" % st in pag or "<option selected>%s</option>" % st in pag
            # senza alcuna pratica e senza nome: la preanalisi parte (ricognizione)
            s, corpo = ti._post(base + "/caso/CasoRac/pratica/preanalisi", {})
            assert s == 200 and "Ricognizione del fascicolo" in corpo
            assert corpo.count("<div class='rq ") == 6 and "Sufficienza per iniziare" in corpo and "Sufficienza per concludere" in corpo
            for tit in ("Allerta finanziaria / sostenibilità sui dati storici", "Qualità dei dati", "Fattibilità", "Stato della conclusione"):
                assert "<h3>%s</h3>" % tit in corpo
            pc = Path(tmp) / "casi" / "CasoRac" / "PRATICA"
            assert list(pc.glob("Ricognizione_fascicolo_*.docx")) and "/file/PRATICA/Ricognizione_fascicolo_" in corpo
            # stati: serve il nome; valori fuori elenco ignorati
            assert ti._post(base + "/caso/CasoRac/pratica/checklist", {"s_A1": "ricevuto", "nome": ""})[0] == 400
            assert ti._post(base + "/caso/CasoRac/pratica/checklist", {"s_A1": "<script>", "nome": "T"})[1].count("Nessuna modifica") == 1
            s, corpo = ti._post(base + "/caso/CasoRac/pratica/checklist", {"s_A1": "ricevuto", "s_B1": "da aggiornare", "nome": "Tester"})
            assert s == 200 and "<option selected>ricevuto</option>" in corpo
            # escape HTML nel nome mostrato
            ap = ti._post(base + "/caso/CasoRac/pratica/approva", {"nome": "<b>X</b>"})
            assert ap[0] == 200 and "<b>X</b>" not in ap[1] and "&lt;b&gt;X&lt;/b&gt;" in ap[1]
            assert ti._post(base + "/caso/CasoRac/pratica/approva", {"nome": " "})[0] == 400
            assert pr.stato_approvazione(pc)["approvata_da"] == "<b>X</b>"
            # gate per il consolidamento ancora attivo via interfaccia
            assert ti._post(base + "/caso/CasoRac/pratica/valuta", {})[0] in (400, 409)
            assert not (pc / "valutazione_v3.json").exists()
            # pagina con voce ostile nella checklist -> escape
            (pc / "metriche.json").write_text(json.dumps(PARZIALI))
            (pc.parent / "bil.pdf").write_bytes(b"%PDF-1.4 sintetico")
            assert ti._post(base + "/caso/CasoRac/pratica/registra", {"pdf": "bil.pdf", "tipo": "bilancio", "natura": "STORICO"})[0] == 200
            assert ti._post(base + "/caso/CasoRac/pratica/preanalisi", {"nome": "T"})[0] == 200
            assert (pc / "preanalisi_provvisoria.json").exists()
            pag = ti._get(base + "/caso/CasoRac")[1].decode()
            assert "non è più valida" in pag and "PRELIMINARE / PROVVISORIO" in pag and pag.count("<div class='rq ") == 6
        finally:
            srv.shutdown()
            il.CONFIG = il.PROGETTO / "config_motore.json"


def test_interfaccia_v2_invariata():
    import test_interfaccia as ti
    il = ti.il
    with tempfile.TemporaryDirectory() as tmp:
        c = Path(tmp) / "cfg.json"
        c.write_text('{"semaforo": "v2"}')
        il.CONFIG = c
        (Path(tmp) / "casi").mkdir()
        srv, base = ti._avvia(Path(tmp) / "casi")
        try:
            ti._post(base + "/nuovo", {"nome": "CasoV2"})
            pag = ti._get(base + "/caso/CasoV2")[1].decode()
            assert "Raccolta documentale" not in pag and "Avvia preanalisi" not in pag
            assert ti._post(base + "/caso/CasoV2/pratica/preanalisi", {})[0] == 404
        finally:
            srv.shutdown()
            il.CONFIG = il.PROGETTO / "config_motore.json"


def prova():
    for nome, f in sorted(globals().items()):
        if nome.startswith("test_"):
            f()
            print("OK", nome)


if __name__ == "__main__":
    prova()
