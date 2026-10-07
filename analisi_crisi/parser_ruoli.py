"""Parser (e): estratto di ruolo dell'Agente della Riscossione, formato "Estratto Ruolo Semplificato" a testo nativo.

Un PDF = molte cartelle/avvisi di addebito. Tutto in locale, solo regole.
Per ogni documento: ente, righe (carico, sgravio, pagato, residuo), totali. Il totale debito di ogni gruppo
è confrontato con la somma dei totali dei documenti del gruppo (controllo aritmetico).
Le scansioni vanno a `ocr_ruoli.py` (OCR): in quel caso ogni valore è DA VERIFICARE.
"""
from __future__ import annotations

import re
from pathlib import Path

import pdfplumber

from .comune import DA_VERIFICARE, FATTO, KO, NON_ESEGUIBILE, OK, INFERENZA

TIPO = "estratto_di_ruolo"
SCHEMA_RUOLI = "estratto_ruolo/1"
_IMP = r"(-?[\d.]+,\d{2})"
_TESTATA = re.compile(r"^(CARTELLA|AVV\.\s?ADD\.|[A-Z][A-Z. ]{2,25}?)\s*NR\.\s+(\d+(?:\s\d+)?)\s+Rateazione:\s*([SN])", re.I)
_ENTE = re.compile(r"ENTE\s*:\s*(\d+)\s+(.+)$")
_RIGO = re.compile(r"^(\d{3})\s+(\S+)\s+([A-Z])\s+(\d{4})\s+(.*)$")
_IMPORTI = re.compile(rf"^{_IMP}\s+{_IMP}\s+{_IMP}\s+{_IMP}(?:\s+(\w+))?$")
_TOTALI = {
    "tributi": re.compile(rf"Totale tributi in debito\s+{_IMP}", re.I),
    "diritti_notifica": re.compile(rf"Diritti di notifica\s+{_IMP}", re.I),
    "aggio": re.compile(rf"Aggio\s+{_IMP}", re.I),
    "interessi_mora": re.compile(rf"Interessi di mora\s+{_IMP}", re.I),
    "spese": re.compile(rf"Diritti\s*/\s*spese\s+{_IMP}", re.I),
    "totale_documento": re.compile(rf"TOTALE (?:CARTELLA|AVVISO|DOCUMENTO)\s+{_IMP}", re.I),
}
_TOT_DEBITO = re.compile(rf"TOTALE DEBITO\s+{_IMP}", re.I)


def _n(s):
    v = float(s.replace(".", "").replace(",", "."))
    return int(v) if v == int(v) else round(v, 2)


def classe_ente(descrizione: str) -> str:
    d = descrizione.upper()
    if re.search(r"\bINPS\b|INAIL|PREVIDEN|CASSA", d):
        return "previdenziale"
    if re.search(r"AMMINISTRAZIONE FINANZIARIA|AGENZIA|ENTRATE|DOGANE|FINANZA", d):
        return "erariale"
    if re.search(r"COMUNE|PROVINCIA|REGIONE|CITT|PREFETTURA|UNIONE", d):
        return "enti_locali"
    if re.search(r"CAMERA DI COMMERCIO", d):
        return "camera_commercio"
    return "altro"


def _pulisci(riga):
    return riga.strip().strip("+").strip()


def analizza(percorso) -> dict:
    percorso = Path(percorso)
    with pdfplumber.open(percorso) as pdf:
        pagine = [(i, p.extract_text() or "") for i, p in enumerate(pdf.pages, 1)]
    r = {"schema": SCHEMA_RUOLI, "documento": {"file": percorso.name, "tipo": TIPO, "pagine": len(pagine),
         "pagine_con_testo": [n for n, t in pagine if t.strip()]}, "esito": "COMPLETATO", "documenti": [],
         "gruppi": [], "controlli": [], "avvisi": []}
    if not r["documento"]["pagine_con_testo"]:
        r["esito"] = "FERMATO: SCANSIONE"
        r["avvisi"].append("Nessun testo estraibile: usare l'OCR (ocr_ruoli).")
        return r

    for _, t in pagine[:3]:
        mdata = re.search(r"(\d{2}/\d{2}/\d{4})\s+\d{2}:\d{2}", t)
        if mdata:
            r["data_estratto"] = mdata.group(1)
            break
    docs, corrente, gruppo = {}, None, []
    ordine = []
    for n_pagina, testo in pagine:
        ente, riga_aperta = None, None
        for grezza in testo.splitlines():
            riga = _pulisci(grezza)
            if not riga:
                continue
            m = _TESTATA.match(riga)
            if m:
                chiave = (re.sub(r"\s+", " ", m.group(1).upper().replace(" ", "")), re.sub(r"\s+", " ", m.group(2)))
                if chiave not in docs:
                    docs[chiave] = {"tipo_documento": "avviso_di_addebito" if "ADD" in chiave[0] else "cartella",
                                    "numero": chiave[1], "rateazione": m.group(3).upper(), "pagine": [], "righe": [],
                                    "enti": [], "totali": {}, "tot_debito_gruppo": None}
                    ordine.append(chiave)
                    gruppo.append(chiave)
                corrente = docs[chiave]
                if n_pagina not in corrente["pagine"]:
                    corrente["pagine"].append(n_pagina)
                continue
            if corrente is None:
                continue
            m = _ENTE.match(riga)
            if m:
                ente = {"codice": m.group(1), "descrizione": m.group(2).strip(), "classe": classe_ente(m.group(2))}
                if ente not in corrente["enti"]:
                    corrente["enti"].append(ente)
                continue
            m = _RIGO.match(riga)
            if m:
                riga_aperta = {"pr": m.group(1), "cod": m.group(2), "t": m.group(3), "anno": int(m.group(4)),
                               "causale": m.group(5).strip(), "pagina": n_pagina,
                               "ente": (corrente["enti"][-1]["descrizione"] if corrente["enti"] else None)}
                continue
            m = _IMPORTI.match(riga)
            if m and riga_aperta is not None:
                riga_aperta.update(carico=_n(m.group(1)), sgravio=_n(m.group(2)), pagato=_n(m.group(3)),
                                   residuo=_n(m.group(4)), sospeso=(m.group(5) or "").upper() == "SOSP")
                corrente["righe"].append(riga_aperta)
                riga_aperta = None
                continue
            if riga_aperta is not None and "carico" not in riga_aperta:
                riga_aperta["causale"] += " " + riga
                continue
            for k, rx in _TOTALI.items():
                mm = rx.search(riga)
                if mm:
                    corrente["totali"][k] = _n(mm.group(1))
                    break
            else:
                mm = _TOT_DEBITO.search(riga)
                if mm:
                    for ch in gruppo:
                        docs[ch]["tot_debito_gruppo"] = len(r["gruppi"]) + 1
                    r["gruppi"].append({"totale_debito": _n(mm.group(1)), "documenti": [docs[ch]["numero"] for ch in gruppo],
                                        "pagina": n_pagina})
                    gruppo = []
    r["documenti"] = [docs[k] for k in ordine]

    def ctl(nome, atteso, ricalcolato, rif, tol=0.05):
        e = {"nome": nome, "riferimento": rif, "esito": NON_ESEGUIBILE, "atteso": atteso, "ricalcolato": ricalcolato}
        if atteso is not None and ricalcolato is not None:
            e["esito"] = OK if abs(atteso - ricalcolato) <= tol else KO
        r["controlli"].append(e)

    for d in r["documenti"]:
        t = d["totali"]
        ctl("residuo righe = totale tributi in debito", t.get("tributi"),
            round(sum(x["residuo"] for x in d["righe"]), 2) if d["righe"] else None, d["numero"])
        comp = [t.get(k) for k in ("tributi", "diritti_notifica", "aggio", "interessi_mora", "spese")]
        ctl("componenti = totale documento", t.get("totale_documento"),
            round(sum(comp), 2) if all(c is not None for c in comp) else None, d["numero"])
        d["stato"] = FATTO
    for i, g in enumerate(r["gruppi"], 1):
        somma = [d["totali"].get("totale_documento") for d in r["documenti"] if d["tot_debito_gruppo"] == i]
        ctl("somma documenti = totale debito del gruppo", g["totale_debito"],
            round(sum(somma), 2) if somma and None not in somma else None, f"gruppo {i}")
    if any(c["esito"] == KO for c in r["controlli"]):
        r["avvisi"].append("Almeno un controllo aritmetico non torna: verificare sul PDF.")
        for d in r["documenti"]:
            d["stato"] = DA_VERIFICARE
    if gruppo:
        r["avvisi"].append("Documenti dopo l'ultimo TOTALE DEBITO: gruppo non chiuso, controllo non eseguibile.")
    return r


def riepilogo(r) -> dict:
    """Totali per classe di ente (euro, sul totale documento)."""
    out = {}
    for d in r["documenti"]:
        classi = {e["classe"] for e in d["enti"]} or {"altro"}
        k = classi.pop() if len(classi) == 1 else "misto"
        out[k] = round(out.get(k, 0) + d["totali"].get("totale_documento", 0), 2)
    return out
