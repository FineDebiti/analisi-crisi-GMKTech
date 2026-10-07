"""Costruzione di un .docx a partire dal modello CNC, senza librerie esterne: si riscrive solo il corpo del documento.

Si conservano stili, intestazione e piè di pagina del modello (Corpo, Intestazione, Intestazione 2, List Bullet).
"""
from __future__ import annotations

import re
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

COLORI = {  # sfondo, testo
    "VERDE": ("C6EFCE", "006100"), "GIALLO": ("FFEB9C", "7F6000"), "ROSSO": ("FFC7CE", "9C0006"), None: ("EDEDED", "404040"),
}
ETICHETTE = {"VERDE": "● VERDE", "GIALLO": "● GIALLO", "ROSSO": "● ROSSO", None: "○ N.D."}
BLU = "D9E2F3"
FONT = '<w:rFonts w:ascii="Aptos" w:cs="Aptos" w:hAnsi="Aptos" w:eastAsia="Aptos"/>'


def run(testo, grassetto=False, colore=None, dim=None, corsivo=False):
    rpr = FONT + ("<w:b/><w:bCs/>" if grassetto else "") + ("<w:i/><w:iCs/>" if corsivo else "")
    if colore:
        rpr += f'<w:color w:val="{colore}"/>'
    if dim:
        rpr += f'<w:sz w:val="{dim}"/><w:szCs w:val="{dim}"/>'
    return f'<w:r><w:rPr>{rpr}</w:rPr><w:t xml:space="preserve">{escape(str(testo))}</w:t></w:r>'


def par(contenuto, stile="Corpo", allinea=None, dopo=None, line=None, keep=False, salto=False, prima=None):
    if isinstance(contenuto, str) and not contenuto.startswith("<w:r"):
        contenuto = run(contenuto)
    sp = ""
    if dopo is not None or line is not None or prima is not None:
        sp = "<w:spacing" + (f' w:before="{prima}"' if prima is not None else "") + (f' w:after="{dopo}"' if dopo is not None else "") + (f' w:line="{line}" w:lineRule="auto"' if line is not None else "") + "/>"
    ppr = (f'<w:pStyle w:val="{stile}"/>' + ("<w:keepNext/>" if keep else "") + ("<w:pageBreakBefore/>" if salto else "") + sp
           + (f'<w:jc w:val="{allinea}"/>' if allinea else ""))
    return f"<w:p><w:pPr>{ppr}</w:pPr>{contenuto}</w:p>"


def testo(t, dim=19, dopo=60, grassetto=False, corsivo=False, keep=False):
    """Paragrafo compatto del corpo: carattere 9,5 pt, interlinea singola."""
    return par(run(t, grassetto=grassetto, corsivo=corsivo, dim=dim), "Corpo", dopo=dopo, line=250, keep=keep)


def misto(parti, dim=19, dopo=60):
    """parti: lista di (testo, grassetto)."""
    return par("".join(run(t, g, dim=dim) for t, g in parti), "Corpo", dopo=dopo, line=250)


def punto(t, dim=19):
    return par(run("\u2022 " + t, dim=dim), "Corpo", dopo=30, line=250)


def h1(t, salto=False):
    return par(run(t, grassetto=True, colore="365F91", dim=26), "Corpo", dopo=60, prima=160, keep=True, salto=salto)


def h2(t):
    return par(run(t, grassetto=True, colore="4F81BD", dim=21), "Corpo", dopo=40, prima=100, keep=True)


def titolo(testo):
    return par(run(testo, grassetto=True), "Intestazione")


def sottotitolo(testo):
    return par(run(testo, grassetto=True), "Intestazione 2")


def elenco(testo, stile="List Bullet"):
    return par(run(testo), stile)


def _cella(testo, larghezza, fill=None, colore=None, grassetto=False, allinea=None, dim=None, keep=False):
    shd = f'<w:shd w:val="clear" w:color="auto" w:fill="{fill}"/>' if fill else ""
    bordo = "".join(f'<w:{l} w:val="single" w:color="7F7F7F" w:sz="4" w:space="0"/>' for l in ("top", "left", "bottom", "right"))
    righe = str(testo).split("\n")
    corpo = "".join(par(run(r, grassetto=grassetto, colore=colore, dim=dim), "Corpo", allinea, dopo=0, line=(240 if dim else None), keep=keep) for r in righe)
    return (f'<w:tc><w:tcPr><w:tcW w:type="dxa" w:w="{larghezza}"/><w:tcBorders>{bordo}</w:tcBorders>{shd}'
            f'<w:tcMar><w:top w:type="dxa" w:w="{30 if dim else 60}"/><w:left w:type="dxa" w:w="80"/><w:bottom w:type="dxa" w:w="{30 if dim else 60}"/><w:right w:type="dxa" w:w="80"/></w:tcMar>'
            f'<w:vAlign w:val="center"/></w:tcPr>{corpo}</w:tc>')


def tabella(righe, larghezze, intestazione=True, colori=None, destra=(), dim=None, unita=True, grassetto_righe=()):
    """righe: lista di liste di testi. colori: {(riga, colonna): 'VERDE'|'GIALLO'|'ROSSO'|None}.
    dim: dimensione carattere (mezzi punti, es. 17 = 8,5 pt). unita=True: righe non spezzabili e tabella tenuta insieme nella pagina."""
    colori = colori or {}
    xml = ['<w:tbl><w:tblPr><w:tblW w:w="%d" w:type="dxa"/><w:jc w:val="center"/><w:tblLayout w:type="fixed"/></w:tblPr><w:tblGrid>' % sum(larghezze)]
    xml += [f'<w:gridCol w:w="{w}"/>' for w in larghezze]
    xml.append("</w:tblGrid>")
    n = len(righe)
    for i, riga in enumerate(righe):
        k = unita and i < n - 1 and (n <= 7 or i < 1)   # tabelle lunghe: si possono interrompere tra una riga e l'altra (la riga resta intera, l'intestazione si ripete)
        trpr = "<w:trPr><w:cantSplit/>" + ("<w:tblHeader/>" if intestazione and i == 0 else "") + "</w:trPr>"
        xml.append("<w:tr>" + trpr)
        for j, testo in enumerate(riga):
            if (i, j) in colori:
                fill, col = COLORI[colori[(i, j)]]
                xml.append(_cella(testo, larghezze[j], fill, col, grassetto=True, allinea="center", dim=dim, keep=k))
            elif intestazione and i == 0:
                xml.append(_cella(testo, larghezze[j], BLU, None, grassetto=True, dim=dim, keep=k))
            else:
                xml.append(_cella(testo, larghezze[j], None, None, i in grassetto_righe, "right" if j in destra else None, dim=dim, keep=k))
        xml.append("</w:tr>")
    xml.append("</w:tbl>")
    return "".join(xml) + par("", dopo=40, line=200)


def riquadro(titolo_txt, testo, colore):
    """Riquadro a colori con titolo (semaforo)."""
    fill, col = COLORI[colore]
    cella = (f'<w:tc><w:tcPr><w:tcW w:type="dxa" w:w="9700"/><w:shd w:val="clear" w:color="auto" w:fill="{fill}"/>'
             f'<w:tcBorders>' + "".join(f'<w:{l} w:val="single" w:color="{col}" w:sz="12" w:space="0"/>' for l in ("top", "left", "bottom", "right")) +
             f'</w:tcBorders><w:tcMar><w:top w:type="dxa" w:w="120"/><w:left w:type="dxa" w:w="160"/><w:bottom w:type="dxa" w:w="120"/><w:right w:type="dxa" w:w="160"/></w:tcMar></w:tcPr>'
             + par(run(titolo_txt, grassetto=True, colore=col, dim=28), "Corpo", dopo=60)
             + "".join(par(run(r, colore=col), "Corpo", dopo=40) for r in testo.split("\n")) + "</w:tc>")
    return f'<w:tbl><w:tblPr><w:tblW w:w="9700" w:type="dxa"/><w:jc w:val="center"/><w:tblLayout w:type="fixed"/></w:tblPr><w:tblGrid><w:gridCol w:w="9700"/></w:tblGrid><w:tr>{cella}</w:tr></w:tbl>' + par("", dopo=80)


def salva(modello, corpo_xml, uscita, a4=False):
    modello, uscita = Path(modello), Path(uscita)
    if uscita.exists():
        raise FileExistsError(f"esiste già {uscita.name}")
    with zipfile.ZipFile(modello) as z:
        doc = z.read("word/document.xml").decode("utf-8")
        sect = re.search(r"<w:sectPr.*?</w:sectPr>", doc, re.S).group(0)
        if a4:  # formato italiano A4 con margini ridotti; intestazione e piè di pagina del modello invariati
            sect = re.sub(r'<w:pgSz[^>]*/>', '<w:pgSz w:w="11906" w:h="16838" w:orient="portrait"/>', sect)
            sect = re.sub(r'<w:pgMar[^>]*/>', '<w:pgMar w:top="1000" w:right="900" w:bottom="850" w:left="900" w:header="500" w:footer="400"/>', sect)
        inizio = doc.index("<w:body>") + len("<w:body>")
        nuovo = doc[:inizio] + corpo_xml + sect + "</w:body></w:document>"
        with zipfile.ZipFile(uscita, "w", zipfile.ZIP_DEFLATED) as out:
            for info in z.infolist():
                dati = z.read(info.filename)
                if info.filename == "word/document.xml":
                    dati = nuovo.encode("utf-8")
                out.writestr(info.filename, dati)
    return uscita
