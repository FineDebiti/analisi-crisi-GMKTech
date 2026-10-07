"""Estratto di ruolo SCANSIONATO ("Estratto di ruolo" Agenzia Entrate-Riscossione, tabella a colonne): lettura con OCR.

L'OCR perde l'allineamento delle colonne: per ogni documento (numero di 20 cifre) si conservano la data, gli importi
nell'ordine letto e il testo, con un solo importo "candidato" (totale residuo). TUTTO è DA VERIFICARE: l'avvocato
confronta con il PDF prima di usare i numeri. Nessun valore da scansione è mai FATTO.
"""
from __future__ import annotations

import re
from pathlib import Path

from . import ocr
from .comune import DA_VERIFICARE, NON_ESEGUIBILE
from .parser_ruoli import SCHEMA_RUOLI, TIPO, classe_ente

_NUM = re.compile(r"(?<!\d)(\d{20})(?!\d)")
_DATA = re.compile(r"\b(\d{2})[-./](\d{2})[-./](\d{4})\b")
_IMP = re.compile(r"(?<![\d.,])(\d{1,3}(?:\.\d{3})*,\d{2})(?!\d)")
_TIPO = re.compile(r"(cartella dopo avviso di pagamento|avviso di addebito|avviso di accertamento|avviso di pagamento|cartella)", re.I)


def _n(s):
    return float(s.replace(".", "").replace(",", "."))


def analizza(percorso) -> dict:
    percorso = Path(percorso)
    r = {"schema": SCHEMA_RUOLI, "documento": {"file": percorso.name, "tipo": TIPO, "lettura": "OCR"},
         "esito": "COMPLETATO", "documenti": [], "gruppi": [], "controlli": [], "avvisi": []}
    if not ocr.disponibile():
        r["esito"] = "FERMATO: OCR NON DISPONIBILE"
        return r
    pagine = ocr.testo_pagine(percorso)
    r["documento"]["pagine"] = len(pagine)
    prima = []  # righe di contesto (ente) prima del documento
    for n, testo in pagine:
        for riga in testo.replace("|", " ").splitlines():
            riga = riga.strip()
            if not riga or re.match(r"(legenda|\([A-Z0-9©]\))", riga, re.I):
                continue
            m = _NUM.search(riga.replace(" ", "") if False else riga)
            if not m:
                prima.append(riga)
                prima = prima[-4:]
                continue
            dopo = riga[m.end():]
            data = _DATA.search(dopo)
            importi = [_n(x) for x in _IMP.findall(dopo[data.end():] if data else dopo)]
            tipo = _TIPO.search(dopo)
            ente = " ".join(prima + [dopo[:data.start()] if data else dopo]).strip()
            cand = None
            if importi:
                cand = importi[-1] if len(importi) < 2 or importi[-1] != importi[-2] else importi[-2]
            r["documenti"].append({
                "tipo_documento": (tipo.group(1).lower() if tipo else None), "numero": m.group(1), "data_notifica": (
                    f"{data.group(3)}-{data.group(2)}-{data.group(1)}" if data else None),
                "ente_letto": ente[:160], "classe": classe_ente(ente), "importi_letti": importi,
                "totale_residuo_candidato": cand, "pagina": n, "testo_letto": riga[:300], "stato": DA_VERIFICARE,
                "note": ["Lettura OCR: colonne non garantite, confrontare con il PDF."]})
            prima = []
    if not r["documenti"]:
        r["esito"] = "NESSUN DOCUMENTO RICONOSCIUTO"
    r["controlli"].append({"nome": "controlli aritmetici sulle scansioni", "esito": NON_ESEGUIBILE,
                           "riferimento": "OCR: nessun totale affidabile con cui confrontare"})
    r["avvisi"].append("Documento letto da scansione: tutti i valori sono DA VERIFICARE.")
    return r
