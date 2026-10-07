"""Genera un xlsm FITTIZIO per i test della scrittura in Excel. Nessun dato reale, solo libreria standard.

Struttura ricostruita (non copiata dall'Excel reale): fogli protetti, `impostazioni` nascosto,
`_licenza` veryHidden, cartella protetta, macro finta (vbaProject.bin non valido: Excel potrebbe non aprirlo),
un pulsante collegato alla macro, formule (una condivisa) e celle manuali già compilate.
"""
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

QUI = Path(__file__).parent
NOME = "Fittizio.xlsm"
MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG = "http://schemas.openxmlformats.org/package/2006/relationships"
PROTEZIONE = '<sheetProtection password="CC1A" sheet="1" objects="1" scenarios="1"/>'

# (nome, stato). L'ordine è quello delle schede.
FOGLI = [("dashboard", None), ("anagrafica", None), ("flussi_cassa_impresa", None), ("passivo", None),
         ("impostazioni", "hidden"), ("_licenza", "veryHidden")]

INPUT = {10: "Ricavi netti", 11: "Variazione rimanenze", 12: "Altri ricavi operativi", 14: "Materie prime", 15: "Servizi",
         16: "Personale", 17: "Altri costi operativi", 19: "Ammortamenti e svalutazioni", 21: "Oneri/proventi finanziari netti",
         23: "Imposte", 37: "Compensi/ricavi", 38: "Costi", 42: "IRPEF netta", 47: "Ricavi", 48: "Coefficiente", 52: "Imposta sostitutiva"}
MANUALI = {28: "Variazione CCN", 29: "Capex", 30: "Rimborso debiti", 32: "Oneri finanziari netti di cassa",
           40: "Contributi previdenziali", 50: "Contributi previdenziali"}
# {col} viene sostituito con la lettera della colonna.
FORMULE = {13: "SUM({col}10:{col}12)", 18: "SUM({col}14:{col}17)", 20: "{col}13-{col}18", 22: "{col}20-{col}19+{col}21",
           24: "{col}22-{col}23", 31: "{col}24+{col}19-{col}28-{col}29-{col}30", 33: "{col}31-{col}32",
           39: "{col}37-{col}38", 41: "{col}39-{col}40", 43: "{col}41-{col}42", 49: "{col}47*{col}48/100",
           51: "{col}49-{col}50", 53: "{col}51-{col}52", 57: "{col}33", 58: "{col}43", 59: "{col}53"}
ETICHETTE_FORMULE = {13: "Valore della produzione", 18: "Totale costi operativi", 20: "Margine", 22: "Risultato ante imposte",
                     24: "Utile", 31: "Flusso operativo", 33: "Flusso netto", 39: "Reddito", 41: "Reddito netto", 43: "Disponibile",
                     49: "Reddito forfetario", 51: "Reddito netto", 53: "Disponibile", 57: "Sintesi ordinario",
                     58: "Sintesi semplificata", 59: "Sintesi forfetario"}
# Celle già compilate a mano: non devono cambiare.
PRECOMPILATE = {"C28": 1500, "D28": 1700, "D32": 900, "E10": 123456, "E14": 50000}
COLONNE = ("C", "D", "E")


class _Stringhe:
    def __init__(self):
        self.indice = {}

    def __call__(self, testo):
        return self.indice.setdefault(testo, len(self.indice))

    def xml(self):
        voci = "".join(f"<si><t>{escape(t)}</t></si>" for t in self.indice)
        return f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><sst xmlns="{MAIN}" count="{len(self.indice)}" uniqueCount="{len(self.indice)}">{voci}</sst>'


def _foglio(righe_xml, codice, extra=""):
    return (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><worksheet xmlns="{MAIN}" xmlns:r="{REL}">'
            f'<sheetPr codeName="{codice}"/><sheetData>{righe_xml}</sheetData>{PROTEZIONE}'
            f'<pageMargins left="0.7" right="0.7" top="0.75" bottom="0.75" header="0.3" footer="0.3"/>{extra}</worksheet>')


def _flussi(s):
    righe = [f'<row r="8"><c r="B8" t="s"><v>{s("Voce")}</v></c><c r="C8" t="s"><v>{s("Anno -2")}</v></c>'
             f'<c r="D8" t="s"><v>{s("Anno -1")}</v></c><c r="E8" t="s"><v>{s("Previsionale")}</v></c></row>']
    for n in sorted({**INPUT, **MANUALI, **FORMULE}):
        etichetta = INPUT.get(n) or MANUALI.get(n) or ETICHETTE_FORMULE[n]
        celle = [f'<c r="B{n}" t="s"><v>{s(etichetta)}</v></c>']
        for col in COLONNE:
            rif = f"{col}{n}"
            if n in FORMULE:
                if n == 13:  # formula condivisa: il testo sta solo nella prima cella
                    f = '<f t="shared" ref="C13:E13" si="0">SUM(C10:C12)</f>' if col == "C" else '<f t="shared" si="0"/>'
                else:
                    f = f"<f>{FORMULE[n].format(col=col)}</f>"
                celle.append(f'<c r="{rif}">{f}<v>0</v></c>')
            elif rif in PRECOMPILATE:
                celle.append(f'<c r="{rif}" s="1"><v>{PRECOMPILATE[rif]}</v></c>')
            else:
                celle.append(f'<c r="{rif}" s="1"/>')  # cella di input vuota e sbloccata
        righe.append(f'<row r="{n}">{"".join(celle)}</row>')
    return _foglio("".join(righe), "Foglio3")


def _semplice(s, codice, celle, extra=""):
    righe = "".join(
        f'<row r="{i}"><c r="A{i}" t="s"><v>{s(a)}</v></c>' + (f'<c r="B{i}"><v>{b}</v></c>' if isinstance(b, int) else f'<c r="B{i}" t="s"><v>{s(b)}</v></c>') + "</row>"
        for i, (a, b) in enumerate(celle, 1)
    )
    return _foglio(righe, codice, extra)


_VML = """<xml xmlns:v="urn:schemas-microsoft-com:vml" xmlns:o="urn:schemas-microsoft-com:office:office" xmlns:x="urn:schemas-microsoft-com:office:excel">
<o:shapelayout v:ext="edit"><o:idmap v:ext="edit" data="1"/></o:shapelayout>
<v:shapetype id="_x0000_t201" coordsize="21600,21600" o:spt="201" path="m,l,21600r21600,l21600,xe"><v:stroke joinstyle="miter"/><v:path shadowok="f" o:extrusionok="f" strokeok="f" fillok="f" o:connecttype="rect"/><o:lock v:ext="edit" shapetype="t"/></v:shapetype>
<v:shape id="_x0000_s1025" type="#_x0000_t201" style="position:absolute;margin-left:60pt;margin-top:30pt;width:120pt;height:24pt;z-index:1" o:button="t" fillcolor="buttonFace [67]" strokecolor="windowText [64]" o:insetmode="auto">
<v:fill color2="buttonFace [67]" o:detectmouseclick="t"/><o:lock v:ext="edit" rotation="t"/>
<v:textbox><div style="text-align:center"><font face="Calibri" size="220" color="#000000">Genera report</font></div></v:textbox>
<x:ClientData ObjectType="Button"><x:Anchor>1, 0, 2, 0, 3, 0, 4, 0</x:Anchor><x:PrintObject>False</x:PrintObject><x:AutoFill>False</x:AutoFill><x:FmlaMacro>[0]!MacroFittizia</x:FmlaMacro><x:TextHAlign>Center</x:TextHAlign><x:TextVAlign>Center</x:TextVAlign></x:ClientData>
</v:shape></xml>"""

_STILI = (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><styleSheet xmlns="{MAIN}">'
          '<fonts count="1"><font><sz val="11"/><name val="Calibri"/></font></fonts>'
          '<fills count="2"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill></fills>'
          '<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>'
          '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
          '<cellXfs count="2"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>'
          '<xf numFmtId="3" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1" applyProtection="1"><protection locked="0"/></xf></cellXfs>'
          '<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles></styleSheet>')


def genera(percorso=None):
    percorso = Path(percorso or QUI / NOME)
    s = _Stringhe()
    fogli_xml = [
        _semplice(s, "Foglio1", [("Cruscotto fittizio", "solo per test")], extra='<legacyDrawing r:id="rId1"/>'),
        _semplice(s, "Foglio2", [("Denominazione", "ALFA FITTIZIA S.R.L."), ("Codice fiscale", "00000000000")]),
        _flussi(s),
        _semplice(s, "Foglio4", [("Creditore", "Importo"), ("Creditore fittizio", 1000)]),
        _semplice(s, "Foglio5", [("Parametro", "Valore"), ("Anno base", 2025)]),
        _semplice(s, "Foglio6", [("Licenza", "FITTIZIA-0000")]),
    ]
    schede = "".join(
        f'<sheet name="{nome}" sheetId="{i}"' + (f' state="{stato}"' if stato else "") + f' r:id="rId{i}"/>'
        for i, (nome, stato) in enumerate(FOGLI, 1)
    )
    cartella = (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><workbook xmlns="{MAIN}" xmlns:r="{REL}">'
                '<fileVersion appName="xl"/><workbookPr codeName="ThisWorkbook"/>'
                '<workbookProtection workbookPassword="CC1A" lockStructure="1"/><bookViews><workbookView/></bookViews>'
                f'<sheets>{schede}</sheets><definedNames><definedName name="AnnoBase">impostazioni!$B$2</definedName></definedNames>'
                '<calcPr calcId="191029"/></workbook>')
    n = len(FOGLI)
    rel_cartella = "".join(f'<Relationship Id="rId{i}" Type="{REL}/worksheet" Target="worksheets/sheet{i}.xml"/>' for i in range(1, n + 1))
    rel_cartella += (f'<Relationship Id="rId{n + 1}" Type="{REL}/styles" Target="styles.xml"/>'
                     f'<Relationship Id="rId{n + 2}" Type="{REL}/sharedStrings" Target="sharedStrings.xml"/>'
                     f'<Relationship Id="rId{n + 3}" Type="http://schemas.microsoft.com/office/2006/relationships/vbaProject" Target="vbaProject.bin"/>')
    tipi = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Default Extension="bin" ContentType="application/vnd.ms-office.vbaProject"/>'
            '<Default Extension="vml" ContentType="application/vnd.openxmlformats-officedocument.vmlDrawing"/>'
            '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.ms-excel.sheet.macroEnabled.main+xml"/>'
            + "".join(f'<Override PartName="/xl/worksheets/sheet{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>' for i in range(1, n + 1))
            + '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
            '<Override PartName="/xl/sharedStrings.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"/></Types>')

    def rel(contenuto):
        return f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="{PKG}">{contenuto}</Relationships>'

    with zipfile.ZipFile(percorso, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", tipi)
        z.writestr("_rels/.rels", rel(f'<Relationship Id="rId1" Type="{REL}/officeDocument" Target="xl/workbook.xml"/>'))
        z.writestr("xl/workbook.xml", cartella)
        z.writestr("xl/_rels/workbook.xml.rels", rel(rel_cartella))
        for i, xml in enumerate(fogli_xml, 1):
            z.writestr(f"xl/worksheets/sheet{i}.xml", xml)
        z.writestr("xl/worksheets/_rels/sheet1.xml.rels", rel(f'<Relationship Id="rId1" Type="{REL}/vmlDrawing" Target="../drawings/vmlDrawing1.vml"/>'))
        z.writestr("xl/drawings/vmlDrawing1.vml", _VML)
        z.writestr("xl/styles.xml", _STILI)
        z.writestr("xl/sharedStrings.xml", s.xml())
        z.writestr("xl/vbaProject.bin", b"VBA FITTIZIO PER TEST - non e' un progetto VBA valido\n" * 20)
    return percorso


if __name__ == "__main__":
    print("Excel fittizio generato:", genera())
