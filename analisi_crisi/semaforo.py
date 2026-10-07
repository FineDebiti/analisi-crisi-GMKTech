"""Semaforo di fattibilità del risanamento: regole fisse e soglie dichiarate. Supporto alla decisione, NON attestazione.

Tutte le soglie sono in SOGLIE e compaiono nel documento prodotto. Cambiare una soglia = decisione dell'avvocato (HG-2).
"""
from __future__ import annotations

VERDE, GIALLO, ROSSO = "VERDE", "GIALLO", "ROSSO"
PESO = {VERDE: 0, GIALLO: 1, ROSSO: 2}

SOGLIE = {
    "ebitda_margine_verde": 0.08,       # EBITDA / ricavi >= 8% -> verde; tra 0 e 8% giallo; <= 0 rosso
    "ricavi_var_verde": -0.05,          # variazione ricavi >= -5% verde; fino a -20% giallo; oltre rosso
    "ricavi_var_giallo": -0.20,
    "pn_giallo_su_passivo": -0.10,      # PN > 0 verde; PN >= -10% del passivo giallo; oltre rosso
    "scaduto_su_attivo_verde": 0.05,    # soglia allerta CCII (debiti tributari e previdenziali scaduti / attivo)
    "scaduto_su_attivo_giallo": 0.20,
    "copertura_verde": 0.60,            # finanza da continuità / massa passiva
    "copertura_giallo": 0.30,
    "quota_ebitda_destinabile": 0.50,   # quota dell'EBITDA medio destinabile ai creditori
    "anni_piano": 5,
    "realizzo_liquidità": 1.00, "realizzo_crediti": 0.50, "realizzo_rimanenze": 0.40, "realizzo_immobilizzazioni_materiali": 0.30,
    "stress_ricavi": (-0.10, -0.20), "stress_costi": 0.05,
    "costi_liquidazione": 0.15,         # costi della procedura liquidatoria detratti dal realizzo
}


def _colore(valore, verde, giallo, maggiore_meglio=True):
    if valore is None:
        return None
    if maggiore_meglio:
        return VERDE if valore >= verde else (GIALLO if valore >= giallo else ROSSO)
    return VERDE if valore <= verde else (GIALLO if valore <= giallo else ROSSO)


def peggiore(*colori):
    colori = [c for c in colori if c]
    return max(colori, key=PESO.get) if colori else None


def valuta(m: dict, soglie=None) -> dict:
    """`m`: metriche numeriche (None se non disponibili). Restituisce criteri, stress, verdetto e due soluzioni."""
    s = {**SOGLIE, **(soglie or {})}
    criteri = []

    def criterio(codice, nome, valore, colore, spiegazione, critico=False):
        criteri.append({"codice": codice, "nome": nome, "valore": valore, "colore": colore, "spiegazione": spiegazione, "critico": critico})

    ricavi, ebitda = m.get("ricavi"), m.get("ebitda_medio")
    margine = (m["ebitda"] / ricavi) if m.get("ebitda") is not None and ricavi else None
    c = (VERDE if margine >= s["ebitda_margine_verde"] else (GIALLO if margine > 0 else ROSSO)) if margine is not None else None
    criterio("redditivita", "Redditività operativa (EBITDA / ricavi)", margine, c,
             "Verde se almeno l'8%; giallo se positivo; rosso se nullo o negativo.", critico=True)
    var = m.get("ricavi_var")
    criterio("ricavi", "Andamento dei ricavi", var, _colore(var, s["ricavi_var_verde"], s["ricavi_var_giallo"]),
             "Verde se non peggiora oltre il 5%; giallo fino al 20%; rosso oltre.")
    pn, passivo = m.get("pn"), m.get("passivo")
    if pn is not None and passivo:
        c = VERDE if pn > 0 else (GIALLO if pn / passivo >= s["pn_giallo_su_passivo"] else ROSSO)
    else:
        c = None
    criterio("patrimonio", "Patrimonio netto", pn, c, "Verde se positivo; giallo se negativo ma entro il 10% del passivo; rosso oltre.")
    criterio("scaduto", "Debiti tributari e previdenziali scaduti / attivo", m.get("scaduto_su_attivo"),
             _colore(m.get("scaduto_su_attivo"), s["scaduto_su_attivo_verde"], s["scaduto_su_attivo_giallo"], maggiore_meglio=False),
             "Soglia di allerta CCII al 5% (verde); giallo fino al 20%; rosso oltre.")
    cop = m.get("copertura_continuita")
    criterio("capacita", "Capacità di soddisfare i creditori con la continuità", cop,
             _colore(cop, s["copertura_verde"], s["copertura_giallo"]),
             "Finanza destinabile in 5 anni / massa passiva: verde da 60%, giallo da 30%, rosso sotto.", critico=True)
    liq, con = m.get("recovery_liquidazione"), m.get("copertura_continuita")
    if liq is not None and con is not None:
        c = VERDE if con > liq * 1.05 else (GIALLO if con >= liq * 0.95 else ROSSO)
    else:
        c = None
    criterio("best_interest", "Convenienza rispetto alla liquidazione", None if liq is None or con is None else con - liq, c,
             "Verde se la continuità rende più della liquidazione (oltre il 5%); giallo se equivalente; rosso se rende meno.")
    mancanti = m.get("informazioni_mancanti") or []
    criterio("completezza", "Completezza delle informazioni", len(mancanti),
             VERDE if not mancanti else GIALLO,
             "Verde se non manca nulla; giallo se mancano documenti essenziali (mai rosso: l'assenza di un dato non è un giudizio negativo).")
    # Stress: ricavi -10%, -20% e costi +5% (a parità di altre condizioni)
    stress = []
    if m.get("ricavi") and m.get("costi_operativi") is not None:
        for nome, dr, dc in ((f"Ricavi {int(s['stress_ricavi'][0]*100)}%", s["stress_ricavi"][0], 0), (f"Ricavi {int(s['stress_ricavi'][1]*100)}%", s["stress_ricavi"][1], 0),
                             (f"Costi +{int(s['stress_costi']*100)}%", 0, s["stress_costi"])):
            eb = m["ricavi"] * (1 + dr) - m["costi_operativi"] * (1 + dc)
            fin = max(0, eb * s["quota_ebitda_destinabile"]) * s["anni_piano"]
            cp = fin / m["passivo"] if m.get("passivo") else None
            stress.append({"scenario": nome, "ebitda": eb, "finanza": fin, "copertura": cp,
                           "colore": _colore(cp, s["copertura_verde"], s["copertura_giallo"])})
    # Verdetto: rosso se un criterio critico è rosso; giallo se manca qualche criterio o ci sono 2+ gialli; altrimenti verde
    complessivo = peggiore(*(x["colore"] for x in criteri))
    rossi_critici = [x for x in criteri if x["critico"] and x["colore"] == ROSSO]
    gialli = [x for x in criteri if x["colore"] == GIALLO]
    if rossi_critici or sum(1 for x in criteri if x["colore"] == ROSSO) >= 2:
        verdetto = ROSSO
    elif complessivo == ROSSO or len(gialli) >= 2:
        verdetto = GIALLO
    else:
        verdetto = VERDE
    nota_stress = None
    if verdetto == VERDE and stress and stress[0]["colore"] == ROSSO:
        verdetto, nota_stress = GIALLO, "Il piano non regge nemmeno lo stress più lieve (ricavi -10%): verdetto abbassato a giallo."
    testi = {
        VERDE: "Risanamento PERCORRIBILE: la continuità genera risorse adeguate e conviene ai creditori rispetto alla liquidazione.",
        GIALLO: "Risanamento PERCORRIBILE SOLO A CONDIZIONI: restano punti critici o informazioni mancanti da sciogliere prima di proporre un piano.",
        ROSSO: "Risanamento NON PERCORRIBILE allo stato: la continuità non genera risorse sufficienti. Valutare le alternative liquidatorie.",
    }
    return {"criteri": criteri, "stress": stress, "verdetto": verdetto, "esito": testi[verdetto], "nota_stress": nota_stress, "soglie": s,
            "sconosciuti": [x["nome"] for x in criteri if x["colore"] is None]}
