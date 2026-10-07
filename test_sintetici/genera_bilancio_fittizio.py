"""Genera PDF di bilancio abbreviato FITTIZI per i test del parser (a). Nessun dato reale."""
from pathlib import Path

from PIL import Image, ImageDraw
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

QUI = Path(__file__).parent
ESERCIZI = ("31-12-2025", "31-12-2024")
SOCIETA = "ALFA FITTIZIA S.R.L."
PAGINA = object()  # segnaposto: interruzione di pagina

# Componenti (2025, 2024). I totali sono calcolati, quindi il bilancio quadra per costruzione.
CE = {
    "A1": (1_250_000, 1_120_000), "A2": (6_000, -2_500), "A5": (18_500, 12_000),
    "B6": (520_000, 474_000), "B7": (210_300, 196_000), "B8": (48_000, 48_000),
    "B9a": (245_000, 232_000), "B9b": (73_500, 69_600), "B9c": (18_200, 17_100),
    "B10a": (4_000, 4_000), "B10b": (36_500, 35_000),
    "B11": (-8_400, 3_200), "B12": (5_000, 0), "B13": (2_000, 0), "B14": (14_900, 13_300),
    "C16": (350, 210), "C17": (21_850, 24_010), "D19": (1_000, 0), "I20": (23_100, 5_600),
}
ATTIVO = {
    "BI": (12_000, 16_000), "BII": (310_000, 322_000), "BIII": (5_000, 6_000),
    "CI": (104_400, 96_000), "CII_entro": (295_000, 270_000), "CII_oltre": (12_000, 12_000),
    "CIV": (61_300, 38_900), "D": (6_800, 5_900),
}
PASSIVO = {
    "AI": (50_000, 50_000), "AIV": (10_000, 6_000), "AVI": (86_400, 80_000),
    "B": (7_000, 0), "C": (92_000, 78_000), "D_oltre": (180_000, 215_000), "E": (4_200, 3_900),
}


def _colonna(i):
    v = {k: x[i] for k, x in {**CE, **ATTIVO, **{"P_" + k: x for k, x in PASSIVO.items()}}.items()}
    v["A"] = v["A1"] + v["A2"] + v["A5"]
    v["B9"] = v["B9a"] + v["B9b"] + v["B9c"]
    v["B10"] = v["B10a"] + v["B10b"]
    v["Btot"] = sum(v[k] for k in ("B6", "B7", "B8", "B9", "B10", "B11", "B12", "B13", "B14"))
    v["AB"] = v["A"] - v["Btot"]
    v["Ctot"] = v["C16"] - v["C17"]
    v["Dtot"] = -v["D19"]
    v["RAI"] = v["AB"] + v["Ctot"] + v["Dtot"]
    v["U21"] = v["RAI"] - v["I20"]
    v["Bimm"] = v["BI"] + v["BII"] + v["BIII"]
    v["CII"] = v["CII_entro"] + v["CII_oltre"]
    v["Ccirc"] = v["CI"] + v["CII"] + v["CIV"]
    v["TOT_ATTIVO"] = v["Bimm"] + v["Ccirc"] + v["D"]
    v["PN"] = v["P_AI"] + v["P_AIV"] + v["P_AVI"] + v["U21"]
    # Debiti entro l'esercizio: voce di chiusura, così attivo = passivo.
    v["P_D_entro"] = v["TOT_ATTIVO"] - v["PN"] - v["P_B"] - v["P_C"] - v["P_D_oltre"] - v["P_E"]
    v["P_D"] = v["P_D_entro"] + v["P_D_oltre"]
    v["TOT_PASSIVO"] = v["PN"] + v["P_B"] + v["P_C"] + v["P_D"] + v["P_E"]
    return v


def valori():
    """Tutti i valori del bilancio fittizio: chiave -> (2025, 2024)."""
    a, b = _colonna(0), _colonna(1)
    return {k: (a[k], b[k]) for k in a}


def _righe(anomalie=False):
    """Righe del documento: (testo o [righe di testo], chiave dei valori o None, rientro, grassetto)."""
    r = [
        ("Stato patrimoniale", None, 0, True),
        ("Attivo", None, 0, True),
        ("B) Immobilizzazioni", None, 1, False),
        ("I - Immobilizzazioni immateriali", "BI", 2, False),
        ("II - Immobilizzazioni materiali", "BII", 2, False),
        ("III - Immobilizzazioni finanziarie", "BIII", 2, False),
        ("Totale immobilizzazioni (B)", "Bimm", 2, True),
        ("C) Attivo circolante", None, 1, False),
        ("I - Rimanenze", "CI", 2, False),
        ("II - Crediti", None, 2, False),
        ("esigibili entro l'esercizio successivo", "CII_entro", 3, False),
        ("esigibili oltre l'esercizio successivo", "CII_oltre", 3, False),
        ("Totale crediti", "CII", 3, True),
        ("IV - Disponibilità liquide", "CIV", 2, False),
        ("Totale attivo circolante (C)", "Ccirc", 2, True),
        ("D) Ratei e risconti", "D", 1, False),
        ("Totale attivo", "TOT_ATTIVO", 1, True),
        PAGINA,
        ("Passivo", None, 0, True),
        ("A) Patrimonio netto", None, 1, False),
        ("I - Capitale", "P_AI", 2, False),
        ("IV - Riserva legale", "P_AIV", 2, False),
        ("VI - Altre riserve", "P_AVI", 2, False),
        ("IX - Utile (perdita) dell'esercizio", "U21", 2, False),
        ("Totale patrimonio netto", "PN", 2, True),
        ("B) Fondi per rischi e oneri", "P_B", 1, False),
        ("C) Trattamento di fine rapporto di lavoro subordinato", "P_C", 1, False),
        ("D) Debiti", None, 1, False),
        ("esigibili entro l'esercizio successivo", "P_D_entro", 2, False),
        ("esigibili oltre l'esercizio successivo", "P_D_oltre", 2, False),
        ("Totale debiti", "P_D", 2, True),
        ("E) Ratei e risconti", "P_E", 1, False),
        ("Totale passivo", "TOT_PASSIVO", 1, True),
        PAGINA,
        ("Conto economico", None, 0, True),
        ("A) Valore della produzione", None, 1, False),
        ("1) ricavi delle vendite e delle prestazioni", "A1", 2, False),
        (["2) variazioni delle rimanenze di prodotti in corso di lavorazione,", "semilavorati e finiti"], "A2", 2, False),
        ("5) altri ricavi e proventi", None, 2, False),
        ("altri", "A5", 3, False),
        ("Totale altri ricavi e proventi", "A5", 3, False),
        ("Totale valore della produzione", "A", 2, True),
        ("B) Costi della produzione", None, 1, False),
        ("6) per materie prime, sussidiarie, di consumo e di merci", "B6", 2, False),
        ("per servizi" if anomalie else "7) per servizi", "B7", 2, False),
        ("8) per godimento di beni di terzi", "B8", 2, False),
        ("9) per il personale", None, 2, False),
        ("a) salari e stipendi", "B9a", 3, False),
        ("b) oneri sociali", "B9b", 3, False),
        ("c) trattamento di fine rapporto", "B9c", 3, False),
        ("Totale costi per il personale", "B9", 3, False),
        ("10) ammortamenti e svalutazioni", None, 2, False),
        ("a) ammortamento delle immobilizzazioni immateriali", "B10a", 3, False),
        ("b) ammortamento delle immobilizzazioni materiali", "B10b", 3, False),
        ("Totale ammortamenti e svalutazioni", "B10", 3, False),
        # Etichetta lunga spezzata su due righe, con gli importi sulla seconda.
        (["11) variazioni delle rimanenze di materie prime, sussidiarie,", "di consumo e merci"], "B11", 2, False),
        ("12) accantonamenti per rischi", "B12", 2, False),
        ("13) altri accantonamenti", "B13", 2, False),
        ("14) oneri diversi di gestione", "B14", 2, False),
        ("Totale costi della produzione", "Btot_errato" if anomalie else "Btot", 2, True),
        ("Differenza tra valore e costi della produzione (A - B)", "AB", 1, True),
        ("C) Proventi e oneri finanziari", None, 1, False),
        ("16) altri proventi finanziari", None, 2, False),
        ("d) proventi diversi dai precedenti", None, 3, False),
        ("altri", "C16", 4, False),
        ("Totale proventi diversi dai precedenti", "C16", 4, False),
        ("Totale altri proventi finanziari", "C16", 3, False),
        ("17) interessi e altri oneri finanziari", None, 2, False),
        ("altri", "C17", 3, False),
        ("Totale interessi e altri oneri finanziari", "C17", 3, False),
        ("Totale proventi e oneri finanziari (15 + 16 - 17 + - 17-bis)", "Ctot", 2, True),
        ("D) Rettifiche di valore di attività e passività finanziarie", None, 1, False),
        ("19) svalutazioni", None, 2, False),
        ("a) di partecipazioni", "D19", 3, False),
        ("Totale svalutazioni", "D19", 3, False),
        (["Totale delle rettifiche di valore di attività e passività", "finanziarie (18 - 19)"], "Dtot", 2, True),
        ("Risultato prima delle imposte (A - B + - C + - D)", "RAI", 1, True),
        ("20) Imposte sul reddito dell'esercizio, correnti, differite e anticipate", None, 1, False),
        ("imposte correnti", "I20", 2, False),
        (["Totale delle imposte sul reddito dell'esercizio, correnti,", "differite e anticipate"], "I20", 2, False),
        ("21) Utile (perdita) dell'esercizio", "U21", 1, True),
    ]
    return r


def _fmt(n):
    s = f"{abs(n):,}".replace(",", ".")
    return f"({s})" if n < 0 else s


def scrivi_bilancio(percorso, anomalie=False):
    v = valori()
    v["Btot_errato"] = (v["Btot"][0] + 1_000, v["Btot"][1])  # totale 2025 volutamente sbagliato
    righe = _righe(anomalie)
    n_pagine = 1 + sum(1 for x in righe if x is PAGINA)
    c = canvas.Canvas(str(percorso), pagesize=A4)
    c.setTitle("Bilancio fittizio per test")
    larghezza, altezza = A4

    def intestazione(n):
        c.setFont("Helvetica-Bold", 11)
        c.drawString(50, altezza - 45, SOCIETA)
        c.setFont("Helvetica", 8)
        c.drawString(50, altezza - 58, "DOCUMENTO FITTIZIO - SOLO PER TEST - Bilancio abbreviato art. 2435-bis c.c.")
        c.setFont("Helvetica-Bold", 9)
        c.drawRightString(450, altezza - 80, ESERCIZI[0])
        c.drawRightString(540, altezza - 80, ESERCIZI[1])
        c.setFont("Helvetica", 7)
        c.drawString(50, 40, f"Bilancio di esercizio al {ESERCIZI[0]} Pag. {n} di {n_pagine}")
        c.drawString(50, 30, "Generato automaticamente - Documento di prova senza valore legale")

    n = 1
    intestazione(n)
    y = altezza - 100
    for riga in righe:
        if riga is PAGINA:
            c.showPage()
            n += 1
            intestazione(n)
            y = altezza - 100
            continue
        testo, chiave, rientro, grassetto = riga
        c.setFont("Helvetica-Bold" if grassetto else "Helvetica", 9)
        linee = testo if isinstance(testo, list) else [testo]
        for k, linea in enumerate(linee):
            c.drawString(50 + 12 * rientro, y, linea)
            if chiave and k == len(linee) - 1:
                c.drawRightString(450, y, _fmt(v[chiave][0]))
                c.drawRightString(540, y, _fmt(v[chiave][1]))
            y -= 13
    c.save()


def scrivi_scansione(percorso):
    """PDF di sola immagine, senza testo estraibile, come una scansione."""
    img = Image.new("RGB", (620, 877), "white")
    ImageDraw.Draw(img).text((60, 60), "SCANSIONE FITTIZIA - SOLO PER TEST", fill="black")
    c = canvas.Canvas(str(percorso), pagesize=A4)
    c.drawInlineImage(img, 0, 0, width=A4[0], height=A4[1])
    c.save()


def genera():
    scrivi_bilancio(QUI / "bilancio_abbreviato_fittizio.pdf")
    scrivi_bilancio(QUI / "bilancio_abbreviato_fittizio_anomalie.pdf", anomalie=True)
    scrivi_scansione(QUI / "scansione_fittizia.pdf")


if __name__ == "__main__":
    genera()
    print("PDF fittizi generati in", QUI)
