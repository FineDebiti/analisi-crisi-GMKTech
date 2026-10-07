"""Dati numerici della pratica: inserimento assistito, estrazione automatica del bilancio, metriche, storico e decadenza dell'approvazione.

Nessuna regola di calcolo o di giudizio nuova: le metriche sono ricavate con le formule GIA' presenti nel motore
(EBITDA = A - B + ammortamenti come in relazione_caso; rapporto semplificato = relazione_v3.rapporto_semplificato; soglie e colori restano in semaforo_v3).
Un dato vuoto è "non disponibile" (None), MAI zero. File della pratica: dati_valori.json (dati con origine e storico),
metriche.json (derivato, scritto a ogni salvataggio: l'operatore non lo vede né lo modifica), dati_estratti.json (derivato),
preanalisi_dati.json (impronta dei dati al momento della preanalisi).
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from analisi_crisi import checklist as ck
from analisi_crisi import parser_bilancio
from analisi_crisi import pratica as pr
from analisi_crisi.comune import DA_VERIFICARE, FATTO, INFERENZA, peggiore

FILE_DATI = "dati_valori.json"
FILE_METRICHE = "metriche.json"
FILE_REF = "preanalisi_dati.json"
ORIGINI = {"AUTO": "Estratto automaticamente", "OPERATORE": "Inserito dall'operatore", "CORRETTO": "Corretto dall'operatore",
            "LLM": "Proposto dal modello locale (da verificare)"}
TIPI_DOC = ("bilancio", "situazione contabile", "visura", "ruolo", "centrale rischi", "altro")
NATURE_FILE = ("STORICO", "AGGIORNATO", "STIMA")
PROCEDURE = ("CNC", "LC", "Altro")
ND = "non disponibile"
CHI_SISTEMA = "sistema"


class ErroreDati(pr.ErrorePratica):
    pass


# (codice, etichetta, unita, tipo, aiuto)  - i valori che il motore usa oggi per le metriche
CAMPI = (
    ("ricavi", "Ricavi delle vendite e delle prestazioni (A1)", "EUR", "num", "Denominatore del margine EBITDA."),
    ("valore_produzione", "Valore della produzione (totale A)", "EUR", "num", "Serve per l'EBITDA; se mancano i ricavi A1 è usato come denominatore."),
    ("costi_produzione", "Costi della produzione (totale B)", "EUR", "num", "Serve per l'EBITDA."),
    ("ammortamenti", "Ammortamenti e svalutazioni (B10)", "EUR", "num", "EBITDA = A - B + ammortamenti."),
    ("ricavi_prec", "Ricavi dell'esercizio precedente (A1)", "EUR", "num", "Per la variazione dei ricavi."),
    ("totale_attivo", "Totale attivo", "EUR", "num", "Denominatore di patrimonio netto e debiti pubblici."),
    ("patrimonio_netto", "Patrimonio netto", "EUR", "num", "Può essere negativo."),
    ("debiti_totali", "Debiti totali", "EUR", "num", "Per il rapporto debito netto/EBITDA."),
    ("disponibilita_liquide", "Disponibilità liquide", "EUR", "num", "Informativo."),
    ("liquidita_utilizzabile", "Quota utilizzabile delle disponibilità liquide", "EUR", "num", "Detratta dal debito per il debito netto: la indica l'operatore."),
    ("debiti_pubblici", "Debiti pubblici (tributari, previdenziali, riscossione)", "EUR", "num", "Se manca l'estratto di ruolo sono provvisori e da riconciliare."),
    ("debiti_bancari", "Debiti bancari", "EUR", "num", "Informativo (Centrale Rischi non verificata se assente)."),
    ("crediti_soci", "Crediti verso soci/amministratori", "EUR", "num", "Segnale per l'approfondimento dedicato."),
    ("tesoreria_verificata", "Flusso di cassa / tesoreria verificato dal titolare", "", "sino", "Lasciare vuoto se non verificato."),
    ("situazione_corrente_verificata", "Situazione contabile corrente verificata dal titolare", "", "sino", "Lasciare vuoto se non verificata."),
)
CAMPO = {c[0]: {"codice": c[0], "etichetta": c[1], "unita": c[2], "tipo": c[3], "aiuto": c[4]} for c in CAMPI}
CAMPI_LISTA = [CAMPO[c[0]] for c in CAMPI]

# Lettura automatica del bilancio: campo -> (voce del parser, anno: -1 esercizio più recente, -2 precedente)
MAPPA_AUTO = {
    "ricavi": ("ce.A1", -1), "valore_produzione": ("ce.A", -1), "costi_produzione": ("ce.B", -1), "ammortamenti": ("ce.B10", -1),
    "ricavi_prec": ("ce.A1", -2), "totale_attivo": ("sp.tot_attivo", -1), "patrimonio_netto": ("sp.tot_pn", -1),
    "debiti_totali": ("sp.tot_debiti", -1), "disponibilita_liquide": ("sp.disp_liquide", -1), "debiti_bancari": ("sp.deb_banche", -1),
    "crediti_soci": ("sp.crediti_soci", -1),
}
NOTA_LETTURA = ("Lettura automatica: solo il BILANCIO (PDF con testo): ricavi, valore e costi della produzione, ammortamenti, totale attivo, "
                "patrimonio netto, debiti totali e, se presenti nel documento, disponibilità liquide, debiti bancari, crediti verso soci e debiti "
                "tributari/previdenziali. Visura, estratti di ruolo, Centrale Rischi, situazione contabile e altri documenti NON sono letti "
                "automaticamente: i valori vanno inseriti a mano. Ogni valore letto resta da verificare.")


# ---------------------------------------------------------------- formati
def parse_numero(testo):
    """Accetta formati italiani (1.234,56; -1.234,56; (1.234,56); 1234,5; 1234). Vuoto -> None (non disponibile, mai zero)."""
    t = (testo or "").strip().replace("€", "").replace("EUR", "").replace(" ", "").replace(" ", "").replace("'", "")
    if not t:
        return None
    neg = False
    if t.startswith("(") and t.endswith(")"):
        neg, t = True, t[1:-1]
    if t.startswith("-"):
        neg, t = True, t[1:]
    elif t.startswith("+"):
        t = t[1:]
    if "," in t:
        if not re.fullmatch(r"(\d{1,3}(\.\d{3})+|\d+),\d{1,6}", t):
            raise ErroreDati("Il valore '%s' non è un numero valido. Esempi: 1.234,56 oppure 1234,56." % testo.strip()[:30])
        n = float(t.replace(".", "").replace(",", "."))
    elif re.fullmatch(r"\d{1,3}(\.\d{3})+", t) or re.fullmatch(r"\d+", t):
        n = int(t.replace(".", ""))
    elif re.fullmatch(r"\d+\.\d{1,2}", t):
        n = float(t)
    else:
        raise ErroreDati("Il valore '%s' non è un numero valido. Esempi: 1.234,56 oppure 1234,56." % testo.strip()[:30])
    n = -n if neg else n
    if isinstance(n, float) and n.is_integer() and abs(n) < 1e15:
        n = int(n)
    return n


def fmt_it(v):
    if v is None:
        return ND
    if v in ("SI", "NO"):
        return {"SI": "Sì", "NO": "No"}[v]
    if isinstance(v, float) and not v.is_integer():
        s = "{:,.2f}".format(v)
        return s.replace(",", "X").replace(".", ",").replace("X", ".")
    return "{:,}".format(int(v)).replace(",", ".")


def fmt_modifica(v):
    """Valore per un campo di input: cifre e virgola, senza separatore delle migliaia (rilegge identico)."""
    if v is None:
        return ""
    if v in ("SI", "NO"):
        return v
    if isinstance(v, float) and not v.is_integer():
        return repr(v).replace(".", ",")
    return str(int(v))


def pct(v):
    return ND if v is None else ("%.1f%%" % (v * 100)).replace(".", ",")


def dt_it(iso):
    if not iso:
        return ""
    s = str(iso)
    return "%s/%s/%s %s" % (s[8:10], s[5:7], s[:4], s[11:16]) if len(s) >= 16 else s


def data_it(iso):
    s = str(iso or "")
    return "%s/%s/%s" % (s[8:10], s[5:7], s[:4]) if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s) else s


def parse_data(testo):
    t = (testo or "").strip()
    if not t:
        return None
    for f in ("%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(t, f).date().isoformat()
        except ValueError:
            pass
    raise ErroreDati("La data '%s' non è valida. Scrivila come 31/12/2025." % t[:20])


# ---------------------------------------------------------------- archivio dei dati
def _file(pc):
    return Path(pc) / FILE_DATI


def carica(pc):
    try:
        d = json.loads(_file(pc).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        d = {}
    d.setdefault("campi", {})
    d.setdefault("estrazioni", {})
    d.setdefault("controlli_ko", [])
    return d


def _salva(pc, d):
    f = _file(pc)
    tmp = f.with_name(f.name + ".tmp")
    tmp.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, f)


def valori(pc):
    return {k: r.get("valore") for k, r in carica(pc)["campi"].items()}


def _snap(r):
    return {k: r.get(k) for k in ("valore", "stato", "id_documento", "pagina", "origine", "da", "il", "note", "esercizio")}


# ---------------------------------------------------------------- metriche (formule già presenti nel motore)
def calcola_metriche(v):
    """Ritorna (metriche per il motore v3, calcoli leggibili). Un valore mancante resta None: non diventa mai zero."""
    sys.path.insert(0, str(pr.versione.RADICE)) if str(pr.versione.RADICE) not in sys.path else None
    import relazione_v3 as rv3
    g = v.get
    A, B, amm = g("valore_produzione"), g("costi_produzione"), g("ammortamenti")
    ebitda = (A - B + amm) if None not in (A, B, amm) else None
    den, den_nome = (g("ricavi"), "ricavi A1") if g("ricavi") else (A, "valore della produzione")
    margine = (ebitda / den) if ebitda is not None and den else None
    netto, rapporto, fascia = rv3.rapporto_semplificato(g("debiti_totali"), g("liquidita_utilizzabile"), ebitda)
    attivo = g("totale_attivo")
    div = lambda x: (x / attivo) if x is not None and attivo else None
    pn_att, pub_att, soci_att = div(g("patrimonio_netto")), div(g("debiti_pubblici")), div(g("crediti_soci"))
    rp, rc = g("ricavi_prec"), g("ricavi")
    var = ((rc - rp) / rp) if rc is not None and rp else None
    m = {"margine": margine, "rapporti": ({"EBITDA ultimo esercizio": rapporto} if rapporto is not None else {}),
         "flusso_non_positivo": bool(netto is not None and ebitda is not None and ebitda <= 0),
         "pn_su_attivo": pn_att, "pubblici_su_attivo": pub_att, "crediti_soci_su_attivo": soci_att,
         "cassa_verificata": g("tesoreria_verificata") == "SI",
         "corrente_verificata": g("situazione_corrente_verificata") == "SI",
         "riferimento": "dati della pratica (gestione storica)",
         "ebitda": ebitda, "debito_netto": netto, "ricavi_var": var, "ricavi": rc, "debiti_bancari": g("debiti_bancari")}
    calcoli = [
        ("EBITDA (A - B + ammortamenti)", fmt_it(ebitda) + (" €" if ebitda is not None else ""), "Servono valore e costi della produzione e ammortamenti." if ebitda is None else ""),
        ("Margine EBITDA", pct(margine), ("Su " + den_nome + ".") if margine is not None else "Servono EBITDA e ricavi."),
        ("Rapporto semplificato debito netto/EBITDA", (("%.2f" % rapporto).replace(".", ",")) if rapporto is not None else ND,
         ("Debito netto " + fmt_it(netto) + " €; fascia " + fascia + ".") if netto is not None else "Servono debiti totali e quota utilizzabile della liquidità."),
        ("Patrimonio netto / attivo", pct(pn_att), ""),
        ("Debiti pubblici / attivo", pct(pub_att), ""),
        ("Variazione dei ricavi", pct(var), ""),
    ]
    return m, calcoli


def scrivi_metriche(pc):
    m, _ = calcola_metriche(valori(pc))
    f = Path(pc) / FILE_METRICHE
    tmp = f.with_name(f.name + ".tmp")
    tmp.write_text(json.dumps(m, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, f)


def sincronizza(pc):
    """Deriva metriche.json e dati_estratti.json dai dati. Chiamata a ogni salvataggio."""
    scrivi_metriche(pc)
    righe = []
    for i, c in enumerate(CAMPI_LISTA, 1):
        r = carica(pc)["campi"].get(c["codice"])
        if r and r.get("valore") is not None:
            righe.append({"id": len(righe) + 1, "dato": c["etichetta"], "valore": r["valore"], "unita": c["unita"], "natura": r["stato"],
                          "id_documento": r.get("id_documento"), "pagina": r.get("pagina"), "origine": ORIGINI[r["origine"]], "esercizio": r.get("esercizio")})
    pr._scrivi(pc, "dati", righe)


# ---------------------------------------------------------------- approvazione: decade se cambia un dato decisivo
def impronta_dati(pc):
    d = carica(pc)
    inc = pr._leggi(pc, "inc", [])
    reg = pr._leggi(pc, "registro", [])
    base = {"v": [[k, r.get("valore"), r.get("stato")] for k, r in sorted(d["campi"].items())],
            "inc": [[x["id"], x["gravita"], x["stato"]] for x in inc if x["gravita"] == "SOSTANZIALE"],
            "reg": [[r["id"], r.get("sha256"), r.get("tipo"), r.get("natura"), r.get("decisivo")] for r in reg],
            "ck": sorted((k, o.get("stato")) for k, o in ck._leggi_override(pc).items())}
    return hashlib.sha256(json.dumps(base, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def approvazione(pc):
    """{'stato': 'APPROVATA'|'NON APPROVATA', 'decaduta': bool, ...}. Approvata solo se il prodotto e i dati sono quelli approvati."""
    a = pr.stato_approvazione(pc)
    if not a:
        return {"stato": "NON APPROVATA", "decaduta": False}
    ok_dati = a.get("dati_hash") == impronta_dati(pc)
    if a["valida"] and ok_dati:
        return {"stato": "APPROVATA", "decaduta": False, "approvata_da": a["approvata_da"], "approvata_il": a["approvata_il"],
                "documento_word": a.get("documento_word")}
    return {"stato": "NON APPROVATA", "decaduta": True, "approvata_da": a["approvata_da"], "approvata_il": a["approvata_il"],
            "motivo": "la preanalisi è stata rigenerata" if not a["valida"] else "un dato decisivo è stato modificato"}


@contextmanager
def modifica(pc, motivo):
    prima = approvazione(pc)["stato"] == "APPROVATA"
    yield
    sincronizza(pc)
    if prima and approvazione(pc)["stato"] != "APPROVATA":
        pr._verbale(pc, "APPROVAZIONE DECADUTA", "OK", motivo + ": rigenerare la preanalisi e approvare di nuovo")


def preanalisi_aggiornata(pc):
    u = pr.ultima_preanalisi(pc)
    try:
        ref = json.loads((Path(pc) / FILE_REF).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return bool(u) and ref.get("generata_il") == u["generata_il"] and ref.get("dati_hash") == impronta_dati(pc)


def avvia_preanalisi(pc, nome=None):
    sincronizza(pc)
    prima = approvazione(pc)["stato"] == "APPROVATA"
    d = pr.avvia_preanalisi(pc, nome=nome)
    f = Path(pc) / FILE_REF
    tmp = f.with_name(f.name + ".tmp")
    tmp.write_text(json.dumps({"generata_il": d["generata_il"], "dati_hash": impronta_dati(pc)}), encoding="utf-8")
    os.replace(tmp, f)
    if prima:
        pr._verbale(pc, "APPROVAZIONE DECADUTA", "OK", "preanalisi rigenerata: approvare di nuovo")
    return d


def approva(pc, nome):
    if not (nome or "").strip():
        raise pr.ErrorePratica("Scrivi il nome del titolare che approva.")
    if not pr.ultima_preanalisi(pc):
        raise pr.ErrorePratica("Non c'è ancora una preanalisi: premi prima 'Avvia preanalisi'.")
    if not preanalisi_aggiornata(pc):
        raise pr.ErrorePratica("I dati sono cambiati dopo l'ultima preanalisi: premi di nuovo 'Avvia preanalisi', poi approva.")
    a = pr.approva_come_provvisoria(pc, nome)
    a["dati_hash"] = impronta_dati(pc)
    pr._scrivi(pc, "appr", a)
    return a


# ---------------------------------------------------------------- inserimento e correzione
def salva_valori(pc, righe, chi):
    """righe: {codice: {'valore','id_documento','pagina','stato','note'}} (testi del modulo). Scrive solo i campi cambiati.
    Tutto o niente: se un campo non è valido non si salva nulla. Ritorna l'elenco dei codici modificati."""
    chi = (chi or "").strip()
    if not chi:
        raise ErroreDati("Scrivi il tuo nome: serve per lo storico delle modifiche.")
    d = carica(pc)
    reg = {r["id"]: r for r in pr._leggi(pc, "registro", [])}
    ora = pr._ora()
    daapp = []
    for c in CAMPI_LISTA:
        cod = c["codice"]
        if cod not in righe:
            continue
        r = righe[cod]
        et = c["etichetta"]
        if c["tipo"] == "sino":
            tv = (r.get("valore") or "").strip().upper()
            if tv not in ("", "SI", "NO"):
                raise ErroreDati("%s: scegli Sì, No oppure lascia vuoto." % et)
            nuovo = tv or None
        else:
            try:
                nuovo = parse_numero(r.get("valore"))
            except ErroreDati as e:
                raise ErroreDati("%s: %s" % (et, e))
        ids = (r.get("id_documento") or "").strip()
        try:
            id_doc = int(ids) if ids else None
        except ValueError:
            raise ErroreDati("%s: documento di origine non valido." % et)
        if id_doc is not None and id_doc not in reg:
            raise ErroreDati("%s: il documento scelto non è nel registro." % et)
        ps = (r.get("pagina") or "").strip()
        try:
            pagina = int(ps) if ps else None
        except ValueError:
            raise ErroreDati("%s: la pagina deve essere un numero." % et)
        if pagina is not None and pagina < 1:
            raise ErroreDati("%s: la pagina deve essere un numero positivo." % et)
        stato = (r.get("stato") or DA_VERIFICARE).strip()
        if stato not in pr.NATURE_DATO:
            raise ErroreDati("%s: stato non valido." % et)
        if nuovo is not None and stato == "FATTO" and id_doc is None:
            raise ErroreDati("%s: per lo stato FATTO scegli il documento di origine (oppure usa DA VERIFICARE)." % et)
        note = (r.get("note") or "").strip()[:300]
        prec = d["campi"].get(cod)
        if nuovo is None and (prec is None or prec.get("valore") is None):
            continue   # campo lasciato vuoto: resta "non disponibile"
        if prec and (prec.get("valore"), prec.get("id_documento"), prec.get("pagina"), prec.get("stato"), prec.get("note") or "") == (nuovo, id_doc, pagina, stato, note):
            continue
        daapp.append((c, nuovo, id_doc, pagina, stato, note, prec, r.get("origine") == "LLM"))
    if not daapp:
        return []
    with modifica(pc, "dati modificati da %s" % chi):
        for c, nuovo, id_doc, pagina, stato, note, prec, da_llm in daapp:
            cod = c["codice"]
            valore_cambia = prec is not None and prec.get("valore") != nuovo
            if prec is None or prec.get("valore") is None:
                origine = "LLM" if da_llm else "OPERATORE"
            elif valore_cambia:
                origine = "CORRETTO"
            else:
                origine = prec["origine"]
            esercizio = (prec or {}).get("esercizio") or ((reg.get(id_doc) or {}).get("periodo_economico") if id_doc else None)
            rec = {"campo": cod, "valore": nuovo, "unita": c["unita"], "esercizio": esercizio, "id_documento": id_doc, "pagina": pagina, "stato": stato,
                   "note": note, "origine": origine, "da": chi, "il": ora,
                   "precedente": (_snap(prec) if (valore_cambia and prec.get("valore") is not None) else (prec or {}).get("precedente")),
                   "storico": ((prec or {}).get("storico") or []) + ([_snap(prec)] if prec else [])}
            d["campi"][cod] = rec
            _salva(pc, d)
            pr._verbale(pc, "DATO DECISIVO", "OK", "%s: %s -> %s (%s; stato %s) da %s" % (
                c["etichetta"], fmt_it(prec.get("valore")) if prec else ND, fmt_it(nuovo), ORIGINI[origine], stato, chi))
    return [x[0]["codice"] for x in daapp]


# ---------------------------------------------------------------- estrazione automatica (solo bilancio)
def riconosci_tipo_pdf(percorso):
    """Tipo probabile dal testo del PDF (solo le prime pagine). In dubbio: 'altro'. Non scrive nulla."""
    try:
        import pdfplumber
        with pdfplumber.open(str(percorso)) as doc:
            t = " ".join((p.extract_text() or "") for p in doc.pages[:4]).lower().replace("’", "'")
    except Exception:
        return "altro"
    if "centrale dei rischi" in t or "centrale rischi" in t:
        return "centrale rischi"
    if "visura" in t or "camera di commercio" in t:
        return "visura"
    if re.search(r"estratto di ruolo|agenzia delle entrate.?riscossione|cartelle? di pagamento", t):
        return "ruolo"
    if "situazione contabile" in t:
        return "situazione contabile"
    if "conto economico" in t:
        return "bilancio"
    return "altro"


def _val(res, chiave, anno):
    for lista in ("dati", "residui", "controllo"):
        for x in res.get(lista, []):
            if x["chiave"] == chiave and x["anno"] == anno:
                return x
    return None


def _applica_auto(d, c, valore, stato, id_doc, pagina, esercizio, nota, ora):
    prec = d["campi"].get(c)
    if prec is not None:
        if prec["origine"] in ("OPERATORE", "CORRETTO"):
            return "ignorato"   # il dato dell'operatore prevale sempre
        if prec.get("id_documento") != id_doc and (prec.get("esercizio") or "") > (esercizio or ""):
            return "ignorato"   # resta il dato dell'esercizio più recente
        if (prec.get("valore"), prec.get("id_documento"), prec.get("pagina"), prec.get("stato")) == (valore, id_doc, pagina, stato):
            return "invariato"
    d["campi"][c] = {"campo": c, "valore": valore, "unita": CAMPO[c]["unita"], "esercizio": esercizio, "id_documento": id_doc, "pagina": pagina,
                     "stato": stato, "note": nota, "origine": "AUTO", "da": CHI_SISTEMA, "il": ora, "precedente": (prec or {}).get("precedente"),
                     "storico": ((prec or {}).get("storico") or []) + ([_snap(prec)] if prec else [])}
    return "letto"


def estrai_bilancio(pc, cartella, id_doc):
    """Esegue il parser del bilancio sul PDF registrato e collega i valori letti ai dati della pratica (origine 'Estratto automaticamente').
    Nessun valore va nei log. Ritorna il resoconto (senza importi)."""
    reg = {r["id"]: r for r in pr._leggi(pc, "registro", [])}
    r = reg.get(id_doc)
    ora = pr._ora()
    rep = {"documento": id_doc, "il": ora, "esito": "NON ESEGUITA", "letti": [], "non_trovati": [], "ignorati": [], "avvisi": []}
    base = Path(cartella).resolve()
    if not r or not r.get("sha256"):
        rep["avvisi"].append("Documento non presente nel registro come file.")
        return rep
    try:
        p = (base / r["nome"]).resolve()
        p.relative_to(base)
        res = parser_bilancio.analizza(p)
    except Exception as e:   # nessun dettaglio del contenuto nei messaggi
        rep["esito"] = "NON RIUSCITA"
        rep["avvisi"].append("Il documento non è stato letto (%s): inserisci i valori a mano." % type(e).__name__)
        d = carica(pc)
        d["estrazioni"][str(id_doc)] = rep
        _salva(pc, d)
        return rep
    rep["avvisi"] += list(res.get("avvisi", []))[:5]
    if res["esito"] != "COMPLETATO" or not res.get("esercizi"):
        rep["esito"] = "NON LEGGIBILE"
        rep["avvisi"].append("Scansione o date degli esercizi non riconosciute: inserisci i valori a mano.")
        d = carica(pc)
        d["estrazioni"][str(id_doc)] = rep
        _salva(pc, d)
        return rep
    chius = {e["anno"]: e["data_chiusura"] for e in res["esercizi"]}
    with modifica(pc, "lettura automatica del documento %s" % id_doc):
        d = carica(pc)
        for campo, (chiave, anno) in MAPPA_AUTO.items():
            x = _val(res, chiave, anno)
            if x is None or x["valore"] is None:
                rep["non_trovati"].append(campo)
                continue
            nota = "Letto dal parser del bilancio (%s)." % chiave + ((" " + " ".join(x["note"][:2])) if x.get("note") else "")
            st = _applica_auto(d, campo, x["valore"], x["stato"], id_doc, x["fonte"].get("pagina"), chius.get(anno), nota, ora)
            (rep["letti"] if st in ("letto", "invariato") else rep["ignorati"]).append(campo)
        t, pv = _val(res, "sp.deb_tributari", -1), _val(res, "sp.deb_previdenza", -1)
        if t and pv and t["valore"] is not None and pv["valore"] is not None:
            st = peggiore(INFERENZA, t["stato"], pv["stato"])
            s = _applica_auto(d, "debiti_pubblici", t["valore"] + pv["valore"], st, id_doc, t["fonte"].get("pagina"), chius.get(-1),
                              "Somma di debiti tributari e previdenziali del bilancio: provvisoria, da riconciliare con l'estratto di ruolo.", ora)
            (rep["letti"] if s in ("letto", "invariato") else rep["ignorati"]).append("debiti_pubblici")
        else:
            rep["non_trovati"].append("debiti_pubblici")
        d["controlli_ko"] = [c for c in d["controlli_ko"] if c.get("id_documento") != id_doc] + [
            {"id_documento": id_doc, "descrizione": "Nel documento n. %s non quadra: %s (esercizio %s)." % (id_doc, c["nome"], c.get("esercizio"))}
            for c in res.get("controlli", []) if c.get("esito") == "KO"]
        rep["esito"] = "ESEGUITA"
        d["estrazioni"][str(id_doc)] = rep
        _salva(pc, d)
        pr._verbale(pc, "LETTURA AUTOMATICA", "OK", "documento %s (bilancio): %d campi letti, %d non trovati, %d lasciati all'operatore" % (
            id_doc, len(rep["letti"]), len(rep["non_trovati"]), len(rep["ignorati"])))
    aggiorna_documento(pc, id_doc, data_documento=chius.get(-1), periodo=(chius.get(-1) or "")[:4] or None, solo_vuoti=True, silenzioso=True)
    return rep


# ---------------------------------------------------------------- registro
def aggiorna_documento(pc, id_doc, tipo=None, data_documento=None, periodo=None, natura=None, solo_vuoti=False, silenzioso=False):
    if not pr._prima_di(pc, "NUMERI_VERIFICATI"):
        raise pr.ErrorePratica("Il registro è bloccato perché la pratica è avanzata: riaprila dalla vista avanzata per modificarlo.")
    reg = pr._leggi(pc, "registro", [])
    r = next((x for x in reg if x["id"] == id_doc), None)
    if not r:
        raise pr.ErrorePratica("Documento inesistente.")
    nuovi = {}
    if tipo is not None:
        if tipo not in TIPI_DOC:
            raise ErroreDati("Tipo di documento non valido.")
        nuovi["tipo"] = tipo
    if data_documento is not None:
        nuovi["data_documento"] = parse_data(data_documento)
    if periodo is not None:
        nuovi["periodo_economico"] = (periodo.strip()[:40] or None)
    if natura is not None and r.get("sha256"):
        if natura not in NATURE_FILE:
            raise ErroreDati("Natura del documento non valida.")
        nuovi["natura"] = natura
    if solo_vuoti:
        nuovi = {k: v for k, v in nuovi.items() if not r.get(k) and v}
    nuovi = {k: v for k, v in nuovi.items() if r.get(k) != v}
    if not nuovi:
        return False
    with modifica(pc, "registro modificato"):
        r.update(nuovi)
        pr._scrivi(pc, "registro", reg)
        if not silenzioso:
            pr._verbale(pc, "REGISTRO", "OK", "documento %s aggiornato: %s" % (id_doc, ", ".join(sorted(nuovi))))
    return True


# ---------------------------------------------------------------- incongruenze
def riapri_incongruenza(pc, id_inc, nome, motivo):
    nome, motivo = pr._nome(nome), (motivo or "").strip()
    if not motivo:
        raise pr.ErrorePratica("Scrivi il motivo della riapertura.")
    with modifica(pc, "incongruenza %s riaperta" % id_inc):
        inc = pr._leggi(pc, "inc", [])
        x = next((i for i in inc if i["id"] == id_inc), None)
        if not x:
            raise pr.ErrorePratica("Incongruenza inesistente.")
        x.update(stato="APERTA", risolta_da=None, risolta_il=None, nota_risoluzione=None)
        pr._scrivi(pc, "inc", inc)
        pr._verbale(pc, "INCONGRUENZA", "OK", "incongruenza %s riaperta da %s: %s" % (id_inc, nome, motivo))


def bozze_incongruenze(pc):
    """Proposte ovvie, da confermare: non entrano in pratica finché l'operatore non le conferma."""
    v, d = valori(pc), carica(pc)
    b = []
    att, pn, deb = v.get("totale_attivo"), v.get("patrimonio_netto"), v.get("debiti_totali")
    if None not in (att, pn, deb) and pn + deb > att * 1.005 + 1:
        b.append(("Il totale attivo è inferiore a patrimonio netto + debiti: il totale attivo non può essere minore (verificare i valori).", "SOSTANZIALE"))
    if v.get("debiti_pubblici") is not None and deb is not None and v["debiti_pubblici"] > deb * 1.005 + 1:
        b.append(("I debiti pubblici superano i debiti totali.", "SOSTANZIALE"))
    if v.get("liquidita_utilizzabile") is not None and v.get("disponibilita_liquide") is not None and v["liquidita_utilizzabile"] > v["disponibilita_liquide"] * 1.005 + 1:
        b.append(("La quota utilizzabile della liquidità supera le disponibilità liquide.", "MINORE"))
    for c in d["controlli_ko"]:
        b.append((c["descrizione"], "SOSTANZIALE"))
    esist = {x["descrizione"] for x in pr._leggi(pc, "inc", [])}
    return [{"descrizione": t, "gravita": g} for t, g in b if t not in esist]


# ---------------------------------------------------------------- elenco pratiche
NOME_OK = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,59}$")


def nome_cartella(nome):
    s = re.sub(r"[^A-Za-z0-9_-]+", "_", (nome or "").strip()).strip("_-")[:60]
    return s if NOME_OK.match(s or "") else None


def ultima_modifica(pc):
    v = pr._leggi(pc, "verbale", [])
    return v[-1]["timestamp"] if v else None


def elenco_pratiche(radice):
    out = []
    for dd in sorted(Path(radice).iterdir(), key=lambda p: p.name.lower()):
        if not (dd.is_dir() and NOME_OK.match(dd.name)):
            continue
        pc = dd / "PRATICA"
        if (pc / pr.FILE["pratica"]).is_file():
            try:
                info = pr._leggi(pc, "pratica")
                out.append({"cartella": dd.name, "nome": info.get("nome") or dd.name, "procedura": info.get("procedura") or "-", "stato": info["stato"],
                            "approvazione": approvazione(pc)["stato"], "modifica": ultima_modifica(pc),
                            "documenti": len([r for r in pr._leggi(pc, "registro", []) if r.get("sha256")]), "pratica": True})
                continue
            except (OSError, ValueError, KeyError):
                pass
        out.append({"cartella": dd.name, "nome": dd.name, "procedura": "-", "stato": "SENZA PRATICA", "approvazione": "-",
                    "modifica": datetime.fromtimestamp(dd.stat().st_mtime).astimezone().isoformat(timespec="seconds"), "documenti": 0, "pratica": False})
    return out


def crea_pratica(radice, nome, procedura, chi):
    nome = (nome or "").strip()
    cart = nome_cartella(nome)
    if not nome or not cart:
        raise ErroreDati("Scrivi un nome per la pratica (lettere e numeri).")
    if procedura not in PROCEDURE:
        raise ErroreDati("Scegli il tipo di procedura.")
    if (Path(radice) / cart).exists():
        raise ErroreDati("Esiste già una pratica con questo nome: scegline un altro oppure riaprila dall'elenco.")
    (Path(radice) / cart).mkdir()
    return cart, apri(Path(radice) / cart / "PRATICA", nome, procedura, chi)


def apri(pc, nome, procedura, chi):
    pr.apri_pratica(pc, nome, (chi or "").strip() or "operatore non indicato")
    st = pr._leggi(pc, "pratica")
    st["procedura"] = procedura
    pr._scrivi(pc, "pratica", st)
    sincronizza(pc)
    return pc
