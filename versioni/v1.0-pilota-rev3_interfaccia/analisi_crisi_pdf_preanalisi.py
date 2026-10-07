"""PDF A4 della preanalisi provvisoria (reportlab, nessun programma esterno: sul Mac non c'è LibreOffice).

Intestazione "PREANALISI PROVVISORIA" su ogni pagina, stato di approvazione, versione del motore, impronta dei parametri.
Se non approvata: dicitura ben visibile "NON APPROVATA - bozza". Supporto alla decisione, non attestazione.
"""
from __future__ import annotations

import io
from xml.sax.saxutils import escape

from analisi_crisi import pratica as _pr
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import BaseDocTemplate, Frame, PageTemplate, Paragraph, Spacer, Table, TableStyle

ROSSO, VERDE, GRIGIO = colors.HexColor("#b3261e"), colors.HexColor("#1b7a3d"), colors.HexColor("#5b665f")
COL = {"VERDE": colors.HexColor("#d9efdf"), "GIALLO": colors.HexColor("#fbeec6"), "ROSSO": colors.HexColor("#f6d3d0")}
S = {
    "n": ParagraphStyle("n", fontName="Helvetica", fontSize=9, leading=12),
    "p": ParagraphStyle("p", fontName="Helvetica", fontSize=8, leading=10),
    "b": ParagraphStyle("b", fontName="Helvetica-Bold", fontSize=9, leading=12),
    "h": ParagraphStyle("h", fontName="Helvetica-Bold", fontSize=11.5, leading=15, spaceBefore=10, spaceAfter=4, keepWithNext=1, textColor=colors.HexColor("#1f5f4a")),
    "av": ParagraphStyle("av", fontName="Helvetica-Bold", fontSize=10, leading=13, textColor=ROSSO, borderColor=ROSSO, borderWidth=1, borderPadding=5, spaceAfter=8),
}


def _t(x):
    s = "" if x is None else str(x)
    return escape(s) if s.strip() else "-"


def _p(x, stile="n"):
    return Paragraph(_t(x).replace("\n", "<br/>"), S[stile])


def _tab(intest, righe, larg, colori=None):
    dati = [[_p(h, "b") for h in intest]] + [[_p(c, "p") for c in r] for r in righe]
    t = Table(dati, colWidths=[l * mm for l in larg], repeatRows=1, splitInRow=1)
    st = [("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#b8c2bb")), ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e6ece8")),
          ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 3), ("RIGHTPADDING", (0, 0), (-1, -1), 3)]
    for (r, c), colore in (colori or {}).items():
        if colore in COL:
            st.append(("BACKGROUND", (c, r), (c, r), COL[colore]))
    t.setStyle(TableStyle(st))
    return t


def genera(d, appr, aggiornata=True, dati_testo=None):
    """d: preanalisi (dict di pratica.ultima_preanalisi); appr: dict di dati_pratica.approvazione(); ritorna i byte del PDF."""
    approvata = appr.get("stato") == "APPROVATA"
    if approvata:
        stato = "APPROVATA COME PROVVISORIA da %s il %s" % (appr.get("approvata_da"), (appr.get("approvata_il") or "")[:16].replace("T", " "))
    else:
        stato = "NON APPROVATA - bozza"
    ric = d["tipo"] == "RICOGNIZIONE_FASCICOLO"

    def testata(c, doc):
        c.saveState()
        w, h = A4
        c.setFont("Helvetica-Bold", 16)
        c.setFillColor(colors.HexColor("#1f5f4a"))
        c.drawString(18 * mm, h - 14 * mm, "PREANALISI PROVVISORIA")
        c.setFont("Helvetica-Bold", 10.5 if approvata else 12)
        c.setFillColor(VERDE if approvata else ROSSO)
        c.drawString(18 * mm, h - 21 * mm, stato)
        c.setFont("Helvetica", 7.5)
        c.setFillColor(GRIGIO)
        c.drawString(18 * mm, h - 26 * mm, "Motore: %s (%s) - Impronta parametri: %s" % (d["versione_motore"], _pr.versione.REVISIONE.split(" - ")[0], d["impronta"][:24] + "..."))
        c.line(18 * mm, h - 28 * mm, w - 18 * mm, h - 28 * mm)
        c.drawString(18 * mm, 10 * mm, "Pratica: %s - supporto alla decisione, non attestazione" % str(d["pratica"])[:60])
        c.drawRightString(w - 18 * mm, 10 * mm, "Pagina %d" % doc.page)
        c.restoreState()

    buf = io.BytesIO()
    doc = BaseDocTemplate(buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=33 * mm, bottomMargin=16 * mm,
                          title="Preanalisi provvisoria - " + str(d["pratica"]), author="ANALISI CRISI")
    doc.addPageTemplates([PageTemplate(id="p", frames=[Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="f")], onPage=testata)])
    E = []
    if not approvata:
        E.append(Paragraph("NON APPROVATA - bozza. Questo documento non è stato approvato dal titolare" + (
            (": l'approvazione precedente di %s è decaduta (%s)." % (escape(str(appr.get("approvata_da"))), escape(str(appr.get("motivo"))))) if appr.get("decaduta") else "."), S["av"]))
    if not aggiornata:
        E.append(Paragraph("ATTENZIONE: i dati sono stati modificati dopo la generazione di questa preanalisi. Rigenerarla prima di usarla.", S["av"]))
    con0 = d["sufficienza"]["per_concludere"]
    E += [Paragraph(_t("Ricognizione del fascicolo" if ric else "Preanalisi provvisoria") + " - " + _t(d["pratica"]), S["h"]),
          _p(_pr.dicitura(d, approvata), "b"), _p("Elaborazione del %s. Tutti i giudizi sono %s e non costituiscono attestazione." % (str(d["generata_il"])[:16].replace("T", " "), "PRELIMINARE / PROVVISORIO"))]
    E.append(Paragraph("1. Limiti informativi", S["h"]))
    for l in d["limiti_informativi"] or ["Nessun limite informativo rilevante."]:
        E.append(Paragraph("- " + _t(l), S["n"]))
    E.append(Paragraph("2. Quattro riquadri", S["h"]))
    r = d["riquadri"]
    righe, colori = [], {}
    for i, k in enumerate(("sostenibilita", "qualita_dati", "fattibilita", "stato_conclusione"), 1):
        q = r[k]
        righe.append([q["titolo"], "PROVVISORIA" if k == "stato_conclusione" else q["esito"], q["esito"] if k == "stato_conclusione" else q.get("dettaglio", "")])
        colori[(i, 1)] = q.get("colore") or (q["esito"] if k == "sostenibilita" else None)
    E.append(_tab(["Riquadro", "Esito", "Dettaglio"], righe, [52, 34, 88], colori))
    ini, con = d["sufficienza"]["per_iniziare"], d["sufficienza"]["per_concludere"]
    E.append(Paragraph("3. Indicatori di sufficienza", S["h"]))
    E.append(_tab(["Indicatore", "Esito", "Dettaglio"], [
        ["Sufficienza per INIZIARE", "SI", "Si può valutare: " + ("; ".join(ini["valutabile"]) or "solo la ricognizione del fascicolo") + ". Non si può valutare: " + ("; ".join(ini["non_valutabile"]) or "nulla di rilevante") + "."],
        ["Sufficienza per CONCLUDERE", "SI" if con["ok"] else "NO", "; ".join(con.get("motivi_brevi", con["motivi"])) or "Nessun ostacolo noto."]], [52, 22, 100],
        {(1, 1): "VERDE", (2, 1): "VERDE" if con["ok"] else "GIALLO"}))
    E.append(Paragraph("4. Calcoli e giudizi preliminari", S["h"]))
    E.append(_tab(["Calcolo", "Stato", "Valore", "Esito", "Periodo"], [[s["sezione"], s["stato"], s["valore"], s.get("esito") or "-", s.get("periodo") or "-"] for s in d["sezioni"]], [62, 30, 30, 24, 28],
                  {(i + 1, 3): s.get("esito") for i, s in enumerate(d["sezioni"])}))
    E.append(Paragraph("5. Dati e fonti", S["h"]))
    E.append(_tab(["Dato", "Valore", "Periodo", "Stato", "Fonte", "Pag."], [[x["dato"], _pr.eur(x["valore"]) if x["unita"] == "EUR" else x["valore"], x.get("periodo") or "-", x["natura"], x["fonte"], x["pagina"]] for x in d["dati_estratti"]],
                  [56, 28, 22, 22, 34, 12]) if d["dati_estratti"] else _p("Nessun dato registrato: nessun valore è stato assunto o sostituito con zero."))
    E.append(Paragraph("6. Scenari (motivazioni dettagliate, riportate una sola volta)", S["h"]))
    E.append(_tab(["Scenario", "Stato", "Motivo"], [[x["scenario"], x["stato"], "\n".join("- " + m for m in x["motivo"])] for x in d["scenari"]], [44, 34, 96]))
    E.append(Paragraph("6-bis. Documenti e situazioni (ricevuti, mancanti, non pertinenti, inesistenti)", S["h"]))
    righe_doc = [[v["id"] + " " + v["etichetta"], v["stato"], ("non applicabile" if v["stato"] in ("non pertinente", "inesistente") else ("richiesto ora" if v["suggerita"] else "non richiesto"))] for g in ("A", "B") for v in d["checklist"][g]
                 if g == "A" or v["suggerita"] or v["stato"] != "mancante"]
    E.append(_tab(["Voce", "Stato", "Rilevanza"], righe_doc, [110, 34, 30]))
    E.append(Paragraph("7. Criticità e incongruenze", S["h"]))
    E.append(_tab(["Tipo", "Descrizione", "Gravità", "Stato"], [[x["tipo"], x["testo"], x["gravita"], x["stato"]] for x in d["criticita"]], [34, 94, 24, 22])
             if d["criticita"] else _p("Nessuna criticità o incongruenza rilevata con i dati disponibili."))
    E.append(Paragraph("8. Richieste documentali prioritarie (massimo 5)", S["h"]))
    E.append(_tab(["#", "Richiesta", "Che cosa permetterà di verificare"], [[x["ordine"], x["richiesta"], x["permette_di_verificare"]] for x in d["richieste_prioritarie"]], [8, 90, 76])
             if d["richieste_prioritarie"] else _p("Nessuna richiesta prioritaria."))
    E.append(Spacer(1, 6))
    E.append(_p("Versione del motore: %s - impronta dei parametri: %s" % (d["versione_motore"], d["impronta"]), "p"))
    doc.build(E)
    return buf.getvalue()
