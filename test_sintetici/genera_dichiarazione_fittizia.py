"""Genera PDF di dichiarazione dei redditi FITTIZI per i test del parser (c). Nessun dato reale.

Impaginazione semplificata (una riga per rigo): non riproduce il modello ministeriale.
"""
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

QUI = Path(__file__).parent
PERIODO = "2025"
PAGINA = object()

# nome del file -> righe: (testo a sinistra, importo a destra o None)
DOCUMENTI = {
    "dichiarazione_fittizia_professionista.pdf": [
        ("QUADRO RE - Reddito di lavoro autonomo derivante dall'esercizio di arti e professioni", None),
        ("RE1 Codice attività 692011", None),
        ("RE2 Compensi derivanti dall'attività professionale o artistica", "82.000,00"),
        ("RE3 Altri proventi lordi", "3.000,00"),
        ("RE6 Totale compensi (sommare gli importi da rigo RE2 a RE5)", "85.000,00"),
        ("RE7 Quote di ammortamento e spese per l'acquisto di beni mobili", "4.200,00"),
        ("RE12 Compensi corrisposti a terzi per prestazioni afferenti l'attività", "6.000,00"),
        ("RE19 Altre spese documentate", "11.300,00"),
        ("RE20 Totale spese (sommare gli importi da rigo RE7 a RE19)", "21.500,00"),
        ("RE21 Differenza (RE6 - RE20)", "63.500,00"),
        ("RE23 Reddito (o perdita) delle attività professionali e artistiche", "63.500,00"),
        PAGINA,
        ("QUADRO RN - Determinazione dell'IRPEF", None),
        ("RN1 Reddito complessivo", "63.500,00"),
        ("RN4 Reddito imponibile", "58.900,00"),
        ("RN5 Imposta lorda", "17.500,00"),
        ("RN22 Totale detrazioni d'imposta", "1.250,00"),
        ("RN26 Imposta netta", "16.250,00"),
    ],
    # La differenza è volutamente sul rigo RG25 anziché RG26: deve risultare INFERENZA.
    "dichiarazione_fittizia_impresa.pdf": [
        ("QUADRO RG - Reddito di impresa in regime di contabilità semplificata", None),
        ("RG2 Ricavi di cui ai commi 1 (lett. a e b) e 2 dell'art. 85 del TUIR", "140.000,00"),
        ("RG10 Altri componenti positivi", "2.500,00"),
        ("RG12 Totale componenti positivi", "142.500,00"),
        ("RG15 Costi per l'acquisto di materie prime, sussidiarie, semilavorati e merci", "61.000,00"),
        ("RG16 Spese per lavoro dipendente e assimilato e per lavoro autonomo", "28.000,00"),
        ("RG22 Altri componenti negativi", "19.300,00"),
        ("RG24 Totale componenti negativi", "108.300,00"),
        ("RG25 Differenza (RG12 - RG24)", "34.200,00"),
        ("RG31 Reddito d'impresa lordo (o perdita)", "34.200,00"),
        PAGINA,
        ("QUADRO RN - Determinazione dell'IRPEF", None),
        ("RN1 Reddito complessivo", "34.200,00"),
        ("RN5 Imposta lorda", "8.100,00"),
        ("RN26 Imposta netta", "6.900,00"),
    ],
    "dichiarazione_fittizia_forfettario.pdf": [
        ("QUADRO LM - Sezione II - Regime forfetario", None),
        ("LM22 Codice attività 749099 Coefficiente di redditività 78% Componenti positivi 48.000,00 Reddito per attività 37.440,00", None),
        ("LM34 Reddito lordo", "37.440,00"),
        ("LM35 Contributi previdenziali e assistenziali", "9.800,00"),
        ("LM36 Reddito netto", "27.640,00"),
        ("LM38 Reddito al netto delle perdite soggetto ad imposta sostitutiva", "27.640,00"),
        ("LM39 Imposta sostitutiva 15%", "4.146,00"),
    ],
}

# Valori attesi dai test: nome del file -> {riga del foglio: valore}
ATTESI = {
    "dichiarazione_fittizia_professionista.pdf": {37: 85_000, 38: 21_500, 42: 16_250},
    "dichiarazione_fittizia_impresa.pdf": {37: 142_500, 38: 108_300, 42: 6_900},
    "dichiarazione_fittizia_forfettario.pdf": {47: 48_000, 48: 78, 52: 4_146},
}


def scrivi(percorso, righe):
    c = canvas.Canvas(str(percorso), pagesize=A4)
    c.setTitle("Dichiarazione fittizia per test")
    altezza = A4[1]

    def intestazione():
        c.setFont("Helvetica-Bold", 11)
        c.drawString(40, altezza - 45, f"MODELLO REDDITI PERSONE FISICHE - Periodo d'imposta {PERIODO}")
        c.setFont("Helvetica", 8)
        c.drawString(40, altezza - 58, "DOCUMENTO FITTIZIO - SOLO PER TEST - Contribuente: ROSSI FITTIZIO MARIO")

    intestazione()
    y = altezza - 90
    for riga in righe:
        if riga is PAGINA:
            c.showPage()
            intestazione()
            y = altezza - 90
            continue
        testo, importo = riga
        c.setFont("Helvetica-Bold" if testo.startswith("QUADRO") else "Helvetica", 8)
        c.drawString(40, y, testo)
        if importo:
            c.drawRightString(550, y, importo)
        y -= 14
    c.save()


def genera():
    for nome, righe in DOCUMENTI.items():
        scrivi(QUI / nome, righe)


if __name__ == "__main__":
    genera()
    print("Dichiarazioni fittizie generate in", QUI)
