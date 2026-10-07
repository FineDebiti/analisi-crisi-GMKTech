"""Controlli dopo la scrittura in Excel: confronto tra originale e copia. Solo libreria standard, esito SENZA valori.

Indipendente dalla libreria che scrive: legge direttamente l'XML dentro i due file.
"""
import hashlib
import re
import xml.etree.ElementTree as ET
import zipfile

from .comune import KO, OK

AVVISO = "AVVISO"
_M = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
_R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
CONDIVISA = "(condivisa)"
VBA = "xl/vbaProject.bin"
# Parti la cui perdita rompe il file: pulsanti e controlli, immagini, grafici, oggetti incorporati.
_PARTI_CRITICHE = re.compile(r"xl/(drawings|ctrlProps|media|activeX|charts|embeddings|customUI)/|^customUI/")
# Valori predefiniti dello schema: una protezione riscritta per esteso equivale a quella originale.
_PREDEFINITI_FOGLIO = {
    "sheet": "0", "objects": "0", "scenarios": "0", "formatCells": "1", "formatColumns": "1", "formatRows": "1",
    "insertColumns": "1", "insertRows": "1", "insertHyperlinks": "1", "deleteColumns": "1", "deleteRows": "1",
    "selectLockedCells": "0", "sort": "1", "autoFilter": "1", "pivotTables": "1", "selectUnlockedCells": "0",
}
_PREDEFINITI_CARTELLA = {"lockStructure": "0", "lockWindows": "0", "lockRevision": "0"}


def impronta(percorso) -> str:
    return hashlib.sha256(open(percorso, "rb").read()).hexdigest()


def _protezione(elemento, predefiniti):
    if elemento is None:
        return None
    attributi = {**predefiniti, **elemento.attrib}
    return {k: {"true": "1", "false": "0"}.get(v, v) for k, v in attributi.items()}


def _celle(foglio, stringhe):
    """rif -> ("f", testo della formula) oppure ("v", valore). Le celle vuote non compaiono."""
    celle = {}
    for c in foglio.iter(_M + "c"):
        f, v, tipo = c.find(_M + "f"), c.find(_M + "v"), c.get("t", "n")
        if f is not None:
            celle[c.get("r")] = ("f", (f.text or "").strip() or CONDIVISA)
        elif tipo == "inlineStr":
            testo = "".join(t.text or "" for t in c.iter(_M + "t"))
            if testo:
                celle[c.get("r")] = ("v", testo)
        elif v is not None and v.text not in (None, ""):
            if tipo == "s":
                celle[c.get("r")] = ("v", stringhe[int(v.text)])
            elif tipo == "n":
                celle[c.get("r")] = ("v", float(v.text))
            else:
                celle[c.get("r")] = ("v", v.text)
    return celle


def leggi(percorso) -> dict:
    """Struttura della cartella: fogli (stato, protezione, celle), protezione, nomi definiti, parti, hash del VBA."""
    with zipfile.ZipFile(percorso) as z:
        parti = set(z.namelist())
        cartella = ET.fromstring(z.read("xl/workbook.xml"))
        relazioni = {r.get("Id"): r.get("Target") for r in ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))}
        stringhe = []
        if "xl/sharedStrings.xml" in parti:
            for si in ET.fromstring(z.read("xl/sharedStrings.xml")).findall(_M + "si"):
                stringhe.append("".join(t.text or "" for t in si.iter(_M + "t")))
        fogli = {}
        for s in cartella.find(_M + "sheets"):
            destinazione = relazioni[s.get(_R + "id")]
            parte = destinazione.lstrip("/") if destinazione.startswith("/") else "xl/" + destinazione
            foglio = ET.fromstring(z.read(parte))
            fogli[s.get("name")] = {
                "stato": s.get("state", "visible"),
                "protezione": _protezione(foglio.find(_M + "sheetProtection"), _PREDEFINITI_FOGLIO),
                "celle": _celle(foglio, stringhe),
            }
        nomi = cartella.find(_M + "definedNames")
        return {
            "fogli": fogli,
            "protezione": _protezione(cartella.find(_M + "workbookProtection"), _PREDEFINITI_CARTELLA),
            "nomi": {} if nomi is None else {n.get("name"): (n.text or "") for n in nomi},
            "parti": parti,
            "vba": hashlib.sha256(z.read(VBA)).hexdigest() if VBA in parti else None,
        }


def _formule_uguali(a, b):
    # Una formula condivisa può essere riscritta come formula singola: si verifica solo che resti una formula.
    return a[1] == b[1] or CONDIVISA in (a[1], b[1])


def confronta(originale, copia, foglio, scritte: dict) -> list[dict]:
    """Controlli post-scrittura. `scritte`: rif -> valore che doveva essere scritto nel foglio indicato."""
    o, c = leggi(originale), leggi(copia)
    esiti = []

    def esito(nome, ok, dettaglio="", grave=True):
        esiti.append({"controllo": nome, "esito": OK if ok else (KO if grave else AVVISO), "dettaglio": "" if ok else dettaglio})

    esito("Macro: vbaProject.bin identico", o["vba"] == c["vba"], "vbaProject.bin assente o diverso")

    stati_o = [(n, f["stato"]) for n, f in o["fogli"].items()]
    stati_c = [(n, f["stato"]) for n, f in c["fogli"].items()]
    diversi = sorted({n for n, _ in set(stati_o) ^ set(stati_c)})
    esito("Fogli: nomi, ordine e visibilità invariati", stati_o == stati_c, "fogli: " + ", ".join(diversi or ["ordine cambiato"]))

    comuni = [n for n in o["fogli"] if n in c["fogli"]]
    diversi = [n for n in comuni if o["fogli"][n]["protezione"] != c["fogli"][n]["protezione"]]
    esito("Protezione dei fogli invariata", not diversi, "fogli: " + ", ".join(diversi))
    esito("Protezione della cartella invariata", o["protezione"] == c["protezione"], "protezione della cartella diversa")
    esito("Nomi definiti invariati", o["nomi"] == c["nomi"], "nomi: " + ", ".join(sorted(set(o["nomi"]) ^ set(c["nomi"])) or ["contenuto cambiato"]))

    def _dove(chiave):
        """`scritte`: chiavi "C10" (foglio indicato) oppure "foglio!C10" (modelli con più fogli)."""
        return tuple(chiave.split("!", 1)) if "!" in chiave else (foglio, chiave)

    previste = {_dove(k): v for k, v in scritte.items()}
    formule, fuori, non_scritte = [], [], []
    for nome in comuni:
        prima, dopo = o["fogli"][nome]["celle"], c["fogli"][nome]["celle"]
        for rif in sorted(set(prima) | set(dopo)):
            a, b = prima.get(rif), dopo.get(rif)
            if a == b:
                continue
            if (a and a[0] == "f") or (b and b[0] == "f"):
                if not (a and b and a[0] == b[0] == "f" and _formule_uguali(a, b)):
                    formule.append(f"{nome}!{rif}")
            elif (nome, rif) not in previste:
                fuori.append(f"{nome}!{rif}")
    for (nome, rif), valore in previste.items():
        if c["fogli"].get(nome, {"celle": {}})["celle"].get(rif) != ("v", valore if isinstance(valore, str) else float(valore)):
            non_scritte.append(f"{nome}!{rif}" if nome != foglio else rif)
    esito("Formule invariate", not formule, "celle: " + ", ".join(formule[:20]))
    esito("Nessuna cella cambiata fuori dalla whitelist", not fuori, "celle: " + ", ".join(fuori[:20]))
    esito("Celle previste scritte con il valore atteso", not non_scritte, "celle: " + ", ".join(non_scritte[:20]))

    perse = sorted(o["parti"] - c["parti"])
    critiche = [p for p in perse if _PARTI_CRITICHE.search(p)]
    esito("Nessun elemento perso (pulsanti, immagini, grafici)", not critiche, "parti perse: " + ", ".join(critiche))
    altre = [p for p in perse if p not in critiche]
    esito("Altre parti del file conservate", not altre, "parti non più presenti: " + ", ".join(altre), grave=False)
    return esiti


def superato(esiti) -> bool:
    return all(e["esito"] != KO for e in esiti)
