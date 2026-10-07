"""Parser (f): visura camerale (InfoCamere / Registro Imprese) a testo nativo. Solo regole, in locale.

Legge la prima pagina ("esito evasione": dati anagrafici attuali) e gli eventi del Registro (scioglimento, liquidazione,
variazione di denominazione, trasformazione). Ogni valore porta pagina e testo letto. Le variazioni di denominazione o
di forma giuridica sono segnalate come AVVISO e rendono DA VERIFICARE ragione sociale e forma giuridica.
"""
from __future__ import annotations

import re
from pathlib import Path

import pdfplumber

from .comune import DA_VERIFICARE, FATTO, INFERENZA

TIPO = "visura_camerale"
SCHEMA_VISURA = "visura/1"
_DATA = r"(\d{2}/\d{2}/\d{4})"


def _norm(t):
    return re.sub(r"\s+", " ", t).strip()


def analizza(percorso) -> dict:
    percorso = Path(percorso)
    with pdfplumber.open(percorso) as pdf:
        pagine = [(i, p.extract_text() or "") for i, p in enumerate(pdf.pages, 1)]
    r = {"schema": SCHEMA_VISURA, "documento": {"file": percorso.name, "tipo": TIPO, "pagine": len(pagine)},
         "esito": "COMPLETATO", "campi": {}, "eventi": [], "avvisi": []}
    if not any(t.strip() for _, t in pagine):
        r["esito"] = "FERMATO: SCANSIONE"
        return r
    p1 = pagine[0][1]
    flat1 = _norm(p1)

    def campo(chiave, valore, pagina, letto, stato=FATTO, note=()):
        if valore:
            r["campi"][chiave] = {"valore": valore, "stato": stato, "pagina": pagina, "testo_letto": letto[:120], "note": list(note)}

    m = re.search(r"Numero REA\s+([A-Z]{2})\s*-\s*(\d+)", flat1)
    if m:
        campo("rea", f"{m.group(1)} - {m.group(2)}", 1, m.group(0))
    m = re.search(r"Codice fiscale e n\.iscr\. al\s+(\d{11})", flat1)
    if m:
        campo("codice_fiscale", m.group(1), 1, m.group(0))
    m = re.search(r"Domicilio digitale/PEC\s+(\S+@\S+)", flat1)
    if m:
        campo("pec", m.group(1), 1, m.group(0))
    m = re.search(r"Forma giuridica\s+(.+?)\s+(?:Procedure in corso|Liquidatore|Il presente)", flat1)
    if m:
        campo("forma_giuridica", m.group(1).strip(), 1, m.group(0))
    m = re.search(r"Procedure in corso\s+(.+?)\s+(?:Liquidatore|Il presente)", flat1)
    if m:
        campo("stato_impresa", m.group(1).strip(), 1, m.group(0))
    m = re.search(r"Liquidatore\s+([A-ZÀ-Ü' ]+?)\s+Il presente", flat1)
    if m:
        campo("liquidatore", m.group(1).strip().title(), 1, "Liquidatore " + m.group(1)[:30])
    # Sede: dopo "Indirizzo Sede legale" fino a CAP (la denominazione precede e occupa più righe).
    m = re.search(r"Indirizzo Sede legale\s+(.+?)\s+CAP\s+(\d{5})", flat1)
    if m:
        campo("sede_legale", f"{m.group(1).strip().title()}, {m.group(2)}", 1, m.group(0))
    # Denominazione attuale: righe prima di "DATI ANAGRAFICI"
    m = re.search(r"DEL\s*\d{2}/\d{2}/\d{4}\s+(.+?)\s+DATI ANAGRAFICI(.*?)Indirizzo", " ".join(p1.splitlines()), re.S)
    nome = None
    righe = p1.splitlines()
    for i, l in enumerate(righe):
        if "DATI ANAGRAFICI" in l:
            nome = _norm(righe[i].split("DATI ANAGRAFICI")[0] + " " + (righe[i + 1].split("Indirizzo")[0] if i + 1 < len(righe) else ""))
            break
    if nome:
        campo("denominazione", nome.title() if nome.isupper() else nome, 1, "DATI ANAGRAFICI (denominazione)")
    testo = _norm(" ".join(t for _, t in pagine))
    # Eventi del Registro (date, senza altro testo)
    for pagina, t in pagine:
        flat = _norm(t)
        for ev, rx in (("scioglimento e liquidazione", r"scioglimento e liquidazione Data iscrizione:\s*" + _DATA),
                       ("data atto di scioglimento", r"Data atto:\s*" + _DATA)):
            for mm in re.finditer(rx, flat):
                r["eventi"].append({"evento": ev, "data": mm.group(1), "pagina": pagina})
        if re.search(r"VARIAZIONE DELLA DENOMINAZIONE", flat):
            mm = re.search(r"VARIAZIONE DELLA DENOMINAZIONE\. DENOMINAZIONE PRECEDENTE:\s*(.+?)\s+Data iscrizione:\s*" + _DATA, flat)
            r["eventi"].append({"evento": "variazione della denominazione", "data": mm.group(2) if mm else None, "pagina": pagina,
                                "precedente": mm.group(1).title() if mm else None})
    m = re.search(r"Data atto di costituzione:\s*" + _DATA, testo)
    if m:
        campo("data_costituzione", m.group(1), 2, m.group(0), stato=INFERENZA,
              note=["Prima data di costituzione trovata nel documento: verificare se ci sono state trasformazioni."])
    variazioni = [e for e in r["eventi"] if e["evento"] == "variazione della denominazione"]
    if variazioni or re.search(r"TRASFORMAZIONE", testo):
        r["avvisi"].append("Il Registro riporta una variazione di denominazione o una trasformazione: ragione sociale e forma "
                           "giuridica attuali possono differire dai documenti degli altri enti (bilanci, CRIF, ruoli). Verificare.")
        for k in ("denominazione", "forma_giuridica"):
            if k in r["campi"]:
                r["campi"][k]["stato"] = INFERENZA
                r["campi"][k]["note"].append("Variazione di denominazione/forma giuridica nel Registro: verificare quella in vigore.")
    if not r["campi"]:
        r["esito"] = "NESSUN CAMPO RICONOSCIUTO"
    return r
