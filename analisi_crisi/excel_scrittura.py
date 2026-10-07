"""Scrittura in Excel (opzione B, HG-3): solo su una copia, solo nelle celle della whitelist.

Metodo approvato dal Boss: modifica diretta dell'XML del foglio dentro il file (nessuna libreria esterna).
Tutte le altre parti del file sono copiate byte per byte. Il piano (dry-run) non apre l'Excel e non contiene valori.
"""
import re
import zipfile
from pathlib import Path

from .comune import DA_VERIFICARE, FOGLIO

# Colonne C e D (anno -2, anno -1): righe di input del conto economico.
RIGHE_CD = frozenset({10, 11, 12, 14, 15, 16, 17, 19, 21, 23})
# Colonna E: solo i due blocchi regime delle dichiarazioni, uno per volta. Mai righe 40 e 50.
BLOCCO_ORDINARIO = frozenset({37, 38, 42})
BLOCCO_FORFETTARIO = frozenset({47, 48, 52})
RIGHE_AMMESSE = RIGHE_CD | BLOCCO_ORDINARIO | BLOCCO_FORFETTARIO
COLONNE_AMMESSE = frozenset({"C", "D", "E"})
SUFFISSO = "_COMPILATO"

# Modello AZIENDE (xlsx, fogli non protetti): righe di input per foglio, solo colonne C e D.
# La colonna E (anno corrente/previsionale) e le formule non si scrivono mai.
AZIENDE = {
    "bilancio_ce": frozenset({6, 7, 8, 11, 12, 13, 14, 17, 20, 21, 24, 25, 29}),
    "bilancio_sp": frozenset({7, 8, 9, 12, 13, 14, 15, 18, 23, 24, 25, 29, 30, 31, 32, 33, 34, 35, 36, 39}),
    # Elenco creditori (classe, creditore, natura, bene/garanzia, importo) e rapporto scaduto/attivo dell'allerta CCII.
    "passivo_creditori": frozenset(range(17, 42)),
    "allerta_ccii": frozenset({22}),
    "anagrafica_azienda": frozenset({6, 7, 9, 10, 11, 13, 16, 24}),
}
COLONNE_AZIENDE = {"bilancio_ce": "CD", "bilancio_sp": "CD", "passivo_creditori": "BCDEF", "allerta_ccii": "C", "anagrafica_azienda": "C"}

DA_SCRIVERE = "DA SCRIVERE"
SCRITTA = "SCRITTA"
ESCLUSA_COLONNA = "ESCLUSA: colonna fuori whitelist"
ESCLUSA_RIGA = "ESCLUSA: riga fuori whitelist"
ESCLUSA_REGIME = "ESCLUSA: i due blocchi regime non si compilano insieme"
NON_SCRITTA_STATO = "NON SCRITTA: DA VERIFICARE, serve l'approvazione in revisione"
NON_SCRITTA_VUOTA = "NON SCRITTA: nessun valore"
RIFIUTATA_FORMULA = "RIFIUTATA: la cella contiene una formula"
RIFIUTATA_BLOCCATA = "RIFIUTATA: cella bloccata in un foglio protetto"
RIFIUTATA_OCCUPATA = "RIFIUTATA: la cella contiene già un dato (non si sovrascrive)"
RIFIUTATA_ASSENTE = "RIFIUTATA: cella non presente nel foglio (stile ignoto)"

_M = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
_R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"


def _ammessa(colonna, riga):
    if colonna in ("C", "D"):
        return riga in RIGHE_CD
    return colonna == "E" and riga in (BLOCCO_ORDINARIO | BLOCCO_FORFETTARIO)


def _piano_aziende(r, approvate):
    voci = []
    for riga in r.get("modello_aziende", []):
        for colonna, c in sorted(riga["celle"].items()):
            cella = f"{riga['foglio']}!{colonna}{riga['riga']}"
            if colonna not in COLONNE_AZIENDE.get(riga["foglio"], "CD"):
                azione = ESCLUSA_COLONNA
            elif riga["riga"] not in AZIENDE.get(riga["foglio"], ()):
                azione = ESCLUSA_RIGA
            elif c["valore"] is None:
                azione = NON_SCRITTA_VUOTA
            elif c["stato"] == DA_VERIFICARE and cella not in approvate:
                azione = NON_SCRITTA_STATO
            else:
                azione = DA_SCRIVERE
            voci.append({"cella": cella, "campo": riga["voce"], "stato": c["stato"], "azione": azione, "valore": c["valore"]})
    return voci


def piano(r: dict, approvate=frozenset(), modello="traietti") -> list[dict]:
    """Dal JSON di un'estrazione all'elenco delle celle con l'azione prevista. `valore` non va mai stampato.

    `approvate`: celle DA VERIFICARE approvate dal Boss in revisione (file approvazioni.json).
    """
    if modello == "aziende":
        return _piano_aziende(r, approvate)
    voci = []
    for riga in sorted(r.get("foglio", []), key=lambda x: x["riga"]):
        for colonna, c in sorted(riga["celle"].items()):
            cella = f"{colonna}{riga['riga']}"
            if colonna not in COLONNE_AMMESSE:
                azione = ESCLUSA_COLONNA
            elif not _ammessa(colonna, riga["riga"]):
                azione = ESCLUSA_RIGA
            elif c["valore"] is None:
                azione = NON_SCRITTA_VUOTA
            elif c["stato"] == DA_VERIFICARE and cella not in approvate:
                azione = NON_SCRITTA_STATO
            else:
                azione = DA_SCRIVERE
            voci.append({"cella": cella, "campo": riga["voce"], "stato": c["stato"], "azione": azione, "valore": c["valore"]})
    # Un solo blocco regime per volta: se ce ne sono due con celle da scrivere, nessuno dei due si scrive.
    def blocco(v):
        return int(v["cella"][1:]) in BLOCCO_ORDINARIO, int(v["cella"][1:]) in BLOCCO_FORFETTARIO
    attivi = [v for v in voci if v["azione"] == DA_SCRIVERE and v["cella"][0] == "E"]
    if any(blocco(v)[0] for v in attivi) and any(blocco(v)[1] for v in attivi):
        for v in attivi:
            v["azione"] = ESCLUSA_REGIME
    return voci


def testo_piano(voci) -> str:
    """Tabella cella -> campo -> stato -> azione, senza valori."""
    righe = ["| Cella | Campo | Stato | Azione |", "|---|---|---|---|"]
    righe += [f"| {v['cella']} | {v['campo']} | {v['stato']} | {v['azione']} |" for v in voci]
    return "\n".join(righe) + "\n"


def percorso_copia(originale) -> Path:
    originale = Path(originale)
    return originale.with_name(originale.stem + SUFFISSO + originale.suffix)


def _parte_foglio(z, nome):
    import xml.etree.ElementTree as ET
    relazioni = {x.get("Id"): x.get("Target") for x in ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))}
    for s in ET.fromstring(z.read("xl/workbook.xml")).find(_M + "sheets"):
        if s.get("name") == nome:
            t = relazioni[s.get(_R + "id")]
            return t.lstrip("/") if t.startswith("/") else "xl/" + t
    raise KeyError(f"foglio {nome} non trovato")


def _stili_bloccati(z):
    """Per ogni indice di stile: True se le celle sono bloccate (predefinito di Excel)."""
    import xml.etree.ElementTree as ET
    if "xl/styles.xml" not in z.namelist():
        return []
    xfs = ET.fromstring(z.read("xl/styles.xml")).find(_M + "cellXfs")
    risultato = []
    for xf in ([] if xfs is None else xfs):
        p = xf.find(_M + "protection")
        risultato.append(not (p is not None and p.get("locked") in ("0", "false")))
    return risultato


def _occupata(corpo):
    """Cella con un dato dell'utente: testo, oppure numero diverso da zero."""
    if "<is>" in corpo:
        return bool(re.sub(r"<[^>]+>", "", corpo).strip())
    v = re.search(r"<v>(.*?)</v>", corpo)
    if not v or v.group(1) == "":
        return False
    try:
        return float(v.group(1)) != 0
    except ValueError:
        return True


def _contenuto(v):
    """XML del contenuto: numero oppure testo in linea (con escape)."""
    if isinstance(v, str):
        from xml.sax.saxutils import escape
        return "inlineStr", f'<is><t xml:space="preserve">{escape(v)}</t></is>'
    return None, f"<v>{_numero(v)}</v>"


def _numero(v):
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        raise ValueError("valore non numerico")
    return repr(v) if isinstance(v, float) else str(v)


def scrivi(voci, originale, copia, foglio_predefinito=FOGLIO) -> dict:
    """Crea la copia con le celle DA SCRIVERE aggiornate nell'XML. Restituisce rif -> valore scritto.

    Il rif è "C10" per il foglio predefinito, "foglio!C10" per gli altri (modelli con più fogli).
    """
    originale, copia = Path(originale), Path(copia)
    if copia.resolve() == originale.resolve():
        raise ValueError("la copia coincide con l'originale")
    if copia.exists():
        raise FileExistsError(f"esiste già {copia.name}: spostarlo o eliminarlo prima di riscrivere")
    scritte, nuovi_testi = {}, {}
    with zipfile.ZipFile(originale) as z:
        bloccati = _stili_bloccati(z)
        per_foglio = {}
        for v in voci:
            if v["azione"] == DA_SCRIVERE:
                nome, _, rif = v["cella"].rpartition("!")
                per_foglio.setdefault(nome or foglio_predefinito, []).append((v, rif))
        for nome, elenco in per_foglio.items():
            parte = _parte_foglio(z, nome)
            testo = z.read(parte).decode("utf-8")
            protetto = re.search(r'<sheetProtection[^>]*\ssheet="(1|true)"', testo) is not None
            for v, rif in elenco:
                m = re.search(r'<c r="%s"([^>]*?)(?:/>|>(.*?)</c>)' % rif, testo, re.S)
                if m is None:
                    v["azione"] = RIFIUTATA_ASSENTE
                    continue
                attributi, corpo = m.group(1), m.group(2) or ""
                stile = re.search(r'\ss="(\d+)"', attributi)
                if "<f" in corpo:
                    v["azione"] = RIFIUTATA_FORMULA
                elif protetto and (int(stile.group(1)) < len(bloccati) and bloccati[int(stile.group(1))] if stile else True):
                    v["azione"] = RIFIUTATA_BLOCCATA
                elif _occupata(corpo):
                    v["azione"] = RIFIUTATA_OCCUPATA
                else:
                    tipo, contenuto = _contenuto(v["valore"])
                    nuova = f'<c r="{rif}"{" s=" + chr(34) + stile.group(1) + chr(34) if stile else ""}{" t=" + chr(34) + tipo + chr(34) if tipo else ""}>{contenuto}</c>'
                    testo = testo[:m.start()] + nuova + testo[m.end():]
                    v["azione"] = SCRITTA
                    scritte[v["cella"]] = v["valore"]
            nuovi_testi[parte] = testo
        with zipfile.ZipFile(copia, "w") as nuovo:
            for info in z.infolist():
                dati = z.read(info.filename)
                if info.filename in nuovi_testi:
                    dati = nuovi_testi[info.filename].encode("utf-8")
                elif info.filename == "xl/workbook.xml":
                    dati = _ricalcolo(dati.decode("utf-8")).encode("utf-8")
                nuovo.writestr(info, dati, compress_type=info.compress_type)
    return scritte


def _ricalcolo(xml):
    """Chiede a Excel il ricalcolo completo all'apertura (i valori memorizzati delle formule sono superati)."""
    if "fullCalcOnLoad" in xml:
        return xml
    if re.search(r"<calcPr\b", xml):
        return re.sub(r"<calcPr\b", '<calcPr fullCalcOnLoad="1"', xml, count=1)
    m = re.search(r"<(oleSize|customWorkbookViews|pivotCaches|extLst)\b", xml)
    ins = '<calcPr fullCalcOnLoad="1"/>'
    return xml[:m.start()] + ins + xml[m.start():] if m else xml.replace("</workbook>", ins + "</workbook>")
