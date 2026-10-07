"""Checklist della raccolta documentale: SEMPLICE E NON BLOCCANTE.

Gruppo A = documenti di partenza (raccomandati, mai obbligatori per iniziare).
Gruppo B = approfondimenti SUGGERITI dall'analisi (mai obbligatori): ogni voce e' legata alla criticita' che la fa suggerire
e agli scenari per cui e' decisiva. Se un approfondimento decisivo manca si SOSPENDE SOLTANTO il giudizio su quegli scenari.
Lo stato di ogni voce e' uno tra STATI_VOCE; e' memorizzato in <pratica>/checklist.json (override dell'operatore) oppure dedotto
dal registro documentale. Il gate resta SOLO per il consolidamento (pratica.valuta).
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime
from pathlib import Path

from analisi_crisi import semaforo_v3

FILE_CHECKLIST = "checklist.json"
STATI_VOCE = ("ricevuto", "mancante", "da aggiornare", "illeggibile", "non pertinente")
STATO_DEFAULT = "mancante"
FALLBACK_RUOLI = "provvisori e da riconciliare"
FALLBACK_CR = "l'esposizione non è verificata"
ND = "non calcolabile con i dati disponibili"
TESTO_RUOLI = "Estratto di ruolo non disponibile: i debiti pubblici rilevati in contabilità sono " + FALLBACK_RUOLI + "."
TESTO_CR = "Centrale dei Rischi non disponibile: esposizione non verificata (si usano le informazioni contabili e contrattuali disponibili)."

SCENARI = {
    "continuita": "Continuità aziendale / risanamento",
    "ristrutturazione": "Ristrutturazione dei debiti",
    "liquidazione": "Liquidazione del patrimonio",
    "transazione_fiscale": "Transazione e rateazione dei debiti pubblici",
}

# parole chiave per dedurre la voce dal 'tipo' o dal nome di un documento registrato
_PAROLE = {
    "A1": r"visura|camerale|certificato",
    "A2": r"bilanc|situazione|contabil",
    "A3": r"ruol|riscossione",
    "A4": r"centrale|rischi|\bcr\b",
    "B1": r"tesoreria|cassa",
    "B2": r"estratt\w* conto|estratti_conto|conto corrente",
    "B3": r"creditor",
    "B4": r"rateazion|rateizz",
    "B5": r"perizi",
    "B6": r"cespit",
    "B7": r"inventari",
    "B8": r"contratt",
    "B9": r"esecutiv|pignorament|precetto",
    "B10": r"\bsoci\b|amministrator",
}


def _voce(id, gruppo, etichetta, raccomandata, fallback="", trigger=None, scenari=(), descr=""):
    return {"id": id, "gruppo": gruppo, "etichetta": etichetta, "raccomandata": raccomandata, "fallback": fallback,
            "trigger": trigger, "scenari": list(scenari), "descrizione": descr}


VOCI = [
    _voce("A1", "A", "Certificato camerale o visura camerale", True,
          "Assetto societario, cariche e procedure in corso non verificati su fonte camerale."),
    _voce("A2", "A", "Documentazione contabile disponibile (bilanci degli esercizi precedenti; situazione contabile o bilancio provvisorio dell'esercizio in corso)", True,
          "Si usano i soli periodi disponibili; i calcoli sui periodi mancanti risultano: " + ND + ".",
          descr="Non sono richiesti tre esercizi: basta quanto disponibile."),
    _voce("A3", "A", "Estratto di ruolo / situazione presso l'Agente della riscossione", True,
          "In assenza si usano i debiti pubblici rilevati in contabilità, qualificati " + FALLBACK_RUOLI + ".",
          descr="Raccomandato ma non indispensabile."),
    _voce("A4", "A", "Centrale dei Rischi della Banca d'Italia", True,
          "In assenza si usano le informazioni contabili e contrattuali disponibili; " + FALLBACK_CR + ".",
          descr="Riferimento per l'esposizione bancaria."),
    _voce("B1", "B", "Tesoreria (flussi di cassa, scadenziario)", False, trigger="cassa", scenari=("continuita", "ristrutturazione")),
    _voce("B2", "B", "Estratti conto bancari", False, trigger="bancario", scenari=("ristrutturazione", "continuita")),
    _voce("B3", "B", "Elenco analitico dei creditori", False, trigger="indebitamento", scenari=("ristrutturazione", "liquidazione")),
    _voce("B4", "B", "Rateazioni in corso", False, trigger="pubblici", scenari=("transazione_fiscale", "ristrutturazione")),
    _voce("B5", "B", "Perizie (immobili, beni, aziende)", False, trigger="patrimonio", scenari=("liquidazione",)),
    _voce("B6", "B", "Libro cespiti", False, trigger="patrimonio", scenari=("liquidazione",)),
    _voce("B7", "B", "Inventario", False, trigger="patrimonio", scenari=("liquidazione",)),
    _voce("B8", "B", "Contratti rilevanti (fornitura, lavoro, finanziamento, leasing)", False, trigger="margine", scenari=("continuita",)),
    _voce("B9", "B", "Atti esecutivi (pignoramenti, precetti, ipoteche)", False, trigger="pubblici", scenari=("transazione_fiscale", "liquidazione")),
    _voce("B10", "B", "Documentazione dei crediti verso soci/amministratori", False, trigger="soci", scenari=("liquidazione", "ristrutturazione")),
]
_BY_ID = {v["id"]: v for v in VOCI}

CRITICITA = {
    "cassa": "Flusso di cassa non verificato (l'EBITDA non equivale a cassa) o margine non positivo",
    "bancario": "Esposizione bancaria non verificata (Centrale dei Rischi non ricevuta)",
    "indebitamento": "Indebitamento elevato rispetto al flusso (debito netto/EBITDA oltre 3) o patrimonio netto negativo",
    "pubblici": "Debiti pubblici rilevanti rispetto all'attivo",
    "patrimonio": "Patrimonio netto negativo o ridotto: serve il valore di realizzo dell'attivo",
    "margine": "Margine EBITDA basso o non positivo: serve verificare la tenuta dei contratti",
    "soci": "Crediti verso soci/amministratori presenti in bilancio",
}


VERIFICA = {  # che cosa permette di verificare ciascuna voce
    "A1": "assetto societario, cariche, sede e procedure in corso",
    "A2": "margine EBITDA, patrimonio netto, debito netto e debiti pubblici contabili",
    "A3": "importo e stato dei debiti verso l'Agente della riscossione (riconciliazione dei debiti pubblici contabili)",
    "A4": "esposizione bancaria effettiva e classificazione delle linee di credito",
    "B1": "flusso di cassa disponibile e capacità di sostenere il piano",
    "B2": "movimentazioni, affidamenti utilizzati e riscontro con la Centrale dei Rischi",
    "B3": "composizione del passivo per classi e ordine di soddisfacimento",
    "B4": "piani di rateazione in corso e loro regolarità",
    "B5": "valore di realizzo dei beni",
    "B6": "consistenza e valore residuo dei cespiti",
    "B7": "consistenza delle rimanenze e dei beni",
    "B8": "tenuta dei ricavi e vincoli contrattuali sulla continuità",
    "B9": "procedure esecutive in corso e beni gravati",
    "B10": "esigibilità dei crediti verso soci/amministratori",
}


class ErroreChecklist(Exception):
    pass


def _ora():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _json(percorso, default):
    try:
        return json.loads(Path(percorso).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def _leggi_override(pratica):
    d = _json(Path(pratica) / FILE_CHECKLIST, {})
    return d.get("voci", {}) if isinstance(d, dict) else {}


def _stato_da_registro(pratica, voce_id):
    """Stato dedotto dal registro: 'ricevuto' se esiste un file registrato pertinente, altrimenti None."""
    rx = re.compile(_PAROLE[voce_id], re.I)
    for r in _json(Path(pratica) / "registro_documentale.json", []):
        if r.get("natura") != "NON DISPONIBILE" and rx.search(" ".join(str(r.get(k) or "") for k in ("tipo", "nome"))):
            return "ricevuto"
    return None


def documenti_ricevuti(pratica):
    return [r for r in _json(Path(pratica) / "registro_documentale.json", []) if r.get("natura") != "NON DISPONIBILE"]


def imposta_stato(pratica, voce_id, nuovo_stato, nome, nota=""):
    """Scrive l'override dell'operatore in checklist.json (scrittura atomica). Valida id e stato."""
    if voce_id not in _BY_ID:
        raise ErroreChecklist("voce inesistente")
    if nuovo_stato not in STATI_VOCE:
        raise ErroreChecklist("stato non ammesso")
    nome = (nome or "").strip()
    if not nome:
        raise ErroreChecklist("serve il nome di chi aggiorna lo stato")
    c = Path(pratica) / FILE_CHECKLIST
    d = _json(c, {})
    d.setdefault("voci", {})[voce_id] = {"stato": nuovo_stato, "da": nome, "il": _ora(), "nota": (nota or "").strip()[:300]}
    tmp = c.with_name(c.name + ".tmp")
    tmp.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, c)
    return d["voci"][voce_id]


def segnali(metriche):
    """Criticita' attive dedotte dalle metriche disponibili. Senza metriche: nessun segnale (mai dedotto da un'assenza)."""
    if not metriche:
        return {}
    sost = semaforo_v3.sostenibilita(metriche)
    col = {c["codice"]: c["colore"] for c in sost["criteri"]}
    out = {}
    if not metriche.get("cassa_verificata") or (metriche.get("margine") is not None and metriche["margine"] <= 0):
        out["cassa"] = CRITICITA["cassa"]
    if col.get("rapporto") in ("GIALLO", "ROSSO") or col.get("patrimonio") in ("GIALLO", "ROSSO"):
        out["indebitamento"] = CRITICITA["indebitamento"]
    if col.get("pubblici") in ("GIALLO", "ROSSO"):
        out["pubblici"] = CRITICITA["pubblici"]
    if col.get("patrimonio") in ("GIALLO", "ROSSO"):
        out["patrimonio"] = CRITICITA["patrimonio"]
    if col.get("margine") in ("GIALLO", "ROSSO"):
        out["margine"] = CRITICITA["margine"]
    if (metriche.get("crediti_soci_su_attivo") or 0) > 0:
        out["soci"] = CRITICITA["soci"]
    return out


def stato_checklist(pratica, metriche=None):
    """Checklist completa con lo stato effettivo di ogni voce. Legge checklist.json (override) e il registro; non scrive.
    Ritorna {'A': [...], 'B': [...]}. Ogni voce B porta 'suggerita' (bool) e 'criticita' (testo) se attivata da un segnale."""
    ov = _leggi_override(pratica)
    sg = segnali(metriche)
    gruppi = {"A": [], "B": []}
    for v in VOCI:
        o = ov.get(v["id"])
        if o and o.get("stato") in STATI_VOCE:
            stato, origine, da, il, nota = o["stato"], "operatore", o.get("da"), o.get("il"), o.get("nota", "")
        else:
            ded = _stato_da_registro(pratica, v["id"])
            stato, origine, da, il, nota = (ded or STATO_DEFAULT), ("registro" if ded else "predefinito"), None, None, ""
        riga = dict(v, stato=stato, origine=origine, aggiornato_da=da, aggiornato_il=il, nota=nota,
                    suggerita=(v["gruppo"] == "A") or (v["trigger"] in sg),
                    criticita=(sg.get(v["trigger"]) if v["trigger"] else None),
                    scenari_nomi=[SCENARI[s] for s in v["scenari"]], verifica=VERIFICA[v["id"]])
        gruppi[v["gruppo"]].append(riga)
    return gruppi


def sospensioni(pratica, metriche=None):
    """Scenari sospesi: per ogni voce B suggerita e decisiva non ricevuta (mancante / da aggiornare / illeggibile) sospende SOLO i suoi scenari.
    Ritorna {scenario: [motivi]}."""
    out = {}
    for v in stato_checklist(pratica, metriche)["B"]:
        if v["suggerita"] and v["stato"] in ("mancante", "da aggiornare", "illeggibile"):
            for s in v["scenari"]:
                out.setdefault(s, []).append(f"{v['etichetta']} ({v['stato']}): verifica mancante, legata a: {v['criticita']}")
    return out


def sufficienza_per_iniziare(pratica, metriche=None):
    """SEMPRE ok=True: per iniziare basta la pratica. Indica che cosa si potra' e non si potra' valutare."""
    ck = stato_checklist(pratica, metriche)
    A = {v["id"]: v for v in ck["A"]}
    ok_stato = lambda i: A[i]["stato"] in ("ricevuto",)
    valutabile, non_val, limiti = [], [], []
    if ok_stato("A2"):
        valutabile.append("indicatori economico-finanziari sui periodi disponibili (calcolo per calcolo)")
    else:
        non_val.append("indicatori economico-finanziari: " + ND + " (manca la documentazione contabile)")
        limiti.append("Manca la documentazione contabile: sarà prodotta una ricognizione del fascicolo con le richieste prioritarie.")
    if ok_stato("A1"):
        valutabile.append("assetto societario da fonte camerale")
    else:
        limiti.append(A["A1"]["fallback"])
    if ok_stato("A3"):
        valutabile.append("debiti verso l'Agente della riscossione da estratto di ruolo")
    else:
        limiti.append(TESTO_RUOLI)
    if ok_stato("A4"):
        valutabile.append("esposizione bancaria da Centrale dei Rischi")
    else:
        limiti.append(TESTO_CR)
        non_val.append("esposizione bancaria verificata")
    return {"ok": True, "valutabile": valutabile, "non_valutabile": non_val, "limiti": limiti}


def sufficienza_per_concludere(pratica, metriche=None):
    """False finche' mancano dati decisivi per gli scenari o numeri decisivi confermati. Elenca i motivi."""
    p = Path(pratica)
    motivi = []
    num = _json(p / "numeri_decisivi.json", [])
    if not num:
        motivi.append("nessun numero decisivo proposto e confermato dal titolare")
    else:
        nc = [str(n["id"]) for n in num if not n.get("confermato_da")]
        if nc:
            motivi.append("numeri decisivi non confermati: " + ", ".join(nc))
    sos = [str(x["id"]) for x in _json(p / "incongruenze.json", []) if x.get("gravita") == "SOSTANZIALE" and x.get("stato") == "APERTA"]
    if sos:
        motivi.append("incongruenze sostanziali aperte: " + ", ".join(sos))
    for sc, mm in sospensioni(p, metriche).items():
        motivi.append(f"scenario '{SCENARI[sc]}' sospeso: " + " | ".join(mm))
    mancanti = [r["nome"] for r in _json(p / "registro_documentale.json", []) if r.get("decisivo") and r.get("natura") == "NON DISPONIBILE"]
    if mancanti:
        motivi.append("documenti decisivi mancanti: " + ", ".join(mancanti))
    A = {v["id"]: v for v in stato_checklist(p, metriche)["A"]}
    if A["A2"]["stato"] != "ricevuto":
        motivi.append("documentazione contabile non ricevuta")
    return {"ok": not motivi, "motivi": motivi}
