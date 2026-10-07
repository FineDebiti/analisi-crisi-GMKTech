"""Test del parser della visura camerale su un documento FITTIZIO."""
import sys
import tempfile
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

QUI = Path(__file__).resolve().parent
sys.path.insert(0, str(QUI.parent))

from analisi_crisi import modello_aziende, parser_visura  # noqa: E402

PAG1 = ["Camera di Commercio Industria Artigianato e", "Agricoltura di FANTASIA", "Registro Imprese - Archivio ufficiale della CCIAA",
        "ESITO EVASIONE PROTOCOLLO 00001/2026 DEL", "01/01/2026", "ALFA TEST S.N.C. DI ROSSI MARIO & FIGLI DATI ANAGRAFICI",
        "Indirizzo Sede legale CITTA DI PROVA (XX) VIA", "DELLE PROVE 1", "CAP 00000", "Domicilio digitale/PEC alfa@pec.test",
        "Numero REA XX - 123456", "Codice fiscale e n.iscr. al 12345678901", "Registro Imprese", "Forma giuridica societa' in nome collettivo",
        "Procedure in corso scioglimento e liquidazione", "Liquidatore ROSSI MARIO", "Il presente documento è fornito unicamente a riscontro"]
PAG2 = ["Registro Imprese Codice fiscale e numero di iscrizione: 12345678901", "Estremi di costituzione Data atto di costituzione: 10/05/2010",
        "scioglimento e liquidazione Data iscrizione: 22/02/2021", "Data atto: 03/02/2021",
        "VARIAZIONE DELLA DENOMINAZIONE. DENOMINAZIONE PRECEDENTE:", "ALFA TEST S.R.L. IN LIQUIDAZIONE", "Data iscrizione: 16/05/2022"]


def _pdf(percorso):
    c = canvas.Canvas(str(percorso), pagesize=A4)
    for pagina in (PAG1, PAG2):
        y = 800
        c.setFont("Helvetica", 9)
        for riga in pagina:
            c.drawString(30, y, riga)
            y -= 13
        c.showPage()
    c.save()


def test_visura():
    with tempfile.TemporaryDirectory() as tmp:
        pdf = Path(tmp) / "visura_fittizia.pdf"
        _pdf(pdf)
        r = parser_visura.analizza(pdf)
    c = r["campi"]
    assert c["codice_fiscale"]["valore"] == "12345678901" and c["codice_fiscale"]["stato"] == "FATTO"
    assert c["rea"]["valore"] == "XX - 123456"
    assert c["pec"]["valore"] == "alfa@pec.test"
    assert c["stato_impresa"]["valore"] == "scioglimento e liquidazione"
    assert c["liquidatore"]["valore"] == "Rossi Mario"
    assert c["data_costituzione"]["valore"] == "10/05/2010"
    # Variazione di denominazione: ragione sociale e forma giuridica scendono a INFERENZA e c'è l'avviso.
    assert c["denominazione"]["stato"] == "INFERENZA" and c["forma_giuridica"]["stato"] == "INFERENZA"
    assert r["avvisi"] and any(e["evento"] == "variazione della denominazione" and e["data"] == "16/05/2022" for e in r["eventi"])
    righe = modello_aziende.celle_anagrafica(r)
    assert {x["riga"] for x in righe} >= {6, 7, 9, 10, 11, 13, 16, 24}


def prova():
    for nome, f in sorted(globals().items()):
        if nome.startswith("test_"):
            f()
            print("OK", nome)


if __name__ == "__main__":
    prova()
