"""Test del parser della situazione contabile su un documento FITTIZIO (due colonne, conti MM/GG/CCC)."""
import sys
import tempfile
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

QUI = Path(__file__).resolve().parent
sys.path.insert(0, str(QUI.parent))

from analisi_crisi import modello_aziende, parser_situazione  # noqa: E402

# (sinistra, destra) per riga; ogni lato = (codice, descrizione, importo) oppure None
PATR = [
    (("03/**/***", "IMMOBILIZZAZIONI IMMATERIALI", "1.000,00"), ("04/**/***", "F/AMM IMMOB. IMMAT.", "400,00")),
    (("06/**/***", "IMMOBILIZZAZIONI MATERIALI", "10.000,00"), ("07/**/***", "F/AMM IMMOB. MATERIALI", "4.000,00")),
    (("14/00000", "CREDITI V/CLIENTI", "5.000,00"), ("28/05/***", "CAPITALE", "2.000,00")),
    (("24/**/***", "DISPONIBILITA' LIQUIDE", "600,00"), ("28/20/***", "RISERVA LEGALE", "500,00")),
    (None, ("28/40/***", "UTILI PORTATI A NUOVO", "300,00")),
    (None, ("28/**/***", "PATRIMONIO NETTO", "2.800,00")),
    (None, ("34/**/***", "DEBITI V/BANCHE", "7.000,00")),
    (None, ("40/00000", "DEBITI V/FORNITORI", "2.000,00")),
]
# attività 16.600 ; passività 4.400 + 4.000 + 2.800 + 7.000 + 2.000 = 20.200 ; utile = attività - passività non quadra: serve pareggio
# si usa: totale attività 16.600, passività 16.200, utile 400
PATR[7] = (None, ("40/00000", "DEBITI V/FORNITORI", "2.000,00"))
ECON = [
    (("66/**/***", "COSTI MATERIE PRIME", "3.000,00"), ("58/**/***", "RICAVI", "9.000,00")),
    (("68/**/***", "COSTI PER SERVIZI", "1.000,00"), ("64/**/***", "ALTRI RICAVI", "200,00")),
    (("72/**/***", "COSTI PER IL PERSONALE", "4.000,00"), None),
    (("88/**/***", "ONERI FINANZIARI", "800,00"), None),
]


def _lato(c, lato, x_cod, x_fine, y):
    if lato:
        c.drawString(x_cod, y, f"{lato[0]} {lato[1][:28]}")
        c.drawRightString(x_fine, y, lato[2])


def _pdf(percorso):
    c = canvas.Canvas(str(percorso), pagesize=A4)
    for titolo, righe, tot in (
        ("SITUAZIONE PATRIMONIALE AL 31/12/2023", PATR, ["*** TOTALE ATTIVITA` 16.600,00", "*** TOTALE PASSIVITA` 16.200,00", "**** UTILE DI ESERCIZIO 400,00"]),
        ("SITUAZIONE ECONOMICA AL 31/12/2023", ECON, ["*** TOTALE COSTI 8.800,00|*** TOTALE RICAVI 9.200,00", "**** UTILE DI ESERCIZIO 400,00"]),
    ):
        c.setFont("Courier", 7)
        c.drawString(30, 800, "Ditta ALFA TEST SRL")
        c.drawString(30, 788, titolo + " Pagina 1")
        y = 760
        for sx, dx in righe:
            _lato(c, sx, 20, 285, y)
            _lato(c, dx, 310, 580, y)
            y -= 11
        for t in tot:
            for i, parte in enumerate(t.split("|")):
                c.drawString(20 if i == 0 else 310, y, parte)
            y -= 11
        c.showPage()
    c.save()


def test_situazione():
    with tempfile.TemporaryDirectory() as tmp:
        pdf = Path(tmp) / "situazione_fittizia.pdf"
        _pdf(pdf)
        r = parser_situazione.analizza(pdf)
    assert set(r["mastri"]) >= {"03", "04", "06", "07", "14", "24", "34", "40", "58", "64", "66", "68", "72", "88"}
    assert r["mastri"]["04"]["D"] == 400 and r["mastri"]["03"]["S"] == 1000
    esiti = {c["nome"].split(":")[0]: c["esito"] for c in r["controlli"]}
    assert esiti["costi"] == esiti["ricavi"] == "OK", r["controlli"]
    righe = {(x["foglio"], x["riga"]): x["celle"]["D"] for x in modello_aziende.celle_situazione(r, "D")}
    assert righe[("bilancio_sp", 7)]["valore"] == 600      # 1.000 - 400
    assert righe[("bilancio_sp", 8)]["valore"] == 6000     # 10.000 - 4.000
    assert righe[("bilancio_sp", 23)]["valore"] == 2000 and righe[("bilancio_sp", 24)]["valore"] == 500 and righe[("bilancio_sp", 25)]["valore"] == 300
    assert righe[("bilancio_sp", 32)]["valore"] == 7000 and righe[("bilancio_sp", 33)]["valore"] == 2000
    assert righe[("bilancio_ce", 6)]["valore"] == 9000 and righe[("bilancio_ce", 11)]["valore"] == 3000
    assert all(c["stato"] in ("INFERENZA", "DA VERIFICARE") for c in righe.values())
    assert r["avvisi"] and "ammortamento" in r["avvisi"][-1]


def prova():
    for nome, f in sorted(globals().items()):
        if nome.startswith("test_"):
            f()
            print("OK", nome)


if __name__ == "__main__":
    prova()
