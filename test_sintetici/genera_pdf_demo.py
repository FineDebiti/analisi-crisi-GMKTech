"""Scrive in una cartella 3 PDF SINTETICI per provare l'interfaccia con il browser: bilancio, visura finta, altro. Nessun dato reale.

Uso:  .venv/bin/python test_sintetici/genera_pdf_demo.py [cartella]      (default: ./PDF_DEMO)
"""
import sys
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

QUI = Path(__file__).resolve().parent
sys.path.insert(0, str(QUI))
import genera_bilancio_fittizio as gb  # noqa: E402


def _testo(percorso, righe):
    c = canvas.Canvas(str(percorso), pagesize=A4)
    y = 800
    for i, r in enumerate(righe):
        c.setFont("Helvetica-Bold" if i == 0 else "Helvetica", 14 if i == 0 else 10)
        c.drawString(60, y, r)
        y -= 22 if i == 0 else 15
    c.save()


def genera(cartella):
    cartella = Path(cartella)
    cartella.mkdir(parents=True, exist_ok=True)
    gb.scrivi_bilancio(cartella / "bilancio_demo.pdf")
    _testo(cartella / "visura_demo.pdf", [
        "VISURA CAMERALE ORDINARIA - DOCUMENTO FITTIZIO", "Camera di Commercio di Città Fittizia", "Denominazione: ALFA FITTIZIA S.R.L.",
        "Forma giuridica: società a responsabilità limitata", "Codice fiscale: 00000000000 (fittizio)", "Sede legale: Via Inventata 1, Città Fittizia",
        "Stato attività: attiva", "Procedure in corso: nessuna (dato fittizio)", "Amministratore unico: Mario Fittizio (nome inventato)"])
    _testo(cartella / "altro_demo.pdf", [
        "CONTRATTO DI FORNITURA - DOCUMENTO FITTIZIO", "Tra ALFA FITTIZIA S.R.L. e BETA INVENTATA S.P.A.", "Oggetto: fornitura di materiali (esempio).",
        "Durata: 24 mesi dalla firma.", "Nessun valore reale: file creato solo per le prove."])
    return sorted(cartella.glob("*.pdf"))


if __name__ == "__main__":
    dest = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("PDF_DEMO")
    for f in genera(dest):
        print("Creato:", f)
