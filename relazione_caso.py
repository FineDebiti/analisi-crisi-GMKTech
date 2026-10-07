"""Relazione Word di preanalisi (modello CNC) con semaforo di fattibilità, da un caso già estratto.

Uso:  python relazione_caso.py --bilancio b.json --ruoli r.json --visura v.json --fatti fatti.json --out Relazione.docx
                              [--situazione s.json] [--modello Template.docx]
La relazione contiene valori: va salvata solo nella cartella riservata. A video si stampano soltanto i colori dei semafori.
Supporto alla decisione, non attestazione: ogni dato è marcato FATTO / INFERENZA / DA VERIFICARE.
"""
import html
import json
import re
import sys
from datetime import date
from pathlib import Path

from analisi_crisi import semaforo as sem
from analisi_crisi import word_xml as w

PROGETTO = Path(__file__).resolve().parent
MESI = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre"]
CLASSI = {"erariale": "Erario (Agenzia delle Entrate e altri uffici finanziari)", "previdenziale": "Enti previdenziali (INPS / INAIL)",
          "enti_locali": "Enti locali e Regione", "camera_commercio": "Camera di Commercio", "altro": "Altri enti"}


ND = "non disponibile"


def eur(v):
    return ND if v is None else "€ " + f"{round(v):,}".replace(",", ".")


def pct(v, cifre=0):
    return ND if v is None else f"{v * 100:.{cifre}f}".replace(".", ",") + "%"


def carica(percorso):
    return json.loads(Path(percorso).read_text(encoding="utf-8")) if percorso else None


def data_it(iso):
    return f"{iso[8:10]}/{iso[5:7]}/{iso[:4]}" if iso else "data non rilevata"


def leggi_bilancio(b):
    per = {}
    for k in ("dati", "controllo", "residui"):
        for d in b.get(k, []):
            if d["valore"] is not None:
                per[d["chiave"], d["anno"]] = d
    anni = {e["anno"]: e["data_chiusura"][:4] for e in b["esercizi"]}
    per["_date"] = {e["anno"]: e["data_chiusura"] for e in b["esercizi"]}
    return per, anni


def fonte_str(per, chiavi, anni_=(-1,)):
    """Documento e pagina da cui provengono i dati usati; mai un valore inventato."""
    out = []
    for k in chiavi:
        for a in anni_:
            d = per.get((k, a))
            if d:
                f = d.get("fonte") or {}
                s = f"{f.get('file', 'documento n.d.')}, " + (f"p. {f['pagina']}" if f.get("pagina") else "pagina non rilevata")
                if s not in out:
                    out.append(s)
    return "; ".join(out) if out else ND


def pagine_ruoli(ruoli):
    ps = []
    for d in ruoli["documenti"]:
        p = d.get("pagine")
        if isinstance(p, int):
            ps.append(p)
        elif isinstance(p, (list, tuple)):
            ps += [q for q in p if isinstance(q, int)]
    return f"pp. {min(ps)}-{max(ps)}" if ps else "pagine non rilevate"


def fonte_ruoli(ruoli):
    if not ruoli["documenti"]:
        return "estratti di ruolo non disponibili"
    return f"{(ruoli.get('documento') or {}).get('file', 'estratto di ruolo')}, {pagine_ruoli(ruoli)}"


def metriche(bil, ruoli, fatti, s):
    """Nessun valore mancante viene sostituito con zero: resta None e il criterio diventa 'non disponibile'."""
    per, anni = bil
    g = lambda k, a: per[k, a]["valore"] if (k, a) in per else None
    es = {}
    for a in (-2, -1):
        A, B, amm = g("ce.A", a), g("ce.B", a), g("ce.B10", a)
        es[a] = {"anno": anni.get(a), "data": per["_date"].get(a), "ricavi": g("ce.A1", a), "altri": g("ce.A5", a), "A": A, "B": B, "amm": amm,
                 "ebitda": (A - B + amm) if None not in (A, B, amm) else None, "utile": g("ce.U21", a),
                 "personale": g("ce.B9", a), "costi_op": (B - amm) if B is not None and amm is not None else None}
    u = es[-1]
    docs = ruoli["documenti"]
    senza_totale = sum(1 for d in docs if "totale_documento" not in d["totali"])
    totale_ruoli = sum(d["totali"].get("totale_documento", 0) for d in docs) if docs else None
    per_classe = {}
    for d in docs:
        cl = {e["classe"] for e in d["enti"]}
        k = cl.pop() if len(cl) == 1 else "misto"
        per_classe[k] = per_classe.get(k, 0) + d["totali"].get("totale_documento", 0)
    attivo, pn, debiti = g("sp.tot_attivo", -1), g("sp.tot_pn", -1), g("sp.tot_debiti", -1)
    massa = max(debiti, totale_ruoli or 0) if debiti is not None else None
    massa_da = None if massa is None else ("ruoli (aggiornato)" if (totale_ruoli or 0) > debiti else "debiti di bilancio (storico)")
    ebs = [e["ebitda"] for e in es.values() if e["ebitda"] is not None]
    ebitda_medio = sum(ebs) / len(ebs) if ebs else None
    finanza_anno = max(0, ebitda_medio) * s["quota_ebitda_destinabile"] if ebitda_medio is not None else None
    finanza_tot = finanza_anno * s["anni_piano"] if finanza_anno is not None else None
    comp = {k: g(k, -1) for k in ("sp.disp_liquide", "sp.crediti_entro", "sp.rimanenze", "sp.imm_mat")}
    crediti_soci = g("sp.crediti_soci", -1)
    realizzo = lordo = None
    if None not in comp.values():
        lordo = (comp["sp.disp_liquide"] * s["realizzo_liquidità"] + (comp["sp.crediti_entro"] + (crediti_soci or 0)) * s["realizzo_crediti"]
                 + comp["sp.rimanenze"] * s["realizzo_rimanenze"] + comp["sp.imm_mat"] * s["realizzo_immobilizzazioni_materiali"])
        realizzo = lordo * (1 - s["costi_liquidazione"])
    mancanti = []
    if not docs:
        mancanti.append("Estratti di ruolo (debiti erariali e previdenziali)")
    if fatti.get("cr") in ("non_pervenuta", "non_acquisita"):
        mancanti.append("Centrale dei Rischi (esposizione bancaria)")
    if fatti.get("situazione_assente", True):
        mancanti.append("Situazione contabile aggiornata")
    if fatti.get("pignoramenti_non_letti"):
        mancanti.append("Atti di pignoramento (lettura dei dati)")
    scaduto = sum(v for k, v in per_classe.items() if k != "altro")
    m = {"ricavi": u["ricavi"], "ebitda": u["ebitda"], "ebitda_medio": ebitda_medio, "costi_operativi": u["costi_op"],
         "ricavi_var": ((u["ricavi"] - es[-2]["ricavi"]) / es[-2]["ricavi"]) if u["ricavi"] is not None and es[-2]["ricavi"] else None,
         "pn": pn, "passivo": massa, "scaduto_su_attivo": (scaduto / attivo) if attivo and totale_ruoli is not None else None,
         "copertura_continuita": (finanza_tot / massa) if finanza_tot is not None and massa else None,
         "recovery_liquidazione": min(1, realizzo / massa) if realizzo is not None and massa else None,
         "informazioni_mancanti": mancanti}
    extra = {"esercizi": es, "totale_ruoli": totale_ruoli, "per_classe": per_classe, "attivo": attivo, "debiti": debiti, "massa": massa, "massa_da": massa_da,
             "finanza_anno": finanza_anno, "finanza_tot": finanza_tot, "realizzo": realizzo, "lordo": lordo, "comp": comp, "crediti_soci": crediti_soci,
             "scaduto": scaduto, "ruoli_senza_totale": senza_totale, "g": g, "per": per}
    return m, extra


def schede(m, x, esito, s, bil, ruoli, fatti):
    """Una scheda per ogni semaforo: valore assoluto, %, formula, natura e data, fonte, soglia, motivazione."""
    per, _ = bil
    es, u, p = x["esercizi"], x["esercizi"][-1], x["esercizi"][-2]
    d1, d0 = data_it(u["data"]), data_it(p["data"])
    dr = ruoli.get("data_estratto") or "data non rilevata"
    col = {c["codice"]: c["colore"] for c in esito["criteri"]}
    nd_mot = "Non valutabile: almeno un dato necessario non è disponibile. Nessun giudizio assegnato (l'assenza del dato non è un giudizio negativo)."

    def mot(codice, ind, verde, giallo, rosso):
        c = col[codice]
        return nd_mot if c is None else f"{ind}: { {'VERDE': verde, 'GIALLO': giallo, 'ROSSO': rosso}[c]}"

    marg = (m["ebitda"] / m["ricavi"]) if m["ebitda"] is not None and m["ricavi"] else None
    doc_bil = "bilancio di verifica provvisorio (non depositato)" if fatti.get("bilancio_provvisorio") else "bilancio depositato"
    S = {}
    S["redditivita"] = dict(
        sintesi=f"EBITDA {eur(m['ebitda'])} / ricavi {eur(m['ricavi'])} = {pct(marg, 1)}", natura=f"STORICO, esercizio al {d1}",
        righe=[("Valore assoluto", f"EBITDA (numeratore): {eur(u['ebitda'])}\nRicavi (denominatore): {eur(u['ricavi'])}\n"
                                   f"Composizione: valore della produzione {eur(u['A'])} - costi della produzione {eur(u['B'])} + ammortamenti e svalutazioni {eur(u['amm'])}"),
               ("Indicatore percentuale", pct(marg, 1)), ("Formula", "(A - B + B10) / A1  =  (valore produzione - costi produzione + ammortamenti) / ricavi vendite e prestazioni"),
               ("Natura e data del dato", f"STORICO - " + doc_bil + ", esercizio chiuso al {d1}. Dato aggiornato: " + ("non disponibile." if fatti.get("situazione_assente", True) else "situazione contabile acquisita, non usata in questo calcolo.")),
               ("Documento e pagina", fonte_str(per, ("ce.A", "ce.B", "ce.B10", "ce.A1"))),
               ("Soglia utilizzata", f"Verde se >= {pct(s['ebitda_margine_verde'])}; giallo se maggiore di 0 e inferiore alla soglia verde; rosso se <= 0"),
               ("Motivazione", mot("redditivita", f"margine {pct(marg, 1)}", "margine operativo pari o superiore alla soglia", "margine positivo ma sotto la soglia verde",
                                   "la gestione caratteristica non genera margine (EBITDA nullo o negativo)"))])
    var_ass = (u["ricavi"] - p["ricavi"]) if u["ricavi"] is not None and p["ricavi"] is not None else None
    S["ricavi"] = dict(
        sintesi=f"{eur(u['ricavi'])} vs {eur(p['ricavi'])} = {pct(m['ricavi_var'], 1)}", natura=f"STORICO, esercizi al {d0} e al {d1}",
        righe=[("Valore assoluto", f"Ricavi {u['anno']} (primo termine della differenza): {eur(u['ricavi'])}\nRicavi {p['anno']} (denominatore): {eur(p['ricavi'])}\nVariazione assoluta: {eur(var_ass)}"),
               ("Indicatore percentuale", pct(m["ricavi_var"], 1)), ("Formula", f"(ricavi {u['anno']} - ricavi {p['anno']}) / ricavi {p['anno']}   [voce A1]"),
               ("Natura e data del dato", f"STORICO - " + doc_bil + f", esercizi chiusi al {d0} e al {d1}"),
               ("Documento e pagina", fonte_str(per, ("ce.A1",), (-2, -1))),
               ("Soglia utilizzata", f"Verde se >= {pct(s['ricavi_var_verde'])}; giallo se >= {pct(s['ricavi_var_giallo'])}; rosso se inferiore"),
               ("Motivazione", mot("ricavi", f"variazione {pct(m['ricavi_var'], 1)}", "calo contenuto o crescita", "calo significativo ma entro la soglia gialla", "calo superiore alla soglia gialla"))])
    ratio_pn = (m["pn"] / m["passivo"]) if m["pn"] is not None and m["passivo"] else None
    S["patrimonio"] = dict(
        sintesi=f"PN {eur(m['pn'])} / massa passiva {eur(m['passivo'])} = {pct(ratio_pn, 1)}", natura=f"STORICO al {d1}" + (f"; massa: {x['massa_da']}" if x["massa_da"] else ""),
        righe=[("Valore assoluto", f"Patrimonio netto (numeratore): {eur(m['pn'])}\nMassa passiva (denominatore): {eur(m['passivo'])}\n"
                                   f"di cui debiti di bilancio {eur(x['debiti'])} (STORICO) e totale ruoli {eur(x['totale_ruoli'])} (AGGIORNATO al {dr}); si assume il maggiore: {x['massa_da'] or ND}"),
               ("Indicatore percentuale", pct(ratio_pn, 1)), ("Formula", "patrimonio netto (voce A dello stato patrimoniale passivo) / massa passiva;  massa passiva = max(debiti D di bilancio; totale ruoli)"),
               ("Natura e data del dato", f"PN: STORICO al {d1}. Ruoli: AGGIORNATO al {dr}. Debiti di bilancio: STORICO al {d1}."),
               ("Documento e pagina", fonte_str(per, ("sp.tot_pn", "sp.tot_debiti")) + "; ruoli: " + fonte_ruoli(ruoli)),
               ("Soglia utilizzata", f"Verde se PN > 0; giallo se PN negativo ma >= {pct(s['pn_giallo_su_passivo'])} della massa passiva; rosso oltre"),
               ("Motivazione", mot("patrimonio", f"PN {eur(m['pn'])}, pari a {pct(ratio_pn, 1)} della massa passiva", "patrimonio netto positivo", "patrimonio netto negativo ma contenuto", "patrimonio netto negativo e oltre la soglia gialla"))])
    S["scaduto"] = dict(
        sintesi=f"{eur(x['scaduto'])} / attivo {eur(x['attivo'])} = {pct(m['scaduto_su_attivo'], 1)}", natura=f"AGGIORNATO ruoli al {dr}; attivo STORICO al {d1}",
        righe=[("Valore assoluto", f"Debiti tributari e previdenziali da ruoli (numeratore): {eur(x['scaduto'])}\nTotale attivo (denominatore): {eur(x['attivo'])}"),
               ("Indicatore percentuale", pct(m["scaduto_su_attivo"], 1)), ("Formula", "totale ruoli erariali, previdenziali, enti locali e camera di commercio (escluso 'altri enti') / totale attivo dello stato patrimoniale"),
               ("Natura e data del dato", f"Numeratore: AGGIORNATO, estratti di ruolo del {dr}. Denominatore: STORICO, bilancio al {d1}. I due termini hanno date diverse."),
               ("Documento e pagina", f"{fonte_ruoli(ruoli)}; attivo: {fonte_str(per, ('sp.tot_attivo',))}"),
               ("Soglia utilizzata", f"Verde se <= {pct(s['scaduto_su_attivo_verde'])} (allerta CCII); giallo se <= {pct(s['scaduto_su_attivo_giallo'])}; rosso oltre"),
               ("Motivazione", mot("scaduto", f"incidenza {pct(m['scaduto_su_attivo'], 1)}", "sotto la soglia di allerta", "oltre la soglia di allerta ma entro la soglia gialla", "oltre la soglia gialla")
                + (f" Attenzione: {x['ruoli_senza_totale']} documento/i di ruolo senza totale letto." if x["ruoli_senza_totale"] else ""))])
    S["capacita"] = dict(
        sintesi=f"{eur(x['finanza_tot'])} / massa {eur(m['passivo'])} = {pct(m['copertura_continuita'], 1)}", natura=f"STIMA su dati storici ({d0}, {d1})",
        righe=[("Valore assoluto", f"Finanza destinabile in {s['anni_piano']} anni (numeratore): {eur(x['finanza_tot'])}\nMassa passiva (denominatore): {eur(m['passivo'])}\n"
                                   f"EBITDA medio {eur(m['ebitda_medio'])}; finanza annua {eur(x['finanza_anno'])}"),
               ("Indicatore percentuale", pct(m["copertura_continuita"], 1)),
               ("Formula", f"(max(0; EBITDA medio) x {pct(s['quota_ebitda_destinabile'])} x {s['anni_piano']} anni) / massa passiva;  EBITDA medio = media dei due esercizi disponibili"),
               ("Natura e data del dato", "STIMA - proiezione prudenziale basata su dati storici, con ipotesi di quota e durata dichiarate. Non è un piano."),
               ("Documento e pagina", fonte_str(per, ("ce.A", "ce.B", "ce.B10", "sp.tot_debiti"), (-2, -1))),
               ("Soglia utilizzata", f"Verde se >= {pct(s['copertura_verde'])}; giallo se >= {pct(s['copertura_giallo'])}; rosso sotto"),
               ("Motivazione", mot("capacita", f"copertura {pct(m['copertura_continuita'], 1)}", "la continuità soddisfa in misura adeguata i creditori", "soddisfazione parziale, da migliorare", "la continuità genera risorse insufficienti"))])
    c = x["comp"]
    S["best_interest"] = dict(
        sintesi=f"continuità {pct(m['copertura_continuita'], 1)} vs liquidazione {pct(m['recovery_liquidazione'], 1)} (realizzo {eur(x['realizzo'])})", natura=f"STIMA su dati storici ({d1})",
        righe=[("Valore assoluto", f"Continuità: {eur(x['finanza_tot'])}\nLiquidazione (realizzo netto): {eur(x['realizzo'])} su massa passiva {eur(m['passivo'])}\n"
                                   f"Componenti: liquidità {eur(c['sp.disp_liquide'])}; crediti entro l'esercizio {eur(c['sp.crediti_entro'])}"
                                   + (f" + crediti verso soci {eur(x['crediti_soci'])}" if x["crediti_soci"] else " (crediti verso soci: non rilevati, non inclusi)")
                                   + f"; rimanenze {eur(c['sp.rimanenze'])}; immobilizzazioni materiali {eur(c['sp.imm_mat'])}"),
               ("Indicatore percentuale", f"Continuità {pct(m['copertura_continuita'], 1)}; liquidazione {pct(m['recovery_liquidazione'], 1)}"),
               ("Formula", f"liquidazione = [liquidità x {pct(s['realizzo_liquidità'])} + crediti x {pct(s['realizzo_crediti'])} + rimanenze x {pct(s['realizzo_rimanenze'])} + imm. materiali x {pct(s['realizzo_immobilizzazioni_materiali'])}] x (1 - {pct(s['costi_liquidazione'])}) / massa passiva (max 100%)"),
               ("Natura e data del dato", f"STIMA - coefficienti di realizzo standard applicati a valori STORICI al {d1}. Da confermare con perizie."),
               ("Documento e pagina", fonte_str(per, ("sp.disp_liquide", "sp.crediti_entro", "sp.crediti_soci", "sp.rimanenze", "sp.imm_mat"))),
               ("Soglia utilizzata", "Verde se la continuità supera la liquidazione di oltre il 5%; giallo se equivalente (+/-5%); rosso se rende meno"),
               ("Motivazione", mot("best_interest", f"continuità {pct(m['copertura_continuita'], 1)} contro liquidazione {pct(m['recovery_liquidazione'], 1)}", "la continuità conviene ai creditori", "i due scenari sono equivalenti", "la liquidazione rende più della continuità"))])
    mc = m["informazioni_mancanti"]
    S["completezza"] = dict(
        sintesi=f"{len(mc)} informazione/i mancante/i", natura="Stato della documentazione",
        righe=[("Valore assoluto", f"Informazioni mancanti: {len(mc)}\n" + ("\n".join("- " + i for i in mc) if mc else "nessuna")), ("Indicatore percentuale", "non applicabile"),
               ("Formula", "conteggio dei documenti essenziali non acquisiti o non letti"), ("Natura e data del dato", "Stato al momento della preanalisi"),
               ("Documento e pagina", "non applicabile"), ("Soglia utilizzata", "Verde se non manca nulla; giallo se manca almeno un documento essenziale; mai rosso"),
               ("Motivazione", "Nessun documento essenziale mancante." if not mc else "Mancano documenti essenziali: la valutazione resta provvisoria; l'assenza di un dato non è un giudizio negativo.")])
    return S


def costruisci(bil, ruoli, visura, fatti, soglie=None, anonimizza=False):
    ruoli = ruoli or {"documenti": [], "controlli": [], "documento": {}}
    visura = visura or {"campi": {"denominazione": {"valore": fatti.get("nome", "[ragione sociale]"), "stato": "DA VERIFICARE"}}, "avvisi": []}
    s = {**sem.SOGLIE, **(soglie or {})}
    m, x = metriche(bil, ruoli, fatti, s)
    esito = sem.valuta(m, s)
    c = visura["campi"]
    nome = c.get("denominazione", {}).get("valore", "[ragione sociale]")
    mese = f"{MESI[date.today().month - 1]} {date.today().year}"
    P = []
    P += [w.par(w.run("PREANALISI ECONOMICO-FINANZIARIA", True, dim=44), "Corpo", "center"),
          w.par(w.run("E VALUTAZIONE DI PERCORRIBILITÀ DEL RISANAMENTO", True, dim=32), "Corpo", "center"),
          w.par(w.run(nome, True, dim=36), "Corpo", "center"),
          w.par(w.run("Composizione Negoziata della Crisi - supporto alla decisione (non è un'attestazione)", dim=22), "Corpo", "center"),
          w.par(w.run(f"Documento di lavoro riservato - {mese}", corsivo=True), "Corpo", "center")]
    # Sintesi in testa
    P.append(w.riquadro(f"SEMAFORO FINALE: {w.ETICHETTE[esito['verdetto']]}", esito["esito"] + ("\n" + esito["nota_stress"] if esito["nota_stress"] else ""), esito["verdetto"]))
    if anonimizza:
        P.append(w.par(w.run("VERSIONE ANONIMIZZATA. Sono stati sostituiti con codici coerenti: denominazione e nominativi (anche come singoli termini), codice fiscale, REA, PEC, sede e nomi dei file. "
                             "Importi, date, percentuali e relazioni economiche sono invariati. Nessun'altra omissione. La legenda dei codici è conservata a parte nella cartella riservata.", True, colore="9C5700"), "Corpo"))
    S = schede(m, x, esito, s, bil, ruoli, fatti)
    righe = [["Tema", "Semaforo", "Numeri che sostengono il giudizio", "Natura e data"]]
    colori = {}
    for i, cr in enumerate(esito["criteri"], 1):
        righe.append([cr["nome"], w.ETICHETTE[cr["colore"]], S[cr["codice"]]["sintesi"], S[cr["codice"]]["natura"]])
        colori[(i, 1)] = cr["colore"]
    P += [w.titolo("Quadro di sintesi per macro-tema"), w.tabella(righe, [2200, 1350, 3850, 2300], colori=colori),
          w.par(w.run("Natura del dato: STORICO = bilancio (depositato o, se indicato, provvisorio non depositato); AGGIORNATO = documento recente (ruoli, situazione contabile); STIMA = calcolo con ipotesi dichiarate. "
                      "'non disponibile' = dato assente: non è zero e non produce un giudizio negativo.", corsivo=True)),
          w.titolo("Schede dei semafori: dai numeri al giudizio")]
    for cr in esito["criteri"]:
        sc = S[cr["codice"]]
        P += [w.tabella([[cr["nome"], w.ETICHETTE[cr["colore"]]]] + [[a, b] for a, b in sc["righe"]], [2500, 7200], colori={(0, 1): cr["colore"]})]
    # 1 Premessa
    P += [w.titolo("1. Premessa e metodo"),
          w.par("La presente preanalisi verifica, sulla base della documentazione disponibile, se esistano i presupposti per un percorso di risanamento "
                "in Composizione Negoziata e quanto potrebbe ricavare il ceto creditorio rispetto alla liquidazione. Le regole di valutazione sono fisse e "
                "dichiarate nella sezione 13: il semaforo è un supporto alla decisione del professionista, non un'attestazione né un piano."),
          w.par(f"Ogni dato è marcato FATTO (letto dal documento), INFERENZA (ricavato o riclassificato) o DA VERIFICARE. Ipotesi di lavoro: si destina ai creditori il "
                f"{pct(s['quota_ebitda_destinabile'])} dell'EBITDA medio per {s['anni_piano']} anni.")]
    # 2 Profilo
    nat = "finanziaria/debitoria" if (m["ebitda_medio"] or 0) > 0 else "industriale (la gestione non produce margine operativo)"
    P += [w.titolo("2. Profilo dell'impresa e natura della crisi"),
          w.tabella([["Dato", "Valore", "Stato"]] + [[lab, c[k]["valore"], c[k]["stato"]] for lab, k in (
              ("Denominazione", "denominazione"), ("Forma giuridica", "forma_giuridica"), ("Sede legale", "sede_legale"), ("REA", "rea"),
              ("Stato dell'impresa", "stato_impresa"), ("Liquidatore", "liquidatore")) if k in c], [2600, 5600, 1500]),
          w.par(f"Natura della crisi (regola: EBITDA medio positivo = crisi finanziaria, altrimenti industriale): {nat}.")]
    for nota in fatti.get("note_profilo", []):
        P.append(w.par(w.run(nota, corsivo=True)))
    for a in visura.get("avvisi", []):
        P.append(w.par(w.run("Avviso della visura: " + a, colore="9C5700")))
    # 3 Analisi economica
    P.append(w.titolo("3. Analisi economica"))
    for a in (-2, -1):
        e = x["esercizi"][a]
        f = lambda *k: fonte_str(bil[0], k, (a,))
        nt = f"STORICO al {data_it(e['data'])}"
        P += [w.sottotitolo(f"Esercizio {e['anno']} (chiuso al {data_it(e['data'])})"),
              w.tabella([["Voce", "Importo", "Natura", "Documento e pagina"],
                         ["Ricavi vendite/prestazioni", eur(e["ricavi"]), nt + " - FATTO", f("ce.A1")], ["Altri ricavi e proventi", eur(e["altri"]), nt + " - FATTO", f("ce.A5")],
                         ["Valore della produzione", eur(e["A"]), nt + " - FATTO", f("ce.A")], ["Costi della produzione", eur(e["B"]), nt + " - FATTO", f("ce.B")],
                         ["di cui ammortamenti e svalutazioni", eur(e["amm"]), nt + " - FATTO", f("ce.B10")],
                         ["EBITDA (A - B + ammortamenti)", eur(e["ebitda"]), nt + " - INFERENZA", "calcolato"],
                         ["Utile (perdita) d'esercizio", eur(e["utile"]), nt + " - FATTO", f("ce.U21")]], [2700, 1600, 2300, 3100], destra=(1,))]
    if m["ricavi_var"] is not None:
        P.append(w.par(f"Variazione dei ricavi tra i due esercizi: {pct(m['ricavi_var'], 1)}."))
    # 4 Dato corrente
    P += [w.titolo("4. Il dato corrente e la necessità di prudenza"),
          w.par("Situazione contabile aggiornata: " + ("non disponibile. Nessun valore infra-annuale è stato assunto come base del piano." if fatti.get("situazione_assente", True)
                                                      else "acquisita (vedere dati nel modello)."))]
    # 5 Indebitamento
    if not ruoli["documenti"]:
        P += [w.titolo("5. Analisi dell'indebitamento da ruoli"), w.par("Estratti di ruolo: non disponibili. L'esposizione verso Erario ed enti previdenziali non è nota e non è stata assunta pari a zero.")]
    else:
        P += [w.titolo("5. Analisi dell'indebitamento da ruoli"),
              w.par(f"AGGIORNATO al {ruoli.get('data_estratto') or 'data non rilevata'}. Fonte: estratti di ruolo dell'Agente della Riscossione ({len(ruoli['documenti'])} documenti tra cartelle e avvisi di addebito); {fonte_ruoli(ruoli)}."),
              w.tabella([["Creditore (classe)", "Totale residuo con oneri (AGGIORNATO)"]] + [[CLASSI.get(k, "Più classi (documento multi-ente)" if k == "misto" else k), eur(v)] for k, v in sorted(x["per_classe"].items(), key=lambda kv: -kv[1])]
                        + [["TOTALE RUOLI", eur(x["totale_ruoli"])]], [6200, 3500], destra=(1,)),
              w.par("Controlli aritmetici sul documento: " + ("tutti superati." if all(c["esito"] in ("OK", "NON ESEGUIBILE") for c in ruoli["controlli"]) else "ALCUNI NON TORNANO, verificare."))]
        sosp = sum(1 for d in ruoli["documenti"] for r_ in d["righe"] if r_.get("sospeso"))
        if sosp:
            P.append(w.par(f"Voci in sospensione: {sosp}."))
        P.append(w.par(w.run("Classificazione: tutti i ruoli sono trattati come privilegio generale tributi e contributi; sanzioni e interessi possono essere chirografari "
                             "(da distinguere quando si dispone del dettaglio per natura del credito).", corsivo=True)))
    # 6 Ulteriore indebitamento
    P.append(w.titolo("6. Ulteriore indebitamento da verificare"))
    righe = [["Fonte", "Esito", "Stato"]] + [[e["fonte"], e["esito"], e["stato"]] for e in fatti.get("esiti", [])]
    if fatti.get("cr") in ("non_pervenuta", "non_acquisita"):
        righe.append(["Centrale dei Rischi (Banca d'Italia)", ("Richiesta non pervenuta" if fatti.get("cr") == "non_pervenuta" else "Non acquisita") + ": esposizione bancaria NON nota", "DA VERIFICARE"])
    colori = {i: None for i in range(len(righe))}
    P.append(w.tabella(righe, [3300, 4900, 1500], colori={(i, 2): ("VERDE" if r_[2] == "FATTO" else "GIALLO") for i, r_ in enumerate(righe) if i}))
    if fatti.get("pignoramenti_non_letti"):
        P.append(w.par(f"Atti di pignoramento acquisiti in scansione: {fatti['pignoramenti_atti']} (lettura con OCR da completare: creditore, data, importo)."))
    # 7 Diagnosi
    fav, crit = [], []
    if (m["ebitda_medio"] or 0) > 0:
        fav.append("la gestione produce un margine operativo positivo")
    else:
        crit.append("la gestione non produce un margine operativo positivo")
    if m["ricavi_var"] is not None:
        (fav if m["ricavi_var"] >= -0.05 else crit).append(f"i ricavi variano del {pct(m['ricavi_var'], 1)} tra gli esercizi")
    if m["pn"] is not None:
        (fav if m["pn"] > 0 else crit).append("il patrimonio netto è " + ("positivo" if m["pn"] > 0 else "negativo"))
    P += [w.titolo("7. Diagnosi preliminare della crisi"),
          w.par("Elementi favorevoli: " + ("; ".join(fav) if fav else "nessuno rilevato dai dati disponibili") + "."),
          w.par("Elementi critici: " + ("; ".join(crit) if crit else "nessuno rilevato dai dati disponibili") + ".")]
    # 8 Patrimonio e liquidazione
    P += [w.titolo("8. Patrimonio e scenario liquidatorio"),
          w.par("STIMA prudenziale con coefficienti standard di realizzo (sezione 13), al netto dei costi della procedura. È una INFERENZA da confermare con perizie."),
          w.tabella([["Voce", "Valore", "Natura"], ["Realizzo stimato in liquidazione", eur(x["realizzo"]), "STIMA"], ["Massa passiva considerata", eur(x["massa"]), x["massa_da"] or ND],
                     ["Soddisfazione stimata in liquidazione", pct(m["recovery_liquidazione"]), "STIMA"]], [5000, 2400, 2300], destra=(1,))]
    # 9 Capacità
    P += [w.titolo("9. Capacità di risanamento con la continuità"),
          w.tabella([["Voce", "Valore", "Natura"], ["EBITDA medio degli ultimi due esercizi", eur(m["ebitda_medio"]), "STORICO - INFERENZA"],
                     [f"Finanza annua destinabile ({pct(s['quota_ebitda_destinabile'])} dell'EBITDA medio)", eur(x["finanza_anno"]), "STIMA"],
                     [f"Finanza complessiva in {s['anni_piano']} anni", eur(x["finanza_tot"]), "STIMA"],
                     ["Soddisfazione stimata con la continuità", pct(m["copertura_continuita"]), "STIMA"],
                     ["Soddisfazione stimata in liquidazione", pct(m["recovery_liquidazione"]), "STIMA"]], [5000, 2400, 2300], destra=(1,))]
    # 10 Stress
    if esito["stress"]:
        righe = [["Scenario", "EBITDA", "Finanza in 5 anni", "Soddisfazione", "Semaforo"]]
        col = {}
        for i, st in enumerate(esito["stress"], 1):
            righe.append([st["scenario"], eur(st["ebitda"]), eur(st["finanza"]), pct(st["copertura"]), w.ETICHETTE[st["colore"]]])
            col[(i, 4)] = st["colore"]
        P += [w.titolo("10. Stress test minimo (STIMA)"), w.tabella(righe, [2300, 1800, 2100, 1700, 1800], colori=col, destra=(1, 2, 3))]
    # 11 Giudizio e semaforo finale
    P += [w.titolo("11. Giudizio preliminare di fattibilità e semaforo finale"),
          w.riquadro(f"{w.ETICHETTE[esito['verdetto']]}", esito["esito"], esito["verdetto"])]
    if esito["sconosciuti"]:
        P.append(w.par("Criteri non valutabili per mancanza di dati: " + "; ".join(esito["sconosciuti"]) + "."))
    if esito["verdetto"] == sem.ROSSO:
        opz = [("A", "Strumento liquidatorio ordinato", "Se la continuità non regge, valutare la liquidazione (controllata o giudiziale, secondo i requisiti) per massimizzare il realizzo ed evitare l'aggravio di interessi e azioni esecutive."),
               ("B", "Ripartenza con nuova finanza esterna", "Verificare se un terzo (soci, investitori, affitto o cessione d'azienda) possa apportare risorse tali da superare il realizzo liquidatorio; solo in tal caso riconsiderare la CNC.")]
    elif esito["verdetto"] == sem.GIALLO:
        opz = [("A", "CNC condizionata", "Procedere con la CNC solo dopo aver sciolto i punti in giallo (documenti mancanti, stress test) e aver dimostrato il surplus rispetto alla liquidazione."),
               ("B", "Accordo con il solo debito pubblico", "In alternativa, trattare separatamente il debito erariale e previdenziale (transazione fiscale/rateazione) mantenendo la gestione corrente regolare.")]
    else:
        opz = [("A", "CNC con piano di continuità", "Procedere con la Composizione Negoziata: piano industriale prudenziale, destinazione della finanza annua e proposta a livelli (liquidazione, debito pubblico, chirografari)."),
               ("B", "Accordo di ristrutturazione", "Se si raggiungono le adesioni, valutare un accordo di ristrutturazione dei debiti con transazione fiscale.")]
    P.append(w.sottotitolo("Soluzioni percorribili (nell'ordine consigliato)"))
    P += [w.par(w.run(f"{o[0]}. {o[1]}: ", True) + w.run(o[2])) for o in opz]
    # 12 Documentazione
    P += [w.titolo("12. Documentazione ancora necessaria"), *[w.elenco(t, "List Number") for t in (
        (["Richiesta della Centrale dei Rischi (Banca d'Italia): esposizione bancaria"] if fatti.get("cr") in ("non_pervenuta", "non_acquisita") else [])
        + (["Situazione contabile aggiornata e bilancio di verifica"] if fatti.get("situazione_assente", True) else [])
        + (["Lettura e riepilogo degli atti di pignoramento (creditore, data, importo)"] if fatti.get("pignoramenti_non_letti") else [])
        + ["Dettaglio delle cartelle per natura del credito (tributo, sanzioni, interessi)", "Posizioni INPS/INAIL aggiornate",
           "Elenco analitico di fornitori e altri debiti", "Libro cespiti e valutazione del magazzino", "Budget e piano di tesoreria dei primi dodici mesi"])]]
    # 13 Soglie
    soglie_tab = [["Parametro", "Valore"], ["EBITDA / ricavi per il verde", pct(s["ebitda_margine_verde"])], ["Ricavi: verde / giallo fino a", f"{pct(s['ricavi_var_verde'])} / {pct(s['ricavi_var_giallo'])}"],
                  ["Debiti pubblici scaduti / attivo: verde / giallo fino a", f"{pct(s['scaduto_su_attivo_verde'])} / {pct(s['scaduto_su_attivo_giallo'])}"],
                  ["Soddisfazione con la continuità: verde / giallo da", f"{pct(s['copertura_verde'])} / {pct(s['copertura_giallo'])}"],
                  ["Quota di EBITDA destinabile; anni di piano", f"{pct(s['quota_ebitda_destinabile'])}; {s['anni_piano']}"],
                  ["Realizzo: liquidità, crediti, rimanenze, immobilizzazioni materiali", f"{pct(s['realizzo_liquidità'])}, {pct(s['realizzo_crediti'])}, {pct(s['realizzo_rimanenze'])}, {pct(s['realizzo_immobilizzazioni_materiali'])}"],
                  ["Costi della procedura liquidatoria", pct(s["costi_liquidazione"])], ["Stress test", "ricavi -10%, ricavi -20%, costi +5%"]]
    P += [w.titolo("13. Parametri e soglie utilizzate"), w.tabella(soglie_tab, [6200, 3500], destra=(1,)),
          w.par(w.run("Il semaforo finale è ROSSO se un criterio critico (redditività, capacità di soddisfare i creditori) è rosso o se due criteri sono rossi; GIALLO se c'è almeno un rosso non critico o due gialli; VERDE altrimenti. "
                      "Una modifica delle soglie è una decisione del professionista.", corsivo=True))]
    return "".join(P), esito


STOP = {"liquidazione", "società", "responsabilità", "limitata", "semplice", "nome", "collettivo", "figli", "snc", "s.n.c.", "s.r.l.", "srl", "italia", "milano", "roma"}


def mappa_anonima(visura, bil, ruoli):
    """Codici coerenti per identificativi e nominativi. Restituisce {originale: codice}."""
    c = visura["campi"]
    mp, n = {}, {}

    def codice(pref):
        n[pref] = n.get(pref, 0) + 1
        return f"{pref}-{n[pref]:02d}"
    for campo, pref in (("denominazione", "SOCIETA"), ("liquidatore", "PERSONA"), ("codice_fiscale", "CF"), ("rea", "REA"), ("pec", "PEC"), ("sede_legale", "SEDE")):
        v = (c.get(campo) or {}).get("valore")
        if v and v not in mp:
            mp[v] = codice(pref)
            if campo in ("denominazione", "liquidatore", "sede_legale"):
                cod = mp[v]
                for tok in re.findall(r"[A-Za-zÀ-ÿ']{5,}", v):
                    if tok.lower() not in STOP and tok not in mp:
                        mp[tok] = cod
    nomi = {dd["fonte"].get("file") for dd in bil[0].values() if isinstance(dd, dict) and isinstance(dd.get("fonte"), dict)}
    nomi.add((ruoli.get("documento") or {}).get("file"))
    for nome in sorted(x for x in nomi if x):
        mp[nome] = codice("DOC")
    return mp


def applica_anonimato(corpo, mp):
    for orig in sorted(mp, key=len, reverse=True):
        for forma in {orig, html.escape(orig, quote=False)}:
            corpo = re.sub(re.escape(forma), mp[orig], corpo, flags=re.IGNORECASE)
    residui = [o for o in mp if re.search(re.escape(o), corpo, re.IGNORECASE)]
    if residui:
        raise RuntimeError(f"anonimizzazione incompleta: {len(residui)} termini ancora presenti")
    return corpo


def main(argv):
    def arg(nome, default=None):
        return argv[argv.index(nome) + 1] if nome in argv else default
    if not all(arg(a) for a in ("--bilancio", "--fatti", "--out")):
        print(__doc__)
        return 2
    anon = "--anonimizza" in argv
    bil = leggi_bilancio(carica(arg("--bilancio")))
    ruoli, visura = carica(arg("--ruoli")), carica(arg("--visura"))
    visura = visura or {"campi": {"denominazione": {"valore": carica(arg("--fatti")).get("nome", "[ragione sociale]"), "stato": "DA VERIFICARE"}}, "avvisi": []}
    ruoli = ruoli or {"documenti": [], "controlli": [], "documento": {}}
    corpo, esito = costruisci(bil, ruoli, visura, carica(arg("--fatti")), anonimizza=anon)
    if anon:
        mp = mappa_anonima(visura, bil, ruoli)
        corpo = applica_anonimato(corpo, mp)
        legenda = Path(arg("--legenda", str(Path(arg("--out")).with_suffix("")) + "_legenda.json"))
        if legenda.exists():
            raise FileExistsError(f"esiste già {legenda.name}")
        legenda.write_text(json.dumps({v: k for k, v in mp.items()}, ensure_ascii=False, indent=1), encoding="utf-8")
        print("Legenda codici salvata:", legenda.name, f"({len(mp)} voci)")
    w.salva(arg("--modello", PROGETTO / "Template_Preanalisi_Economico-Finanziaria_CNC.docx"), corpo, arg("--out"))
    print("Semaforo finale:", esito["verdetto"])
    for c in esito["criteri"]:
        print(" ", c["codice"], c["colore"])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
