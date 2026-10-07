"""Mappa delle celle del modello AZIENDE (Modello_Aziende_Valutazione_Crisi_Template.xlsx).

Colonne come nel modello Traietti: C = Anno -2, D = Anno -1. La colonna E (corrente/previsionale) è manuale.
Le righe con formule non compaiono. Le riclassificazioni sono sempre INFERENZA con una nota.
"""
from .comune import DA_VERIFICARE, FATTO, INFERENZA, OK, RigaFoglio, cella, peggiore

CE = "bilancio_ce"
SP = "bilancio_sp"


def _righe(rimanenze):
    """(foglio, RigaFoglio). Il controllo indica il totale del documento che conferma una voce assente."""
    n_ce = "Riclassificazione conto economico art. 2425."
    return (
        (CE, RigaFoglio(6, "Ricavi delle vendite e delle prestazioni (A1)", (("ce.A1", 1),))),
        (CE, RigaFoglio(7, "Variazione delle rimanenze di prodotti (A2/A3)", rimanenze, controllo="ce.A")),
        (CE, RigaFoglio(8, "Altri ricavi e proventi (A5, A4)", (("ce.A5", 1), ("ce.A4", 1)), controllo="ce.A",
                        nota="Include A4 (incrementi di immobilizzazioni) se presente.")),
        (CE, RigaFoglio(11, "Costi per materie prime e merci (B6, B11)", (("ce.B6", 1), ("ce.B11", 1)), controllo="ce.B",
                        nota="Include la variazione delle rimanenze di materie prime (B11).")),
        (CE, RigaFoglio(12, "Costi per servizi (B7)", (("ce.B7", 1),))),
        (CE, RigaFoglio(13, "Costi per godimento beni di terzi (B8)", (("ce.B8", 1),), controllo="ce.B")),
        (CE, RigaFoglio(14, "Oneri diversi di gestione (B14)", (("ce.B14", 1),))),
        (CE, RigaFoglio(17, "Costo del personale (B9)", (("ce.B9", 1),))),
        (CE, RigaFoglio(20, "Ammortamenti e svalutazioni (B10)", (("ce.B10", 1),), controllo="ce.B")),
        (CE, RigaFoglio(21, "Accantonamenti per rischi e oneri (B12, B13)", (("ce.B12", 1), ("ce.B13", 1)), controllo="ce.B")),
        (CE, RigaFoglio(24, "Proventi finanziari (C15, C16)", (("ce.C15", 1), ("ce.C16", 1)), controllo="ce.C")),
        (CE, RigaFoglio(25, "Oneri finanziari (C17)", (("ce.C17", 1),), controllo="ce.C")),
        (CE, RigaFoglio(29, "Imposte sul reddito (20)", (("ce.I20", 1),), controllo="ce.RAI")),
        (SP, RigaFoglio(7, "Immobilizzazioni immateriali", (("sp.imm_immat", 1),), controllo="sp.tot_attivo")),
        (SP, RigaFoglio(8, "Immobilizzazioni materiali", (("sp.imm_mat", 1),), controllo="sp.tot_attivo")),
        (SP, RigaFoglio(9, "Immobilizzazioni finanziarie (e crediti oltre l'esercizio)",
                        (("sp.imm_fin", 1), ("sp.crediti_oltre", 1)), controllo="sp.tot_attivo",
                        nota="I crediti esigibili oltre l'esercizio sono qui per la quadratura del modello: verificare.")),
        (SP, RigaFoglio(12, "Rimanenze", (("sp.rimanenze", 1),), controllo="sp.tot_attivo")),
        (SP, RigaFoglio(15, "Disponibilità liquide", (("sp.disp_liquide", 1),), controllo="sp.tot_attivo")),
        (SP, RigaFoglio(18, "Ratei e risconti attivi", (("sp.ratei_att", 1),), controllo="sp.tot_attivo")),
        (SP, RigaFoglio(23, "Capitale sociale", (("sp.capitale", 1),), controllo="sp.tot_passivo")),
        (SP, RigaFoglio(24, "Riserve (II-VII)",
                        tuple((k, 1) for k in ("sp.ris_sovr", "sp.ris_riv", "sp.ris_leg", "sp.ris_stat", "sp.ris_altre", "sp.ris_cop")),
                        controllo="sp.tot_passivo", forza_inferenza=True, nota="Somma delle riserve II-VII.")),
        (SP, RigaFoglio(25, "Utili (perdite) portati a nuovo", (("sp.utili_nuovo", 1),), controllo="sp.tot_passivo")),
        (SP, RigaFoglio(29, "Fondi per rischi e oneri", (("sp.fondi", 1),), controllo="sp.tot_passivo")),
        (SP, RigaFoglio(30, "TFR", (("sp.tfr", 1),), controllo="sp.tot_passivo")),
        (SP, RigaFoglio(39, "Ratei e risconti passivi", (("sp.ratei_pass", 1),), controllo="sp.tot_passivo")),
    )


def celle_aziende(r: dict) -> list[dict]:
    """Dal risultato del parser (dati, residui, controllo, controlli) alle celle del modello Aziende."""
    per = {}
    for sezione in ("dati", "residui", "controllo"):
        for d in r.get(sezione, []):
            per[d["chiave"], d["anno"]] = d
    esiti = {(c["chiave"], c["anno"]): c["esito"] for c in r.get("controlli", []) if "chiave" in c}
    anni = [e["anno"] for e in r.get("esercizi", [])] or []
    colonna = {-1: "D", -2: "C"}
    rimanenze = (("ce.A23", 1),) if any(k == "ce.A23" for k, _ in per) else (("ce.A2", 1), ("ce.A3", 1))
    risultato = []
    for foglio, rf in _righe(rimanenze):
        celle = {}
        for anno in anni:
            dati = {k: per[k, anno] for k, _ in rf.componenti if (k, anno) in per}
            c = cella(rf, dati, esiti.get((rf.controllo, anno)))
            # Voce assente e nessun totale di conferma: la cella resta vuota (zero nel modello), non scritta.
            celle[colonna[anno]] = c
        if celle:
            risultato.append({"foglio": foglio, "riga": rf.riga, "voce": rf.nome, "componenti": [k for k, _ in rf.componenti], "celle": celle})
    risultato += _crediti_e_debiti(per, anni, colonna)
    return risultato


def _riga(foglio, n, voce, celle):
    return {"foglio": foglio, "riga": n, "voce": voce, "componenti": [], "celle": celle}


def _crediti_e_debiti(per, anni, colonna):
    """Righe che dipendono da come il documento ripartisce crediti e debiti (bilancio abbreviato o ordinario)."""
    out = []
    for anno in anni:
        col = colonna[anno]
        g = lambda k: per.get((k, anno)) if per.get((k, anno)) and per[k, anno]["valore"] is not None else None

        def componi(chiavi, note, base=INFERENZA, sottrai=()):
            presenti = [g(k) for k in chiavi if g(k)]
            if not presenti:
                return {"valore": None, "stato": DA_VERIFICARE, "note": ["Nessuna voce trovata nel documento."]}
            valore = sum(d["valore"] for d in presenti) - sum(g(k)["valore"] for k in sottrai if g(k))
            stato = peggiore(base, *(d["stato"] for d in presenti))
            return {"valore": valore, "stato": stato, "note": list(note)}

        # Crediti: clienti se distinti, altrimenti tutti i crediti a breve nella riga "altri crediti".
        clienti = g("sp.crediti_clienti")
        nota_cr = ["Bilancio abbreviato: crediti verso clienti non distinti, inseriti tra gli altri crediti a breve."]
        if clienti:
            out.append(_riga("bilancio_sp", 13, "Crediti verso clienti", {col: {"valore": clienti["valore"], "stato": clienti["stato"], "note": []}}))
            altri = componi(("sp.crediti_entro", "sp.crediti_soci"), ["Crediti a breve al netto dei crediti verso clienti."], sottrai=("sp.crediti_clienti",))
        else:
            altri = componi(("sp.crediti_entro", "sp.crediti_soci"), nota_cr)
        out.append(_riga("bilancio_sp", 14, "Altri crediti a breve (e crediti verso soci)", {col: altri}))
        # Debiti: dettaglio se presente, altrimenti aggregato entro/oltre.
        dettaglio = [k for k in ("sp.deb_banche", "sp.deb_fornitori", "sp.deb_tributari", "sp.deb_previdenza", "sp.deb_altri") if g(k)]
        if dettaglio:
            nota_b = ["Scadenza non distinta nel documento: debiti bancari inseriti tra quelli entro 12 mesi; riclassificare con la nota integrativa."]
            for riga, k, voce, note in ((32, "sp.deb_banche", "Debiti verso banche (entro 12 mesi)", nota_b),
                                        (33, "sp.deb_fornitori", "Debiti verso fornitori", []),
                                        (34, "sp.deb_tributari", "Debiti tributari", []),
                                        (35, "sp.deb_previdenza", "Debiti verso istituti previdenziali", []),
                                        (36, "sp.deb_altri", "Altri debiti", [])):
                if g(k):
                    stato = g(k)["stato"] if not note else peggiore(g(k)["stato"], INFERENZA)
                    out.append(_riga("bilancio_sp", riga, voce, {col: {"valore": g(k)["valore"], "stato": stato, "note": note}}))
        else:
            out.append(_riga("bilancio_sp", 36, "Altri debiti (debiti esigibili entro l'esercizio)",
                             {col: componi(("sp.debiti_entro",), ["Bilancio abbreviato: debiti non ripartiti per natura, inseriti tra gli altri debiti a breve."])}))
            out.append(_riga("bilancio_sp", 31, "Debiti verso banche oltre 12 mesi (debiti esigibili oltre l'esercizio)",
                             {col: componi(("sp.debiti_oltre",), ["Bilancio abbreviato: debiti oltre l'esercizio non ripartiti; non necessariamente bancari."])}))
    # Accorpa per riga le colonne C e D
    unite = {}
    for x in out:
        e = unite.setdefault((x["foglio"], x["riga"]), {**x, "celle": {}})
        e["celle"].update(x["celle"])
    return list(unite.values())


# ---- Estratti di ruolo -> foglio passivo_creditori e rapporto scaduto/attivo (allerta CCII) ----
PASSIVO = "passivo_creditori"
CLASSE_TRIBUTI = "Privilegio generale - tributi e contributi"
CLASSE_CHIRO = "Chirografario"
PRIMA_RIGA, ULTIMA_RIGA = 17, 41
_NATURA = {"erariale": "Ruolo erariale", "previdenziale": "Ruolo previdenziale (INPS/INAIL)", "enti_locali": "Ruolo tributi/entrate locali",
           "camera_commercio": "Ruolo Camera di Commercio", "altro": "Ruolo - altro ente"}


def celle_ruoli(r, attivo=None):
    """Righe per il modello Aziende dal JSON di un estratto di ruolo (parser_ruoli / ocr_ruoli).

    Una riga per ente creditore (residuo dei tributi, classe INFERENZA) più una riga per aggio, interessi di mora e spese
    di riscossione. Le righe da OCR sono sempre DA VERIFICARE. `attivo`: totale attivo di bilancio per il rapporto
    scaduto/attivo (allerta CCII, C22); senza attivo la cella non viene compilata.
    """
    ocr = r["documento"].get("lettura") == "OCR"
    per_ente, extra, stato_nat = {}, 0.0, FATTO
    for d in r["documenti"]:
        base = DA_VERIFICARE if ocr or d["stato"] != FATTO else FATTO
        if ocr:
            nome = (d.get("ente_letto") or "Ente non letto")[:60]
            valore = d.get("totale_residuo_candidato")
            classe = d.get("classe") or "altro"
            if valore is None:
                continue
            e = per_ente.setdefault(nome, {"valore": 0.0, "classe": classe, "stato": base, "n": 0})
            e["valore"] += valore
            e["n"] += 1
            continue
        for x in d["righe"]:
            nome = x.get("ente") or (d["enti"][0]["descrizione"] if d["enti"] else "Ente non letto")
            cl = next((en["classe"] for en in d["enti"] if en["descrizione"] == nome), "altro")
            e = per_ente.setdefault(nome, {"valore": 0.0, "classe": cl, "stato": base, "n": 0})
            e["valore"] += x["residuo"]
            e["n"] += 1
            e["stato"] = peggiore(e["stato"], base)
        t = d["totali"]
        extra += sum(t.get(k, 0) for k in ("diritti_notifica", "aggio", "interessi_mora", "spese"))
    righe, n = [], PRIMA_RIGA
    note_ocr = ["Lettura da scansione: importo candidato, confrontare con il PDF."] if ocr else []
    for nome, e in sorted(per_ente.items(), key=lambda kv: -kv[1]["valore"]):
        if n > ULTIMA_RIGA - 1:
            break
        righe.append((n, nome, e))
        n += 1
    out = []
    for n, nome, e in righe:
        stato_importo = e["stato"]
        celle = {
            "B": {"valore": CLASSE_TRIBUTI, "stato": peggiore(INFERENZA, stato_importo),
                  "note": ["Classe assegnata in via generale ai ruoli: sanzioni e interessi possono essere chirografari, da verificare."]},
            "C": {"valore": nome.title() if nome.isupper() else nome, "stato": stato_importo, "note": note_ocr},
            "D": {"valore": f"{_NATURA.get(e['classe'], _NATURA['altro'])} - {e['n']} voci", "stato": INFERENZA, "note": []},
            "F": {"valore": round(e["valore"], 2), "stato": stato_importo, "note": note_ocr + ["Residuo dei tributi in debito, senza aggio, interessi di mora e spese."]},
        }
        out.append(_riga(PASSIVO, n, f"Creditore {n - PRIMA_RIGA + 1} ({e['classe']})", celle))
    if extra and righe and PRIMA_RIGA + len(righe) <= ULTIMA_RIGA:
        n = PRIMA_RIGA + len(righe)
        out.append(_riga(PASSIVO, n, "Aggio, interessi di mora e spese di riscossione", {
            "B": {"valore": CLASSE_CHIRO, "stato": DA_VERIFICARE, "note": ["Natura privilegiata o no da valutare: aggio e spese di riscossione."]},
            "C": {"valore": "Agente della riscossione (aggio, interessi di mora, diritti e spese)", "stato": FATTO, "note": []},
            "D": {"valore": "Oneri di riscossione e interessi di mora", "stato": INFERENZA, "note": []},
            "F": {"valore": round(extra, 2), "stato": FATTO if not ocr else DA_VERIFICARE, "note": []},
        }))
    # Scaduto tributario e previdenziale / attivo (allerta CCII).
    scaduto = sum(e["valore"] for e in per_ente.values() if e["classe"] != "altro") + (extra if righe else 0)
    if attivo and scaduto:
        out.append(_riga("allerta_ccii", 22, "Indebitamento previdenziale e tributario scaduto / Attivo", {"C": {
            "valore": round(scaduto / attivo["valore"], 4), "stato": peggiore(INFERENZA, attivo["stato"], DA_VERIFICARE if ocr else FATTO),
            "note": ["Tutti i ruoli sono considerati scaduti; attivo dell'ultimo bilancio disponibile, non coevo ai ruoli."]}}))
    return out


# ---- Visura camerale -> foglio anagrafica_azienda (colonna C) ----
ANAGRAFICA = "anagrafica_azienda"
_MAPPA_VISURA = (
    (6, "denominazione", "Ragione sociale"), (7, "forma_giuridica", "Forma giuridica"), (9, "codice_fiscale", "Codice fiscale"),
    (10, "sede_legale", "Sede legale"), (11, "rea", "Numero REA / CCIAA"), (13, "data_costituzione", "Data di costituzione"),
    (16, "stato_impresa", "Stato dell'impresa"), (24, "liquidatore", "Curatore / Commissario / Liquidatore"),
)


def celle_anagrafica(v):
    """Righe di anagrafica_azienda dal JSON di una visura (parser_visura). Partita IVA non letta: resta vuota."""
    out = []
    for riga, chiave, nome in _MAPPA_VISURA:
        c = v["campi"].get(chiave)
        if c:
            out.append(_riga(ANAGRAFICA, riga, nome, {"C": {"valore": c["valore"], "stato": c["stato"], "note": c["note"]}}))
    return out


# ---- Situazione contabile (parser_situazione) -> bilancio_sp / bilancio_ce, una colonna scelta (C o D) ----
# Codici di mastro del gestionale: da confermare per ogni studio, per questo ogni riga è INFERENZA con la nota.
_ATT = lambda m: (m["S"] or 0) - (m["D"] or 0)       # netto di un mastro dell'attivo
_PAS = lambda m: (m["D"] or 0) - (m["S"] or 0)       # netto di un mastro del passivo
_COSTO = lambda m: (m["S"] or 0) - (m["D"] or 0)
_RICAVO = lambda m: (m["D"] or 0) - (m["S"] or 0)
_SP_MAPPA = (
    (7, "Immobilizzazioni immateriali (al netto del fondo)", (("03", _ATT), ("04", _ATT))),
    (8, "Immobilizzazioni materiali (al netto del fondo)", (("06", _ATT), ("07", _ATT))),
    (9, "Immobilizzazioni finanziarie", (("09", _ATT),)),
    (13, "Crediti verso clienti", (("14", _ATT),)),
    (14, "Altri crediti", (("18", _ATT),)),
    (15, "Disponibilità liquide", (("24", _ATT),)),
    (18, "Ratei e risconti attivi", (("26", _ATT),)),
    (30, "TFR", (("31", _PAS),)),
    (32, "Debiti verso banche (entro 12 mesi)", (("34", _PAS),)),
    (33, "Debiti verso fornitori", (("40", _PAS), ("41", _PAS))),
    (34, "Debiti tributari", (("48", _PAS),)),
    (35, "Debiti verso istituti previdenziali", (("50", _PAS),)),
    (36, "Altri debiti (altri finanziatori, acconti, altri)", (("36", _PAS), ("38", _PAS), ("52", _PAS))),
)
_CE_MAPPA = (
    (6, "Ricavi delle vendite e delle prestazioni", (("58", _RICAVO),)),
    (8, "Altri ricavi e proventi", (("64", _RICAVO),)),
    (11, "Costi per materie prime e merci (con variazione delle rimanenze)", (("66", _COSTO), ("80", _COSTO))),
    (12, "Costi per servizi", (("68", _COSTO),)),
    (13, "Costi per godimento beni di terzi", (("70", _COSTO),)),
    (14, "Oneri diversi di gestione", (("84", _COSTO),)),
    (17, "Costo del personale", (("72", _COSTO),)),
    (24, "Proventi finanziari", (("87", _RICAVO),)),
    (25, "Oneri finanziari", (("88", _COSTO),)),
)


def celle_situazione(r, colonna="D"):
    """Righe del modello Aziende da una situazione contabile. Tutto INFERENZA se i controlli aritmetici tornano, altrimenti DA VERIFICARE."""
    ok = all(c["esito"] in (OK, "NON ESEGUIBILE") for c in r["controlli"]) and any(c["esito"] == OK for c in r["controlli"])
    stato = INFERENZA if ok else DA_VERIFICARE
    nota = f"Da situazione contabile al {r['date'].get('PATRIMONIALE') or r['date'].get('ECONOMICA')}: riclassificazione dei mastri del gestionale, da confermare."
    out, usati = [], set()

    def aggiungi(foglio, riga, voce, composizione, extra=()):
        presenti = [(m, f) for m, f in composizione if m in r["mastri"]]
        if not presenti:
            return
        usati.update(m for m, _ in presenti)
        valore = round(sum(f(r["mastri"][m]) for m, f in presenti), 2)
        out.append(_riga(foglio, riga, voce, {colonna: {"valore": valore, "stato": stato, "note": [nota, *extra]}}))

    if "PATRIMONIALE" in r["date"]:
        for riga, voce, comp in _SP_MAPPA:
            aggiungi(SP, riga, voce, comp)
        # Patrimonio netto per gruppo: 28/05 capitale, 28/40 utili a nuovo, il resto riserve.
        g = {k: v for k, v in r["gruppi"].items() if k.startswith("28/")}
        if g:
            usati.add("28")
            cap = sum(v["valore"] for k, v in g.items() if k == "28/05")
            utili = sum(v["valore"] for k, v in g.items() if k == "28/40")
            riserve = sum(v["valore"] for k, v in g.items() if k not in ("28/05", "28/40"))
            for riga, voce, val in ((23, "Capitale sociale", cap), (24, "Riserve", riserve), (25, "Utili (perdite) portati a nuovo", utili)):
                out.append(_riga(SP, riga, voce, {colonna: {"valore": round(val, 2), "stato": stato,
                                                           "note": [nota, "Utile/perdita dell'esercizio in corso non inserito: colonna del modello da valutare."]}}))
    if "ECONOMICA" in r["date"]:
        for riga, voce, comp in _CE_MAPPA:
            aggiungi(CE, riga, voce, comp)
        assenti = [m for m in ("74", "76", "78") if m not in r["mastri"]]
        r.setdefault("avvisi", [])
        if assenti:
            av = "Nessun ammortamento, accantonamento o imposta nei conti: situazione provvisoria, voci CE 20, 21 e 29 da stimare."
            if av not in r["avvisi"]:
                r["avvisi"].append(av)
    nonmappati = sorted(m for m in r["mastri"] if m not in usati and m not in ("28",))
    r["non_mappati"] = nonmappati
    return out
