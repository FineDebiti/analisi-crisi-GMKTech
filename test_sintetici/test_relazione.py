"""Test del semaforo e della relazione Word con dati FITTIZI."""
import sys
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

QUI = Path(__file__).resolve().parent
sys.path.insert(0, str(QUI.parent))
sys.path.insert(0, str(QUI))

import genera_ruoli_fittizio as gen  # noqa: E402
import relazione_caso as rc  # noqa: E402
from analisi_crisi import parser_ruoli, semaforo as sem, word_xml  # noqa: E402

MODELLO = QUI.parent / "Template_Preanalisi_Economico-Finanziaria_CNC.docx"


def _bilancio(ricavi_a=1_000_000, ricavi_b=1_000_000, costi=900_000, amm=20_000, pn=300_000, debiti=600_000, senza_amm=False):
    def d(k, a, v):
        return {"chiave": k, "anno": a, "valore": v, "stato": "FATTO", "fonte": {"file": "bilancio_fittizio_alfa.pdf", "pagina": 3}}
    dati = []
    for a, ric in ((-2, ricavi_a), (-1, ricavi_b)):
        dati += [d("ce.A1", a, ric), d("ce.A5", a, 0), d("ce.A", a, ric), d("ce.B", a, costi + amm), d("ce.B10", a, amm), d("ce.B9", a, 200_000), d("ce.U21", a, 30_000)]
    if senza_amm:
        dati = [x for x in dati if x["chiave"] != "ce.B10"]
    dati += [d("sp.tot_attivo", -1, 1_000_000), d("sp.tot_pn", -1, pn), d("sp.tot_debiti", -1, debiti), d("sp.disp_liquide", -1, 50_000),
             d("sp.crediti_entro", -1, 200_000), d("sp.rimanenze", -1, 100_000), d("sp.imm_mat", -1, 300_000)]
    return {"dati": dati, "controllo": [], "residui": [], "esercizi": [{"anno": -2, "data_chiusura": "2021-12-31"}, {"anno": -1, "data_chiusura": "2022-12-31"}]}


def _contesto(tmp, **kw):
    pdf = Path(tmp) / "r.pdf"
    gen.genera(pdf)
    ruoli = parser_ruoli.analizza(pdf)
    visura = {"campi": {"denominazione": {"valore": "Alfa Test Snc", "stato": "FATTO"}, "forma_giuridica": {"valore": "snc", "stato": "FATTO"}}, "avvisi": ["Variazione di denominazione."]}
    fatti = {"cr": "non_pervenuta", "situazione_assente": True, "pignoramenti_non_letti": True, "pignoramenti_atti": 3,
             "esiti": [{"fonte": "CRIF", "esito": "Nessun dato", "stato": "FATTO"}]}
    return rc.leggi_bilancio(_bilancio(**kw)), ruoli, visura, fatti


def test_semaforo_verde_e_rosso():
    ok = dict(ricavi=1000, ebitda=200, ebitda_medio=200, costi_operativi=800, ricavi_var=0.0, pn=300, passivo=400, scaduto_su_attivo=0.02,
              copertura_continuita=0.9, recovery_liquidazione=0.4, informazioni_mancanti=[])
    assert sem.valuta(ok)["verdetto"] == sem.VERDE
    ko = dict(ok, ebitda=-10, ebitda_medio=-10, copertura_continuita=0.0)
    r = sem.valuta(ko)
    assert r["verdetto"] == sem.ROSSO and "NON PERCORRIBILE" in r["esito"]
    # Un solo giallo non critico resta verde; due gialli abbassano a giallo.
    assert sem.valuta(dict(ok, ricavi_var=-0.10))["verdetto"] == sem.VERDE
    assert sem.valuta(dict(ok, ricavi_var=-0.10, scaduto_su_attivo=0.10))["verdetto"] == sem.GIALLO


def test_relazione_redditizia_e_in_perdita():
    with tempfile.TemporaryDirectory() as tmp:
        bil, ruoli, visura, fatti = _contesto(tmp)
        corpo, esito = rc.costruisci(bil, ruoli, visura, fatti)
        assert esito["verdetto"] in (sem.VERDE, sem.GIALLO)
        uscita = word_xml.salva(MODELLO, corpo, Path(tmp) / "relazione.docx")
        with zipfile.ZipFile(uscita) as z:
            ET.fromstring(z.read("word/document.xml"))  # XML ben formato
            testo = z.read("word/document.xml").decode()
        for atteso in ("SEMAFORO FINALE", "Quadro di sintesi", "1. Premessa", "13. Parametri", "Soluzioni percorribili", "Centrale dei Rischi"):
            assert atteso in testo, atteso
        bil2, ruoli, visura, fatti = _contesto(tmp, costi=1_100_000)  # in perdita
        corpo2, esito2 = rc.costruisci(bil2, ruoli, visura, fatti)
        assert esito2["verdetto"] == sem.ROSSO
        assert "NON PERCORRIBILE" in corpo2


def test_schede_complete_e_non_disponibile():
    with tempfile.TemporaryDirectory() as tmp:
        bil, ruoli, visura, fatti = _contesto(tmp)
        corpo, esito = rc.costruisci(bil, ruoli, visura, fatti)
        for atteso in ("Schede dei semafori", "Valore assoluto", "Indicatore percentuale", "Formula", "Natura e data del dato", "Documento e pagina",
                       "Soglia utilizzata", "Motivazione", "bilancio_fittizio_alfa.pdf, p. 3", "STORICO", "STIMA"):
            assert atteso in corpo, atteso
        # Ammortamenti assenti: l'EBITDA non è disponibile, il criterio non è né rosso né verde, e non c'è alcuno zero sostituito.
        bil2, ruoli, visura, fatti = _contesto(tmp, senza_amm=True)
        corpo2, esito2 = rc.costruisci(bil2, ruoli, visura, fatti)
        red = next(c for c in esito2["criteri"] if c["codice"] == "redditivita")
        assert red["colore"] is None
        assert "non disponibile" in corpo2 and "Nessun giudizio assegnato" in corpo2


def test_anonimizzazione_coerente():
    with tempfile.TemporaryDirectory() as tmp:
        bil, ruoli, visura, fatti = _contesto(tmp)
        visura["campi"]["denominazione"]["valore"] = "Zanzibar Quattrocchi S.n.c."
        visura["campi"]["codice_fiscale"] = {"valore": "01234567890", "stato": "FATTO"}
        corpo, _ = rc.costruisci(bil, ruoli, visura, fatti, anonimizza=True)
        assert "Zanzibar" in corpo and "VERSIONE ANONIMIZZATA" in corpo
        mp = rc.mappa_anonima(visura, bil, ruoli)
        out = rc.applica_anonimato(corpo, mp)
        for sensibile in ("Zanzibar", "Quattrocchi", "01234567890", "bilancio_fittizio_alfa.pdf"):
            assert sensibile.lower() not in out.lower(), sensibile
        assert "SOCIETA-01" in out and "DOC-01" in out
        assert "€ 1.000.000" in out  # gli importi restano
        assert rc.mappa_anonima(visura, bil, ruoli) == mp  # codici coerenti


def test_senza_ruoli_ne_visura():
    with tempfile.TemporaryDirectory() as tmp:
        bil, _, _, fatti = _contesto(tmp)
        fatti = dict(fatti, nome="Beta Test", bilancio_provvisorio=True, cr="non_acquisita")
        corpo, esito = rc.costruisci(bil, None, None, fatti)
        sc = next(c for c in esito["criteri"] if c["codice"] == "scaduto")
        assert sc["colore"] is None  # senza ruoli lo scaduto è "non disponibile", non zero e non rosso
        for atteso in ("Estratti di ruolo: non disponibili", "provvisorio (non depositato)", "Beta Test", "Non acquisita"):
            assert atteso in corpo, atteso


def prova():
    for nome, f in sorted(globals().items()):
        if nome.startswith("test_"):
            f()
            print("OK", nome)


if __name__ == "__main__":
    prova()
