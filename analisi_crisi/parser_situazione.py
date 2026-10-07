"""Parser (b): situazione contabile / bilancio provvisorio del gestionale (due colonne: attività | passività, costi | ricavi).

Conti nel formato MM/GG/CCC (mastro/gruppo/conto), totali di mastro MM/**/*** o MM/00000. Ogni riga è assegnata alla colonna
sinistra o destra dalla posizione. I saldi si leggono per mastro; il netto di un mastro dell'attivo è sinistra - destra
(i fondi di ammortamento stanno a destra). Controlli: somma dei mastri = totali stampati nel documento.
"""
from __future__ import annotations

import re
from pathlib import Path

import pdfplumber

from .comune import DA_VERIFICARE, FATTO, INFERENZA, KO, NON_ESEGUIBILE, OK

TIPO = "situazione_contabile"
SCHEMA_SITUAZIONE = "situazione/1"
_CODICE = re.compile(r"^(\d{2})/(\d{2}|\*\*)/(\d{3}|\*\*\*)$|^(\d{2})/(\d{5})$")
_IMPORTO = re.compile(r"^-?\d{1,3}(?:\.\d{3})*,\d{2}$")
_DATA = re.compile(r"SITUAZIONE\s+(PATRIMONIALE|ECONOMICA)\s+AL\s+(\d{2}/\d{2}/\d{4})", re.I)
_TOTALE = re.compile(r"\*{3,5}\s+(TOTALE ATTIVITA|TOTALE PASSIVITA|TOTALE COSTI|TOTALE RICAVI|UTILE DI ESERCIZIO|PERDITA DI ESERCIZIO|TOTALE A PAREGGIO)\S*\s+(-?[\d.]+,\d{2})", re.I)


def _n(s):
    v = float(s.replace(".", "").replace(",", "."))
    return int(v) if v == int(v) else round(v, 2)


def _righe_laterali(pagina):
    """[(lato, testo)] per ogni riga della pagina: lato 'S' o 'D' secondo la posizione orizzontale."""
    parole = pagina.extract_words(keep_blank_chars=False, use_text_flow=False)
    meta = pagina.width * 0.495  # i codici di destra iniziano oltre la metà pagina, gli importi di sinistra finiscono prima
    righe = {}
    for p in parole:
        chiave = round(p["top"] / 3)
        lato = "S" if p["x0"] < meta else "D"
        righe.setdefault((chiave, lato), []).append(p)
    out = []
    for (k, lato), ws in sorted(righe.items()):
        out.append((lato, " ".join(w["text"] for w in sorted(ws, key=lambda w: w["x0"]))))
    return out


def analizza(percorso) -> dict:
    percorso = Path(percorso)
    r = {"schema": SCHEMA_SITUAZIONE, "documento": {"file": percorso.name, "tipo": TIPO}, "esito": "COMPLETATO",
         "date": {}, "mastri": {}, "gruppi": {}, "totali": {}, "controlli": [], "avvisi": [], "non_mappati": []}
    with pdfplumber.open(percorso) as pdf:
        pagine = [(i, p.extract_text() or "", p) for i, p in enumerate(pdf.pages, 1)]
        r["documento"]["pagine"] = len(pagine)
        if not any(t.strip() for _, t, _ in pagine):
            r["esito"] = "FERMATO: SCANSIONE"
            return r
        for n, testo, pag in pagine:
            m = _DATA.search(testo)
            if not m:
                continue
            sezione = m.group(1).upper()
            r["date"][sezione] = m.group(2)
            for lato, riga in _righe_laterali(pag):
                par = riga.split()
                if not par:
                    continue
                if _CODICE.match(par[0]) and _IMPORTO.match(par[-1]) and len(par) >= 3:
                    cod = _CODICE.match(par[0])
                    mastro = cod.group(1) or cod.group(4)
                    descr = " ".join(par[1:-1])
                    if cod.group(4):  # MM/00000: totale del mastro con conti per anagrafica
                        livello = "mastro" if cod.group(5) == "00000" else "conto"
                    elif cod.group(2) == "**":
                        livello = "mastro"
                    elif cod.group(3) == "***":
                        livello = "gruppo"
                    else:
                        livello = "conto"
                    valore = _n(par[-1])
                    if livello == "mastro":
                        e = r["mastri"].setdefault(mastro, {"S": None, "D": None, "descrizione": descr, "pagina": n})
                        e[lato] = (e[lato] or 0) + valore if e[lato] is not None else valore
                    elif livello == "gruppo":
                        r["gruppi"][f"{mastro}/{cod.group(2)}"] = {"valore": valore, "lato": lato, "descrizione": descr}
                else:
                    t = _TOTALE.search(riga)
                    if t:
                        r["totali"][t.group(1).upper()] = _n(t.group(2))
    if not r["mastri"]:
        r["esito"] = "NESSUN CONTO RICONOSCIUTO"
        return r

    def ctl(nome, atteso, ricalcolato, tol=0.05):
        e = {"nome": nome, "esito": NON_ESEGUIBILE, "atteso": atteso, "ricalcolato": ricalcolato}
        if atteso is not None and ricalcolato is not None:
            e["esito"] = OK if abs(atteso - ricalcolato) <= tol else KO
        r["controlli"].append(e)

    patrimoniali = {m: v for m, v in r["mastri"].items() if int(m) < 56}
    economici = {m: v for m, v in r["mastri"].items() if int(m) >= 56}
    somma = lambda ms, lato: round(sum(v[lato] or 0 for v in ms.values()), 2)
    t = r["totali"]
    ctl("attività: somma dei mastri a sinistra = totale attività", t.get("TOTALE ATTIVITA"), somma(patrimoniali, "S") if "PATRIMONIALE" in r["date"] else None)
    ctl("passività: somma dei mastri a destra = totale passività", t.get("TOTALE PASSIVITA"), somma(patrimoniali, "D") if "PATRIMONIALE" in r["date"] else None)
    ctl("costi: somma dei mastri a sinistra = totale costi", t.get("TOTALE COSTI"), somma(economici, "S") if "ECONOMICA" in r["date"] else None)
    ctl("ricavi: somma dei mastri a destra = totale ricavi", t.get("TOTALE RICAVI"), somma(economici, "D") if "ECONOMICA" in r["date"] else None)
    if "UTILE DI ESERCIZIO" in t and "TOTALE RICAVI" in t and "TOTALE COSTI" in t:
        ctl("utile = ricavi - costi", t["UTILE DI ESERCIZIO"], round(t["TOTALE RICAVI"] - t["TOTALE COSTI"], 2))
    if any(c["esito"] == KO for c in r["controlli"]):
        r["avvisi"].append("Almeno un controllo aritmetico non torna: tutte le voci sono DA VERIFICARE.")
    return r
