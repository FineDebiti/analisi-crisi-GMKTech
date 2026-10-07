"""Pagina "Modello locale": estrazione proposta da un modello locale (opzionale), verificata dal codice. Nessuna chiamata se non abilitato."""
from __future__ import annotations

from urllib.parse import quote

from analisi_crisi import dati_pratica as dp
from analisi_crisi import llm_locale as ll
from analisi_crisi import pratica as pr
from analisi_crisi import ui_pratica as ui

E = ui.E


def pagina_modello(n, cart, pc, op, msg=None, err=None, status=200):
    corpo = ui.intestazione(n, pc, "modello", msg, err)
    q = quote(n)
    if not (pc / pr.FILE["pratica"]).is_file():
        return ui.resp(ui.pagina(n, corpo + ui.senza_pratica(n, op)), status)
    cfg = ll.leggi_config()
    corpo += ("<p class='av'><b>Modello locale (sperimentale).</b> Il modello PROPONE dati e ragionamenti; il codice verifica che la citazione sia alla lettera "
              "nella pagina indicata e che il numero coincida. Calcoli, soglie e semafori restano del motore deterministico. Tutto avviene su questa macchina "
              "(endpoint ammesso: solo 127.0.0.1/localhost). I valori applicati restano DA VERIFICARE finché non li confermi tu.</p>")
    if not cfg.get("abilitato"):
        corpo += ("<div class='pn'><p>Modello locale <b>non abilitato</b>: l'applicazione lavora senza alcun modello. Per abilitarlo: <code>llm_config.json</code> "
                  "(vedi GUIDA_GMKTEC.md) con <code>\"abilitato\": true</code>, endpoint locale e id esatto del modello.</p></div>")
        return ui.resp(ui.pagina(n + " - Modello locale", corpo), status)
    corpo += ("<div class='pn'><p class='mu'>Endpoint: %s - modello dichiarato: %s %s - contesto configurato: %s - temperatura %s, seed %s</p>"
              "<form method='post' action='/p/%s/llm_estrai'>%s<button>Estrai con il modello locale (può richiedere diversi minuti)</button></form></div>" % (
                  E(cfg["endpoint"]), E(cfg.get("modello") or "(id dal runtime)"), E(cfg.get("etichetta_modello") or ""), E(cfg.get("contesto_configurato")),
                  E(cfg["temperatura"]), E(cfg["seed"]), q, ui.campo_op(op)))
    run = ll.ultimo_run(pc)
    if not run:
        return ui.resp(ui.pagina(n + " - Modello locale", corpo + "<p class='mu'>Nessuna estrazione ancora eseguita.</p>"), status)
    corpo += "<p class='mu'>Ultimo run %s: modello riportato dal runtime: %s - %s s - JSON valido: %s - impronta prompt <span class='sm'>%s</span></p>" % (
        E(run["id"]), E(", ".join(map(str, (run.get("runtime") or {}).get("modelli_riportati") or [])) or "n.d."), E((run.get("meta") or {}).get("secondi")),
        "sì" if run.get("json_valido") else "NO", E(run["impronta_prompt"][:16]))
    if not run.get("json_valido"):
        corpo += "<p class='er'>La risposta del modello non è un JSON valido (%s). La risposta grezza è conservata in llm/run_%s.json.</p>" % (E(run.get("errore_json")), E(run["id"]))
        return ui.resp(ui.pagina(n + " - Modello locale", corpo), status)
    righe = []
    cor = dp.carica(pc)["campi"]
    for i, p in enumerate(run["proposte"]):
        cod = p.get("campo")
        et = dp.CAMPO[cod]["etichetta"] if cod in dp.CAMPO else str(cod)
        ok = p["esito"] == "RISCONTRATO"
        chk = "<input type='checkbox' name='sel_%d' value='1'%s>" % (i, " checked" if ok else " disabled")
        ex = cor.get(cod) or {}
        if ex.get("valore") is None:
            conf = "nessun valore presente"
        elif ex.get("valore") == p.get("valore"):
            conf = "uguale a: %s" % dp.ORIGINI.get(ex.get("origine"), "")
        else:
            conf = "DIVERSO da %s (%s)" % (dp.fmt_it(ex.get("valore")), dp.ORIGINI.get(ex.get("origine"), ""))
        righe.append([chk, E(et), E(dp.fmt_it(p["valore"]) if isinstance(p.get("valore"), (int, float)) else "non disponibile"), E(p.get("documento")), E(p.get("pagina")),
                      E(p.get("periodo")), E(p.get("natura")), "<span class='sm'>%s</span>" % E(p.get("citazione")), "<b>%s</b>%s" % (E(p["esito"]), ("<br><span class='mu'>%s</span>" % E(p["motivo"])) if p.get("motivo") else ""), E(conf)])
    corpo += ("<h2>Dati proposti</h2><form method='post' action='/p/%s/llm_applica' style='display:block'>%s<p>%s <button>Applica i selezionati come DA VERIFICARE</button></p></form>" % (
        q, ui.T(["", "Dato", "Valore", "Doc.", "Pag.", "Periodo", "Natura", "Citazione", "Verifica del codice", "Confronto con i dati già presenti"], righe, "Il modello non ha proposto dati."), ui.campo_op(op)))
    r = run.get("risposta") or {}
    mancanti = r.get("dati_mancanti") or []
    corpo += "<h3>Dati mancanti segnalati (restano non disponibili, mai zero)</h3><p>%s</p>" % E(", ".join(mancanti) or "nessuno")
    for tit, ch, cols in (("Incongruenze proposte (da confermare nella pagina Incongruenze)", "incongruenze", ("descrizione", "gravita_proposta")),
                          ("Duplicazioni", "duplicazioni", ("descrizione",)), ("Normalizzazioni proposte (nessuna applicata)", "normalizzazioni", ("descrizione", "motivazione", "effetto"))):
        corpo += "<h3>%s</h3>%s" % (E(tit), ui.T(list(cols), [[E(x.get(c)) for c in cols] for x in r.get(ch) or [] if isinstance(x, dict)], "Nessuna."))
    corpo += "<h3>Scenari proposti (informativo: il giudizio ufficiale resta quello del motore)</h3>" + ui.T(
        ["Scenario", "Stato", "Motivi"], [[E(x.get("scenario")), E(x.get("stato")), E("; ".join(map(str, x.get("motivi") or [])))] for x in r.get("scenari") or [] if isinstance(x, dict)], "Nessuno.")
    corpo += "<h3>Richieste prioritarie proposte</h3>" + ui.T(
        ["#", "Richiesta", "Perché", "Riattiva"], [[E(x.get("ordine")), E(x.get("richiesta")), E(x.get("perche")), E(x.get("riattiva"))] for x in r.get("richieste_prioritarie") or [] if isinstance(x, dict)], "Nessuna.")
    return ui.resp(ui.pagina(n + " - Modello locale", corpo), status)


def azione_estrai(n, cart, pc, op):
    if not op:
        raise dp.ErroreDati("Scrivi il tuo nome prima di avviare l'estrazione.")
    try:
        run = ll.esegui_estrazione(pc, cart, op)
    except ll.ErroreLLM as e:
        raise pr.ErrorePratica(str(e))
    return "Estrazione completata: %d proposte, %d riscontrate dal codice." % (len(run["proposte"]), sum(1 for x in run["proposte"] if x["esito"] == "RISCONTRATO"))


def azione_applica(n, cart, pc, op, form_sel):
    if not op:
        raise dp.ErroreDati("Scrivi il tuo nome per applicare le proposte.")
    mod, saltati = ll.applica_proposte(pc, form_sel, op)
    return "Applicati %d valori come DA VERIFICARE." % len(mod) + ((" Saltati: " + "; ".join(saltati)) if saltati else "")
