"""Parser (c): dichiarazione dei redditi, quadri RE / RG / LM (forfetario) e rigo RN dell'imposta netta.

Un PDF = un periodo d'imposta = colonna E di flussi_cassa_impresa. Solo regole, tutto in locale.
I numeri di rigo cambiano da un modello all'altro: quelli qui sotto sono da confermare sul modello dell'anno.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import pdfplumber

from .comune import (CONTROLLO, DA_VERIFICARE, EXCEL, FATTO, FOGLIO, INFERENZA, KO, NON_ESEGUIBILE, OK, SCHEMA,
                     RigaFoglio, cella)

TIPO = "dichiarazione_redditi"
COLONNA = "E"


@dataclass(frozen=True)
class Voce:
    chiave: str
    rigo: str  # rigo atteso
    regex: str  # inizio della descrizione normalizzata
    nome: str
    uso: str = EXCEL

    @property
    def quadro(self):
        return self.rigo[:2]


VOCI = (
    Voce("dr.RE6", "RE6", r"totale compensi", "RE6 Totale compensi"),
    Voce("dr.RE20", "RE20", r"totale spese", "RE20 Totale spese"),
    Voce("dr.RE21", "RE21", r"differenza", "RE21 Differenza (compensi - spese)", CONTROLLO),
    Voce("dr.RG12", "RG12", r"totale componenti positivi", "RG12 Totale componenti positivi"),
    Voce("dr.RG24", "RG24", r"totale componenti negativi", "RG24 Totale componenti negativi"),
    Voce("dr.RG26", "RG26", r"differenza", "RG26 Differenza (positivi - negativi)", CONTROLLO),
    Voce("dr.RN26", "RN26", r"imposta netta", "RN26 Imposta netta (IRPEF)"),
    Voce("dr.LM34", "LM34", r"reddito lordo", "LM34 Reddito lordo (forfetario)", CONTROLLO),
    Voce("dr.LM39", "LM39", r"imposta sostitutiva", "LM39 Imposta sostitutiva"),
)
# Righi delle attività in regime forfetario: coefficiente, componenti positivi, reddito per attività.
RIGHI_ATTIVITA_LM = {f"LM{n}" for n in range(22, 28)}
PRIMO_RIGO_FORFETARIO = 22

_RIGO = re.compile(r"^(?:(?:Impresa familiare|Impresa|Autonomo|familiare)\s+)?(R[EGN]|LM)\s?(\d{1,3})(?=\D|$)")
# Importi con i centesimi staccati ("74.872 ,00"): si riuniscono solo se la parte intera non può essere l'indice di un campo.
_SPEZZATO = re.compile(r"(?<![\d.,])(\d{1,3}(?:\.\d{3})+|\d{2,3})\s+(,\d{2})(?!\d)")
_IMPORTO = re.compile(r"-?\d{1,3}(?:\.\d{3})*,\d{2}")
_PERCENTO = re.compile(r"(\d{1,3}(?:,\d+)?)\s*%")
_PERIODO = re.compile(r"periodo d'imposta\s+(\d{4})")


def _norm(testo):
    return re.sub(r"\s+", " ", testo.replace("’", "'")).strip().lower()


def _importo(testo):
    v = float(testo.replace(".", "").replace(",", "."))
    return int(v) if v == int(v) else v


def _leggi_righi(pagine):
    righi = []
    for n_pagina, testo in pagine:
        for riga in testo.splitlines():
            grezza = _SPEZZATO.sub(r"\1\2", riga.strip())
            m = _RIGO.match(grezza)
            if not m:
                continue
            importi = [_importo(x) for x in _IMPORTO.findall(grezza)]
            if not importi:
                continue
            resto = grezza[m.end():]
            pct = _PERCENTO.search(resto)
            righi.append({
                "codice": m.group(1) + m.group(2),
                "quadro": m.group(1),
                "etichetta": _norm(_IMPORTO.split(resto)[0]),
                "importi": importi,
                "percento": float(pct.group(1).replace(",", ".")) if pct else None,
                "pagina": n_pagina,
                "testo": grezza,
            })
    return righi


def _trova(voce, righi):
    """Restituisce (rigo, stato, note) oppure None. FATTO solo se coincidono rigo e descrizione."""
    for r in righi:
        if r["codice"] == voce.rigo:
            if re.match(voce.regex, r["etichetta"]):
                return r, FATTO, []
            return r, INFERENZA, ["Rigo atteso, ma con una descrizione diversa da quella prevista."]
    attesi = {v.rigo for v in VOCI} | RIGHI_ATTIVITA_LM
    for r in righi:
        if r["quadro"] == voce.quadro and r["codice"] not in attesi and re.match(voce.regex, r["etichetta"]):
            return r, INFERENZA, [f"Descrizione trovata sul rigo {r['codice']} anziché {voce.rigo}."]
    return None


def analizza(percorso) -> dict:
    """Estrae la dichiarazione dal PDF. Non scrive nulla: restituisce il dizionario del JSON."""
    percorso = Path(percorso)
    with pdfplumber.open(percorso) as pdf:
        pagine = [(i, p.extract_text() or "") for i, p in enumerate(pdf.pages, 1)]
    con_testo = [n for n, t in pagine if t.strip()]
    risultato = {
        "schema": SCHEMA,
        "documento": {"file": percorso.name, "tipo": TIPO, "pagine": len(pagine), "pagine_con_testo": con_testo},
        "esito": "COMPLETATO",
        "esercizi": [],
        "regimi": [],
        "foglio": [],
        "dati": [],
        "residui": [],
        "controllo": [],
        "controlli": [],
        "voci_facoltative_assenti": [],
        "righe_non_mappate": [],
        "righe_di_dettaglio_ignorate": 0,
        "avvisi": [],
    }
    if not con_testo:
        risultato["esito"] = "FERMATO: SCANSIONE"
        risultato["avvisi"].append("Nessun testo estraibile: il documento sembra una scansione. OCR non previsto (SPECIFICA.md, regola 11).")
        return risultato

    m = _PERIODO.search(_norm(" ".join(t for _, t in pagine)))
    periodo = m.group(1) if m else None
    if periodo:
        risultato["esercizi"] = [{"periodo_imposta": periodo, "colonna_excel": COLONNA}]
    else:
        risultato["avvisi"].append("Periodo d'imposta non trovato: tutto DA VERIFICARE.")

    righi = _leggi_righi(pagine)
    quadri = {r["quadro"] for r in righi}
    forfetario = any(r["quadro"] == "LM" and int(r["codice"][2:]) >= PRIMO_RIGO_FORFETARIO for r in righi)
    regimi = [q for q in ("RE", "RG") if q in quadri] + (["LM"] if forfetario else [])
    risultato["regimi"] = regimi
    if not regimi:
        risultato["avvisi"].append("Nessun quadro RE, RG o LM (forfetario) riconosciuto.")
    if len(regimi) > 1:
        risultato["avvisi"].append("Più quadri di reddito presenti: le celle interessate sono DA VERIFICARE.")

    per, usati = {}, set()

    def aggiungi(chiave, nome, uso, valore=None, stato=DA_VERIFICARE, rigo=None, testo=None, note=(), riga=None):
        dato = {
            "chiave": chiave, "voce": nome, "esercizio": periodo, "anno": None, "valore": valore,
            "stato": stato if periodo else DA_VERIFICARE,
            "fonte": {"file": percorso.name, "tipo_documento": TIPO, "pagina": rigo["pagina"] if rigo else None,
                      "testo_letto": testo or (rigo["testo"] if rigo else None)},
            "destinazione": {"foglio": FOGLIO, "colonna": COLONNA, "riga": riga} if uso == EXCEL else None,
            "note": list(note),
        }
        per[chiave] = dato
        risultato["dati" if uso == EXCEL else "controllo"].append(dato)

    ordinario = bool({"RE", "RG"} & quadri) or not regimi
    riga_di = {"dr.RE6": 37, "dr.RG12": 37, "dr.RE20": 38, "dr.RG24": 38, "dr.RN26": 42, "dr.LM39": 52}
    for voce in VOCI:
        if voce.quadro in ("RE", "RG") and voce.quadro not in quadri:
            continue
        if voce.quadro == "RN" and not ordinario:
            continue
        if voce.quadro == "LM" and not forfetario:
            continue
        esito = _trova(voce, righi)
        if esito is None:
            aggiungi(voce.chiave, voce.nome, voce.uso, note=["Rigo non trovato nel documento."], riga=riga_di.get(voce.chiave))
        else:
            rigo, stato, note = esito
            usati.add(id(rigo))
            aggiungi(voce.chiave, voce.nome, voce.uso, rigo["importi"][-1], stato, rigo, note=note, riga=riga_di.get(voce.chiave))

    if forfetario:
        attivita = [r for r in righi if r["codice"] in RIGHI_ATTIVITA_LM]
        usati.update(id(r) for r in attivita)
        letto = " / ".join(r["testo"] for r in attivita) or None
        primo = attivita[0] if attivita else None
        piu = len(attivita) > 1
        nota_somma = ["Somma di più attività."] if piu else []
        if attivita:
            aggiungi("dr.LM_ricavi", "LM22-27 Componenti positivi (forfetario)", EXCEL, sum(r["importi"][0] for r in attivita),
                     INFERENZA if piu else FATTO, primo, letto, nota_somma, riga=47)
            coefficienti = {r["percento"] for r in attivita}
            if len(coefficienti) == 1 and None not in coefficienti:
                aggiungi("dr.LM_coeff", "LM22-27 Coefficiente di redditività (%)", EXCEL, coefficienti.pop(), FATTO, primo, letto,
                         ["Valore in percentuale: verificare il formato atteso dalla cella (es. 78 oppure 0,78)."], riga=48)
            else:
                aggiungi("dr.LM_coeff", "LM22-27 Coefficiente di redditività (%)", EXCEL, rigo=primo, testo=letto,
                         note=["Coefficiente assente o diverso tra le attività: inserimento manuale."], riga=48)
            redditi = [r["importi"][-1] for r in attivita if len(r["importi"]) > 1]
            aggiungi("dr.LM_reddito", "LM22-27 Reddito per attività (forfetario)", CONTROLLO,
                     sum(redditi) if len(redditi) == len(attivita) else None, INFERENZA if piu else FATTO, primo, letto, nota_somma)
        else:
            for chiave, nome, uso, riga in (("dr.LM_ricavi", "LM22-27 Componenti positivi (forfetario)", EXCEL, 47),
                                            ("dr.LM_coeff", "LM22-27 Coefficiente di redditività (%)", EXCEL, 48),
                                            ("dr.LM_reddito", "LM22-27 Reddito per attività (forfetario)", CONTROLLO, None)):
                aggiungi(chiave, nome, uso, note=["Righi delle attività non trovati."], riga=riga)
    risultato["righe_di_dettaglio_ignorate"] = sum(1 for r in righi if id(r) not in usati)

    def valore(k):
        return per[k]["valore"] if k in per else None

    def controlla(nome, totale, ricalcolato, tolleranza=0.5):
        if totale not in per:
            return None
        atteso = valore(totale)
        esito = {"nome": nome, "esercizio": periodo, "anno": None, "esito": NON_ESEGUIBILE, "atteso": atteso, "ricalcolato": ricalcolato}
        if atteso is not None and ricalcolato is not None:
            esito["esito"] = OK if abs(ricalcolato - atteso) <= tolleranza else KO
            if esito["esito"] == KO:
                per[totale]["stato"] = DA_VERIFICARE
                per[totale]["note"].append(f"Controllo fallito: {nome}.")
        risultato["controlli"].append(esito)
        return esito["esito"]

    def differenza(a, b):
        return valore(a) - valore(b) if valore(a) is not None and valore(b) is not None else None

    controlla("RE: differenza = totale compensi - totale spese", "dr.RE21", differenza("dr.RE6", "dr.RE20"))
    controlla("RG: differenza = componenti positivi - componenti negativi", "dr.RG26", differenza("dr.RG12", "dr.RG24"))
    controlla("LM: reddito lordo = somma dei redditi per attività", "dr.LM34", valore("dr.LM_reddito"))
    if valore("dr.LM_ricavi") is not None and valore("dr.LM_coeff") is not None:
        controlla("LM: reddito per attività = componenti positivi x coefficiente", "dr.LM_reddito",
                  valore("dr.LM_ricavi") * valore("dr.LM_coeff") / 100, tolleranza=1)

    righe = []
    if ordinario:
        righe += [
            RigaFoglio(37, "Compensi/ricavi (RE/RG)", tuple((k, 1) for k in ("dr.RE6", "dr.RG12") if k in per) or (("dr.RE6", 1),)),
            RigaFoglio(38, "Costi (RE/RG)", tuple((k, 1) for k in ("dr.RE20", "dr.RG24") if k in per) or (("dr.RE20", 1),)),
            RigaFoglio(42, "IRPEF netta (RN)", (("dr.RN26", 1),)),
        ]
        risultato["avvisi"].append("Riga 40 (contributi previdenziali): lasciata vuota, inserimento manuale.")
    if forfetario:
        righe += [
            RigaFoglio(47, "Ricavi (forfetario, LM)", (("dr.LM_ricavi", 1),)),
            RigaFoglio(48, "Coefficiente di redditività (LM)", (("dr.LM_coeff", 1),)),
            RigaFoglio(52, "Imposta sostitutiva (LM)", (("dr.LM39", 1),)),
        ]
        risultato["avvisi"].append("Riga 50 (contributi previdenziali): lasciata vuota, inserimento manuale.")
    for rf in righe:
        c = cella(rf, {k: per[k] for k, _ in rf.componenti if k in per})
        if len(rf.componenti) > 1:
            c["stato"] = DA_VERIFICARE
            c["note"].append("Presenti sia il quadro RE sia il quadro RG: scegliere quale riportare.")
        if not periodo:
            c["stato"] = DA_VERIFICARE
        risultato["foglio"].append({"riga": rf.riga, "voce": rf.nome, "componenti": [k for k, _ in rf.componenti], "celle": {COLONNA: c}})
    risultato["avvisi"].append("Con più dichiarazioni, nell'Excel va l'ultimo periodo d'imposta disponibile (SPECIFICA.md, regola 8).")
    return risultato
