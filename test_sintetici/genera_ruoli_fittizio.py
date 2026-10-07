"""Estratto di ruolo FITTIZIO (nomi e importi inventati) nel formato "Estratto Ruolo Semplificato" a testo."""
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

# (tipo, numero, ente, righe[(carico, sgravio, pagato, residuo)], diritti, aggio, mora, spese)
DOCS = [
    ("CARTELLA NR.", "09720200000001111 000", "00001 AMMINISTRAZIONE FINANZIARIA TEST", [(1000.00, 0.00, 100.00, 900.00), (200.00, 0.00, 0.00, 200.00)], 10.00, 50.00, 20.00, 5.00),
    ("AVV.ADD.NR.", "09720200000002222 000", "00002 INPS TEST", [(500.50, 0.00, 0.00, 500.50)], 0.00, 25.00, 10.00, 0.00),
    ("CARTELLA NR.", "09720200000003333 000", "00003 COMUNE DI FANTASIA", [(300.00, 0.00, 0.00, 300.00)], 5.00, 15.00, 0.00, 0.00),
]


def tot(d):
    return round(sum(r[3] for r in d[3]) + d[4] + d[5] + d[6] + d[7], 2)


def fmt(x):
    return f"{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def genera(percorso):
    c = canvas.Canvas(str(percorso), pagesize=A4)
    totale = 0
    for d in DOCS:
        y = 800
        for riga in ("---- 01/01/2026 10:00 V0A0 ------+", "+ RISCOSSIONE TEST S.P Provincia di:FANTASIA 01+", "+ Estratto Ruolo Semplificato +",
                     "+ COD.FISCALE +AZIENDA FITTIZIA SRL TEST001 +", "+ 00000000000 + +",
                     f"+ {d[0]} {d[1]} Rateazione:N +", f"+ ENTE : {d[2]} +", "+ Pr. Cod. T Anno Causale Tributo +",
                     "+ Imp.carico Imp. sgravio Imp.pagato Imp.residuo +"):
            c.setFont("Courier", 8); c.drawString(30, y, riga); y -= 12
        for i, r in enumerate(d[3]):
            c.drawString(30, y, f"+001 0001 I 2019 TRIBUTO FITTIZIO {i} +"); y -= 12
            c.drawString(30, y, "+ " + " ".join(fmt(x) for x in r) + " +"); y -= 12
        for lab, v in (("Totale tributi in debito", sum(r[3] for r in d[3])), ("Diritti di notifica", d[4]), ("Aggio", d[5]),
                       ("Interessi di mora", d[6]), ("Diritti /spese", d[7]), ("TOTALE CARTELLA", tot(d))):
            c.drawString(30, y, f"+ {lab}   {fmt(v)} +"); y -= 12
        totale += tot(d)
        c.showPage()
    c.setFont("Courier", 8)
    c.drawString(30, 800, "+ CARTELLA NR. 09720200000003333 000 Rateazione:N +")
    c.drawString(30, 788, f"+ *** TOTALE DEBITO {fmt(totale)} * +")
    c.showPage()
    c.save()
    return totale


if __name__ == "__main__":
    import sys
    genera(sys.argv[1])
