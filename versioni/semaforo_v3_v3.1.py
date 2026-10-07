"""Semaforo v3 - tre dimensioni distinte: SOSTENIBILITA', QUALITA' DEI DATI, FATTIBILITA'.

Sostituisce nell'uso la v2 (analisi_crisi/semaforo.py, conservata invariata). Supporto alla decisione, NON attestazione.

Regole (soglie in SOGLIE_V3, dichiarate nel documento come "parametri interni di screening", salvo le fasce
indicative del test pratico del decreto dirigenziale 23/04/2026, qui applicate al solo rapporto SEMPLIFICATO):
 1. SOSTENIBILITA' si riferisce alla gestione STORICA del periodo indicato. Il colore e' il peggiore dei criteri
    determinanti; il rapporto debito netto/EBITDA e' valutato sul flusso piu' PRUDENTE disponibile (non sul migliore).
    L'EBITDA non e' cassa: il criterio "flusso di cassa disponibile" e' NON VERIFICATO finche' manca la tesoreria e
    figura tra i dati decisivi mancanti; non e' mai sostituito da zero ne' dall'EBITDA.
 2. QUALITA' DEI DATI: ALTA / MEDIA / BASSA / INSUFFICIENTE da completezza, aggiornamento e dati decisivi mancanti.
 3. FATTIBILITA': PERCORRIBILE / CONDIZIONATA / NON CONCLUDENTE / NON PERCORRIBILE.
    Se manca anche un solo dato DECISIVO la conclusione e' NON DEFINITIVA: la fattibilita' non puo' essere ne'
    PERCORRIBILE ne' NON PERCORRIBILE (al massimo CONDIZIONATA, se esiste un percorso ipotizzabile; altrimenti
    NON CONCLUDENTE). La liquidazione non e' mai indicata come preferibile se non valutabile.
"""
from __future__ import annotations

SOGLIE_V3 = {
    "margine_verde": 0.08,          # parametro interno
    "pn_giallo_su_attivo": -0.10,   # parametro interno
    "pubblici_verde": 0.05, "pubblici_giallo": 0.20,   # parametri interni (non soglie CCII)
    "rapporto_fasce": (1.0, 3.0, 5.0),   # fasce indicative del test pratico (decreto 23/04/2026): rapporto semplificato
    "doc_aggiornati_alta": 0.80,
}
PESO = {"VERDE": 0, "GIALLO": 1, "ROSSO": 2}
LIV_COL = {"ALTA": "VERDE", "MEDIA": "GIALLO", "BASSA": "ROSSO", "INSUFFICIENTE": "ROSSO"}


def fascia_rapporto(r, soglie=None):
    s = (soglie or SOGLIE_V3)["rapporto_fasce"]
    if r is None:
        return None
    return "<=1" if r <= s[0] else ("1-3" if r <= s[1] else ("3-5" if r <= s[2] else ">5"))


def _peggiore(cs):
    cs = [c for c in cs if c]
    return max(cs, key=PESO.get) if cs else None


def sostenibilita(m, soglie=None):
    s = {**SOGLIE_V3, **(soglie or {})}
    crit = []

    def add(cod, nome, valore, colore, decisivo, nota):
        crit.append({"codice": cod, "nome": nome, "valore": valore, "colore": colore, "determinante": decisivo, "nota": nota})
    mg = m.get("margine")
    add("margine", "Margine EBITDA", mg, None if mg is None else ("VERDE" if mg >= s["margine_verde"] else ("GIALLO" if mg > 0 else "ROSSO")), True,
        "Verde >= 8%; giallo > 0; rosso <= 0 (parametro interno). Se normalizzato, e' un limite superiore.")
    rr = [v for v in (m.get("rapporti") or {}).values() if v is not None]
    prud = max(rr) if rr else None
    if m.get("flusso_non_positivo"):
        col = "ROSSO"
    else:
        col = None if prud is None else ("VERDE" if prud <= s["rapporto_fasce"][1] else ("GIALLO" if prud <= s["rapporto_fasce"][2] else "ROSSO"))
    add("rapporto", "Rapporto semplificato debito netto/EBITDA (flusso piu' prudente)", prud, col, True,
        "Verde fino a 3, giallo fino a 5, rosso oltre (fasce indicative del decreto 23/04/2026 applicate al solo rapporto semplificato; NON e' il test ministeriale).")
    pn = m.get("pn_su_attivo")
    add("patrimonio", "Patrimonio netto / attivo (rettificato se simulato)", pn, None if pn is None else ("VERDE" if pn > 0 else ("GIALLO" if pn >= s["pn_giallo_su_attivo"] else "ROSSO")), True,
        "Verde se > 0; giallo fino a -10%; rosso oltre (parametro interno). Una rettifica solo simulata non e' un fatto.")
    pb = m.get("pubblici_su_attivo")
    add("pubblici", "Debiti pubblici / attivo", pb, None if pb is None else ("VERDE" if pb <= s["pubblici_verde"] else ("GIALLO" if pb <= s["pubblici_giallo"] else "ROSSO")), False,
        "Parametro interno di screening, non soglia del CCII.")
    add("cassa", "Flusso di cassa disponibile (tesoreria)", None, None, False,
        "NON VERIFICATO: l'EBITDA non equivale a cassa; servono rendiconto finanziario o movimenti di tesoreria." if not m.get("cassa_verificata") else "Verificato.")
    det = [x["colore"] for x in crit if x["determinante"]]
    colore = _peggiore(det)
    rossi = sum(1 for x in crit if x["colore"] == "ROSSO")
    if colore != "ROSSO" and rossi >= 2:
        colore = "ROSSO"
    return {"colore": colore or "ND", "criteri": crit, "riferimento": m.get("riferimento", "gestione storica"), "flusso_prudente": prud}


def qualita_dati(documenti, decisivi):
    """documenti: [{'nome','disponibile':bool,'aggiornato':bool}]; decisivi: [{'nome','disponibile':bool}]"""
    n = len(documenti)
    disp = [d for d in documenti if d.get("disponibile")]
    agg = [d for d in disp if d.get("aggiornato")]
    mancanti = [d["nome"] for d in decisivi if not d.get("disponibile")]
    q_disp = len(disp) / n if n else 0
    q_agg = len(agg) / len(disp) if disp else 0
    if q_disp < 0.5 or len(mancanti) >= 3 and q_agg < 0.5:
        liv = "INSUFFICIENTE"
    elif mancanti:
        liv = "BASSA"
    elif q_agg >= SOGLIE_V3["doc_aggiornati_alta"]:
        liv = "ALTA"
    else:
        liv = "MEDIA"
    return {"livello": liv, "colore": LIV_COL[liv], "documenti_disponibili": len(disp), "documenti_totali": n, "documenti_aggiornati": len(agg), "decisivi_mancanti": mancanti}


def fattibilita(sost, qual, percorso_ipotizzabile=False, scenari_tutti_valutabili=False, esito_scenari=None):
    """esito_scenari: 'sufficiente' | 'insufficiente' | None. Usato solo se la conclusione e' definitiva."""
    definitiva = not qual["decisivi_mancanti"]
    if not definitiva:
        esito = "CONDIZIONATA" if percorso_ipotizzabile else "NON CONCLUDENTE"
        colore = "GIALLO" if esito == "CONDIZIONATA" else "ND"
    elif scenari_tutti_valutabili and esito_scenari == "sufficiente" and sost["colore"] != "ROSSO":
        esito, colore = "PERCORRIBILE", "VERDE"
    elif scenari_tutti_valutabili and esito_scenari == "insufficiente":
        esito, colore = "NON PERCORRIBILE", "ROSSO"
    else:
        esito, colore = "CONDIZIONATA" if percorso_ipotizzabile else "NON CONCLUDENTE", "GIALLO" if percorso_ipotizzabile else "ND"
    return {"esito": esito, "colore": colore, "definitiva": definitiva}


def valuta_v3(m, documenti, decisivi, percorso_ipotizzabile=False, scenari_tutti_valutabili=False, esito_scenari=None, soglie=None):
    s = sostenibilita(m, soglie)
    q = qualita_dati(documenti, decisivi)
    f = fattibilita(s, q, percorso_ipotizzabile, scenari_tutti_valutabili, esito_scenari)
    return {"sostenibilita": s, "qualita_dati": q, "fattibilita": f, "definitiva": f["definitiva"],
            "stato": "DEFINITIVA" if f["definitiva"] else "NON DEFINITIVA: mancano dati decisivi (" + "; ".join(q["decisivi_mancanti"]) + ")"}
