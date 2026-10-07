"""Pratica: registro documentale, gate di verifica dei numeri, versione del motore, parametri usati, verbale a catena di hash.

Una pratica e' una cartella con: pratica.json, registro_documentale.json, dati_estratti.json, incongruenze.json,
richieste_prioritarie.json, numeri_decisivi.json, verbale.json (solo append, hash a catena), parametri_usati.json,
valutazione_v3.json (scritta solo a gate superato). Supporto alla decisione, non attestazione.

RACCOLTA NON BLOCCANTE: il gate (valuta) vale SOLO per il consolidamento. avvia_preanalisi() e' sempre possibile, anche a fascicolo
incompleto: produce preanalisi_provvisoria.json (o ricognizione_fascicolo.json se la documentazione e' troppo scarna), checklist.json
(stati delle voci A/B) e il documento Word. approva_come_provvisoria() registra nel verbale nome e data del titolare.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from datetime import datetime
from pathlib import Path

from analisi_crisi import checklist as ck
from analisi_crisi import semaforo_v3, versione

STATI = ["APERTA", "REGISTRO_PRONTO", "NUMERI_IN_VERIFICA", "NUMERI_VERIFICATI", "CONSOLIDATA"]
NATURE_DOC = ("STORICO", "AGGIORNATO", "STIMA", "NON DISPONIBILE")
NATURE_DATO = ("FATTO", "INFERENZA", "IPOTESI", "DA VERIFICARE")
GRAVITA = ("SOSTANZIALE", "MINORE")
STATI_INC = ("APERTA", "RISOLTA")
STATI_RICH = ("APERTA", "INVIATA", "EVASA")
DICITURA = "PROSPETTO PRE-CONCLUSIVO - nessuna conclusione prodotta: attende la verifica dei numeri decisivi"
NON_PRODOTTA = "Valutazione non prodotta: attende la verifica dei numeri decisivi"
FILE = {"pratica": "pratica.json", "registro": "registro_documentale.json", "dati": "dati_estratti.json", "inc": "incongruenze.json",
        "rich": "richieste_prioritarie.json", "num": "numeri_decisivi.json", "verbale": "verbale.json",
        "param": "parametri_usati.json", "val": "valutazione_v3.json", "pre": "preanalisi_provvisoria.json",
        "ric": "ricognizione_fascicolo.json", "appr": "approvazione_provvisoria.json"}
MODELLO = versione.RADICE / "Template_Preanalisi_Economico-Finanziaria_CNC.docx"
ZERO = "0" * 64


class ErrorePratica(Exception):
    pass


class GateNonSuperato(ErrorePratica):
    def __init__(self, motivi):
        self.motivi = list(motivi)
        super().__init__("; ".join(self.motivi))


def _p(pratica, chiave):
    return Path(pratica) / FILE[chiave]


def _ora():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _leggi(pratica, chiave, default=None):
    try:
        return json.loads(_p(pratica, chiave).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default


def _scrivi(pratica, chiave, dati):
    dest = _p(pratica, chiave)
    tmp = dest.with_name(dest.name + ".tmp")
    tmp.write_text(json.dumps(dati, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, dest)


def _nome(n):
    n = (n or "").strip()
    if not n:
        raise ErrorePratica("serve il nome di chi esegue l'operazione")
    return n


# ---------------------------------------------------------------- verbale (solo append, hash a catena)
def _hash_record(rec):
    corpo = {k: v for k, v in rec.items() if k != "hash"}
    return hashlib.sha256(json.dumps(corpo, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest()


def _verbale(pratica, controllo, esito, dettaglio=""):
    """Unico punto di scrittura del verbale: aggiunge un record concatenato al precedente."""
    v = _leggi(pratica, "verbale", [])
    st = _leggi(pratica, "pratica")
    rec = {"n": len(v) + 1, "timestamp": _ora(), "controllo": controllo, "esito": esito, "dettaglio": dettaglio,
           "versione_motore": versione.MOTORE, "impronta": versione.impronta(), "prec": v[-1]["hash"] if v else ZERO}
    rec["hash"] = _hash_record(rec)
    v.append(rec)
    _scrivi(pratica, "verbale", v)
    st["verbale_n"], st["verbale_ultimo"] = rec["n"], rec["hash"]
    _scrivi(pratica, "pratica", st)
    return rec


def verifica_verbale(pratica):
    """Controllo di integrita': {'ok': bool, 'n': record, 'errore': str|None}. Rileva modifica, cancellazione, inserimento, troncamento."""
    try:
        v = _leggi(pratica, "verbale", [])
        st = _leggi(pratica, "pratica") or {}
    except ValueError:
        return {"ok": False, "n": 0, "errore": "verbale illeggibile"}
    prec = ZERO
    for i, r in enumerate(v, 1):
        if r.get("n") != i:
            return {"ok": False, "n": len(v), "errore": f"numerazione interrotta al record {i}"}
        if r.get("prec") != prec:
            return {"ok": False, "n": len(v), "errore": f"catena interrotta al record {i}"}
        if r.get("hash") != _hash_record(r):
            return {"ok": False, "n": len(v), "errore": f"record {i} alterato"}
        prec = r["hash"]
    if st.get("verbale_n") != len(v) or st.get("verbale_ultimo") != (prec if v else None):
        return {"ok": False, "n": len(v), "errore": "verbale troncato o non allineato allo stato della pratica"}
    return {"ok": True, "n": len(v), "errore": None}


# ---------------------------------------------------------------- apertura e stato
def apri_pratica(cartella, nome, aperta_da, dataset_simulato=False):
    c = Path(cartella)
    if (c / FILE["pratica"]).exists():
        raise ErrorePratica("pratica gia' esistente")
    c.mkdir(parents=True, exist_ok=True)
    for k in ("registro", "dati", "inc", "rich", "num", "verbale"):
        _scrivi(c, k, [])
    _scrivi(c, "pratica", {"nome": nome, "stato": STATI[0], "aperta_il": _ora(), "aperta_da": _nome(aperta_da),
                           "dataset_simulato": bool(dataset_simulato), "verbale_n": 0, "verbale_ultimo": None})
    _verbale(c, "APERTURA", "OK", f"pratica '{nome}' aperta da {aperta_da}")
    return c


def stato(pratica):
    return _leggi(pratica, "pratica")["stato"]


def _almeno(pratica, s):
    return STATI.index(stato(pratica)) >= STATI.index(s)


def _prima_di(pratica, s):
    return STATI.index(stato(pratica)) < STATI.index(s)


def _precondizioni(pratica, prossimo):
    m = []
    if prossimo == "REGISTRO_PRONTO" and not _leggi(pratica, "registro"):
        m.append("registro documentale vuoto")
    if prossimo == "NUMERI_IN_VERIFICA" and not _leggi(pratica, "num"):
        m.append("nessun numero decisivo proposto")
    if prossimo == "NUMERI_VERIFICATI":
        m += _motivi_gate_dati(pratica)
    if prossimo == "CONSOLIDATA" and not _p(pratica, "val").exists():
        m.append("valutazione non ancora prodotta")
    return m


def avanza(pratica, a=None, nome=None):
    """Avanza di UN solo passo, in ordine. 'a' (facoltativo) deve essere lo stato immediatamente successivo."""
    s = stato(pratica)
    i = STATI.index(s)
    if i == len(STATI) - 1:
        _verbale(pratica, "AVANZAMENTO", "RIFIUTATO", "gia' CONSOLIDATA")
        raise ErrorePratica("pratica gia' consolidata")
    prossimo = STATI[i + 1]
    if a is not None and a != prossimo:
        _verbale(pratica, "AVANZAMENTO", "RIFIUTATO", f"salto {s} -> {a} non ammesso")
        raise ErrorePratica(f"avanzamento a salti non ammesso: da {s} si va solo a {prossimo}")
    mancano = _precondizioni(pratica, prossimo)
    if mancano:
        _verbale(pratica, "AVANZAMENTO", "RIFIUTATO", f"{s} -> {prossimo}: " + "; ".join(mancano))
        raise ErrorePratica("precondizioni non soddisfatte: " + "; ".join(mancano))
    st = _leggi(pratica, "pratica")
    st["stato"] = prossimo
    _scrivi(pratica, "pratica", st)
    _verbale(pratica, "AVANZAMENTO", "OK", f"{s} -> {prossimo}" + (f" (da {nome.strip()})" if nome and nome.strip() else ""))
    return prossimo


def riapri(pratica, a_stato, motivo, nome):
    """Unico modo di tornare indietro: lascia traccia nel verbale (chi, perche', da/a)."""
    nome, motivo = _nome(nome), (motivo or "").strip()
    if not motivo:
        raise ErrorePratica("serve il motivo della riapertura")
    s = stato(pratica)
    if a_stato not in STATI or STATI.index(a_stato) >= STATI.index(s):
        raise ErrorePratica(f"la riapertura deve tornare a uno stato precedente a {s}")
    st = _leggi(pratica, "pratica")
    st["stato"] = a_stato
    _scrivi(pratica, "pratica", st)
    _verbale(pratica, "RIAPERTURA", "OK", f"{s} -> {a_stato} da {nome}: {motivo}")
    return a_stato


# ---------------------------------------------------------------- registro documentale
def _sha256_file(percorso):
    h = hashlib.sha256()
    with open(percorso, "rb") as f:
        for blocco in iter(lambda: f.read(1 << 20), b""):
            h.update(blocco)
    return h.hexdigest()


def registra_documento(pratica, nome, percorso=None, tipo="", data_documento=None, periodo=None, natura="STORICO", decisivo=False):
    """Con 'percorso' registra un file (sha256; data di acquisizione impostata DAL SISTEMA, non dal chiamante).
    Senza 'percorso' registra un documento ATTESO MA MANCANTE (natura NON DISPONIBILE)."""
    if not _prima_di(pratica, "NUMERI_VERIFICATI"):
        raise ErrorePratica("registro bloccato: riaprire la pratica per modificarlo")
    reg = _leggi(pratica, "registro")
    if percorso is None:
        natura, h, acq = "NON DISPONIBILE", None, None
    else:
        if natura not in NATURE_DOC or natura == "NON DISPONIBILE":
            raise ErrorePratica("natura non valida per un file presente")
        h, acq = _sha256_file(percorso), _ora()
        if any(r["sha256"] == h for r in reg):
            _verbale(pratica, "REGISTRO", "RIFIUTATO", f"duplicato di contenuto: {nome}")
            raise ErrorePratica("documento gia' registrato (stesso contenuto)")
    riga = {"id": max([r["id"] for r in reg] + [0]) + 1, "nome": nome, "sha256": h, "tipo": tipo, "data_acquisizione": acq,
            "data_documento": data_documento, "periodo_economico": periodo, "natura": natura, "decisivo": bool(decisivo)}
    reg.append(riga)
    _scrivi(pratica, "registro", reg)
    _verbale(pratica, "REGISTRO", "OK", f"documento {riga['id']} '{nome}' natura {natura}")
    return riga


# ---------------------------------------------------------------- dati, incongruenze, richieste
def aggiungi_dato(pratica, dato, valore, unita, natura, id_documento=None, pagina=None):
    if natura not in NATURE_DATO:
        raise ErrorePratica("natura del dato non valida")
    reg = {r["id"]: r for r in _leggi(pratica, "registro")}
    if id_documento is not None and id_documento not in reg:
        raise ErrorePratica("documento inesistente nel registro")
    if natura == "FATTO" and id_documento is None:
        raise ErrorePratica("un FATTO richiede il documento di origine")
    dati = _leggi(pratica, "dati")
    riga = {"id": len(dati) + 1, "dato": dato, "valore": valore, "unita": unita, "natura": natura, "id_documento": id_documento, "pagina": pagina}
    dati.append(riga)
    _scrivi(pratica, "dati", dati)
    _verbale(pratica, "DATO", "OK", f"dato {riga['id']} '{dato}' {natura}")
    return riga


def aggiungi_incongruenza(pratica, descrizione, dati_coinvolti, gravita):
    if gravita not in GRAVITA:
        raise ErrorePratica("gravita' non valida")
    inc = _leggi(pratica, "inc")
    riga = {"id": len(inc) + 1, "descrizione": descrizione, "dati_coinvolti": list(dati_coinvolti or []), "gravita": gravita, "stato": "APERTA",
            "aperta_il": _ora(), "risolta_da": None, "risolta_il": None, "nota_risoluzione": None}
    inc.append(riga)
    _scrivi(pratica, "inc", inc)
    _verbale(pratica, "INCONGRUENZA", "OK", f"incongruenza {riga['id']} {gravita} aperta")
    return riga


def risolvi_incongruenza(pratica, id_inc, nome, nota):
    nome, nota = _nome(nome), (nota or "").strip()
    if not nota:
        raise ErrorePratica("serve la nota di risoluzione")
    inc = _leggi(pratica, "inc")
    r = next((x for x in inc if x["id"] == id_inc), None)
    if not r:
        raise ErrorePratica("incongruenza inesistente")
    r.update(stato="RISOLTA", risolta_da=nome, risolta_il=_ora(), nota_risoluzione=nota)
    _scrivi(pratica, "inc", inc)
    _verbale(pratica, "INCONGRUENZA", "OK", f"incongruenza {id_inc} risolta da {nome}")
    return r


def aggiungi_richiesta(pratica, richiesta, perche, priorita, destinatario):
    if priorita not in (1, 2, 3):
        raise ErrorePratica("priorita' da 1 a 3")
    rich = _leggi(pratica, "rich")
    riga = {"id": len(rich) + 1, "richiesta": richiesta, "perche": perche, "priorita": priorita, "destinatario": destinatario, "stato": "APERTA"}
    rich.append(riga)
    _scrivi(pratica, "rich", rich)
    _verbale(pratica, "RICHIESTA", "OK", f"richiesta {riga['id']} priorita' {priorita}")
    return riga


def aggiorna_richiesta(pratica, id_rich, nuovo_stato):
    if nuovo_stato not in STATI_RICH:
        raise ErrorePratica("stato richiesta non valido")
    rich = _leggi(pratica, "rich")
    r = next((x for x in rich if x["id"] == id_rich), None)
    if not r:
        raise ErrorePratica("richiesta inesistente")
    r["stato"] = nuovo_stato
    _scrivi(pratica, "rich", rich)
    _verbale(pratica, "RICHIESTA", "OK", f"richiesta {id_rich} -> {nuovo_stato}")
    return r


# ---------------------------------------------------------------- numeri decisivi
def proponi_numeri_decisivi(pratica, elenco):
    """elenco: [{'nome','valore','unita','fonte'}]. Ogni numero nasce NON confermato."""
    if not _prima_di(pratica, "NUMERI_VERIFICATI"):
        raise ErrorePratica("numeri bloccati: riaprire la pratica per aggiungerne")
    num = _leggi(pratica, "num")
    nuovi = []
    for e in elenco:
        riga = {"id": len(num) + 1, "nome": e["nome"], "valore_proposto": e.get("valore"), "unita": e.get("unita"), "fonte": e.get("fonte"),
                "confermato_da": None, "data_conferma": None, "corretto_a": None, "storico": []}
        num.append(riga)
        nuovi.append(riga)
    _scrivi(pratica, "num", num)
    _verbale(pratica, "NUMERI DECISIVI", "OK", f"proposti {len(nuovi)} numeri")
    return nuovi


def conferma_numero(pratica, id_numero, confermato_da, corretto_a=None):
    """Conferma (o corregge) un numero decisivo. Richiede il nome di chi conferma. Le conferme precedenti restano in 'storico'."""
    try:
        chi = _nome(confermato_da)
    except ErrorePratica:
        _verbale(pratica, "CONFERMA NUMERO", "RIFIUTATO", f"numero {id_numero}: nome di chi conferma mancante")
        raise
    if stato(pratica) != "NUMERI_IN_VERIFICA":
        _verbale(pratica, "CONFERMA NUMERO", "RIFIUTATO", f"numero {id_numero}: stato {stato(pratica)} non ammette conferme")
        raise ErrorePratica("le conferme si danno solo nello stato NUMERI_IN_VERIFICA")
    num = _leggi(pratica, "num")
    r = next((x for x in num if x["id"] == id_numero), None)
    if not r:
        raise ErrorePratica("numero inesistente")
    if r["confermato_da"]:
        r["storico"].append({k: r[k] for k in ("confermato_da", "data_conferma", "corretto_a")})
    r["confermato_da"], r["data_conferma"], r["corretto_a"] = chi, _ora(), corretto_a
    _scrivi(pratica, "num", num)
    _verbale(pratica, "CONFERMA NUMERO", "OK", f"numero {id_numero} '{r['nome']}' " + (f"corretto a {corretto_a} " if corretto_a is not None else "confermato ") + f"da {chi}")
    return r


# ---------------------------------------------------------------- gate
def _motivi_gate_dati(pratica):
    m = []
    num = _leggi(pratica, "num")
    if not num:
        m.append("nessun numero decisivo proposto")
    nc = [str(x["id"]) for x in num if not x.get("confermato_da")]
    if nc:
        m.append("numeri decisivi non confermati: " + ", ".join(nc))
    sos = [str(x["id"]) for x in _leggi(pratica, "inc") if x["gravita"] == "SOSTANZIALE" and x["stato"] == "APERTA"]
    if sos:
        m.append("incongruenze SOSTANZIALI aperte: " + ", ".join(sos))
    return m


def motivi_gate(pratica):
    """Elenco dei motivi per cui il gate NON e' superato (vuoto = superato). Non scrive nel verbale."""
    m = [] if _almeno(pratica, "NUMERI_VERIFICATI") else [f"stato {stato(pratica)}: servono almeno NUMERI_VERIFICATI"]
    return m + _motivi_gate_dati(pratica)


def gate_superato(pratica):
    return not motivi_gate(pratica)


def valuta(pratica, metriche, documenti=None, decisivi=None, **kw):
    """Calcola la valutazione v3 SOLO a gate superato; altrimenti GateNonSuperato (e record nel verbale).
    documenti/decisivi omessi: derivati dal registro. kw: percorso_ipotizzabile, scenari_tutti_valutabili, esito_scenari, soglie, dataset_simulato."""
    motivi = motivi_gate(pratica)
    if motivi:
        _verbale(pratica, "GATE VALUTAZIONE", "RIFIUTATO", "; ".join(motivi))
        raise GateNonSuperato(motivi)
    reg = _leggi(pratica, "registro")
    if documenti is None:
        documenti = [{"nome": r["nome"], "disponibile": r["natura"] != "NON DISPONIBILE", "aggiornato": r["natura"] == "AGGIORNATO"} for r in reg]
    if decisivi is None:
        decisivi = [{"nome": r["nome"], "disponibile": r["natura"] != "NON DISPONIBILE"} for r in reg if r.get("decisivo")]
    kw.setdefault("dataset_simulato", bool(_leggi(pratica, "pratica").get("dataset_simulato")))
    res = semaforo_v3.valuta_v3(metriche, documenti, decisivi, **kw)
    ts, imp = _ora(), versione.impronta()
    _scrivi(pratica, "param", {"timestamp": ts, "versione_motore": versione.MOTORE, "impronta": imp, "parametri": versione.parametri(),
                               "parametri_passati": kw.get("soglie")})
    _scrivi(pratica, "val", {"timestamp": ts, "versione_motore": versione.MOTORE, "impronta": imp, "metriche": metriche, "valutazione": res})
    _verbale(pratica, "VALUTAZIONE", "OK", f"gate superato; fattibilita' {res['fattibilita']['esito']}; {res['stato']}")
    return res


def valutazione_prodotta(pratica):
    """La valutazione salvata, solo se il gate e' (ancora) superato; altrimenti None."""
    if not gate_superato(pratica):
        return None
    return _leggi(pratica, "val")


# ---------------------------------------------------------------- prospetto pre-conclusivo
def prospetto_preconclusivo(pratica):
    st = _leggi(pratica, "pratica")
    reg = _leggi(pratica, "registro")
    nomi = {r["id"]: r["nome"] for r in reg}
    dati = [dict(d, documento=nomi.get(d["id_documento"])) for d in _leggi(pratica, "dati")]
    return {"dicitura": DICITURA, "pratica": st["nome"], "stato": st["stato"], "registro": reg, "dati_estratti": dati,
            "incongruenze": _leggi(pratica, "inc"), "richieste": sorted(_leggi(pratica, "rich"), key=lambda r: r["priorita"]),
            "numeri_decisivi": _leggi(pratica, "num"), "versione_motore": versione.MOTORE, "impronta": versione.impronta()}


def _t(v):
    return "" if v is None else str(v)


def genera_prospetto_word(pratica, uscita=None, modello=None):
    """Documento Word del prospetto: nessun colore di semaforo, nessun giudizio."""
    from analisi_crisi import word_xml as w
    d = prospetto_preconclusivo(pratica)
    P = [w.par(w.run(d["dicitura"], True, "365F91", 26), "Corpo", dopo=60),
         w.testo(f"Pratica: {d['pratica']} - stato: {d['stato']}. Elaborazione del {_ora()}.", dim=19, dopo=40),
         w.testo(f"Motore: {d['versione_motore']} - impronta: {d['impronta']}", dim=16, dopo=60)]

    def sez(titolo, intest, larg, righe, vuoto):
        P.append(w.h1(titolo))
        P.append(w.tabella([intest] + righe, larg, dim=16) if righe else w.testo(vuoto, dim=17))
    sez("1. Registro documentale", ["Id", "Documento", "Tipo", "Acquisito il", "Data doc.", "Periodo", "Natura", "SHA-256"], [400, 2200, 900, 1500, 1000, 1000, 1100, 1500],
        [[r["id"], r["nome"], _t(r["tipo"]), _t(r["data_acquisizione"]), _t(r["data_documento"]), _t(r["periodo_economico"]), r["natura"], _t(r["sha256"])[:12]] for r in d["registro"]], "Nessun documento registrato.")
    sez("2. Dati estratti, con fonte e pagina", ["Dato", "Valore", "Unità", "Natura", "Documento", "Pag."], [2800, 1600, 900, 1500, 2400, 600],
        [[x["dato"], _t(x["valore"]), _t(x["unita"]), x["natura"], _t(x["documento"]), _t(x["pagina"])] for x in d["dati_estratti"]], "Nessun dato estratto.")
    sez("3. Incongruenze", ["Id", "Descrizione", "Dati coinvolti", "Gravità", "Stato"], [400, 4300, 2300, 1300, 1000],
        [[x["id"], x["descrizione"], ", ".join(map(str, x["dati_coinvolti"])), x["gravita"], x["stato"]] for x in d["incongruenze"]], "Nessuna incongruenza registrata.")
    sez("4. Richieste prioritarie", ["Pri.", "Richiesta", "Perché serve", "Destinatario", "Stato"], [500, 3200, 3000, 1600, 1000],
        [[x["priorita"], x["richiesta"], x["perche"], x["destinatario"], x["stato"]] for x in d["richieste"]], "Nessuna richiesta.")
    sez("5. Numeri decisivi da verificare", ["Id", "Numero", "Valore proposto", "Fonte", "Conferma"], [400, 3000, 1800, 2400, 1700],
        [[x["id"], x["nome"], _t(x["valore_proposto"]) + (" " + _t(x["unita"]) if x["unita"] else ""), _t(x["fonte"]),
          ("confermato da " + x["confermato_da"] if x["confermato_da"] else "DA VERIFICARE") + (f" (corretto a {x['corretto_a']})" if x["corretto_a"] is not None else "")] for x in d["numeri_decisivi"]], "Nessun numero proposto.")
    P.append(w.testo(f"Versione del motore: {d['versione_motore']} - impronta dei parametri: {d['impronta']}", dim=16))
    cart = Path(pratica)
    out = Path(uscita) if uscita else cart / f"Prospetto_preconclusivo_{time.strftime('%Y%m%d-%H%M%S')}.docx"
    n = 1
    while out.exists():  # w.salva non sovrascrive mai
        out = out.with_name(f"{out.stem.split('_v')[0]}_v{n}{out.suffix}")
        n += 1
    w.salva(modello or MODELLO, "".join(P), out, a4=True)
    _verbale(pratica, "PROSPETTO PRE-CONCLUSIVO", "OK", f"generato {out.name}")
    return out


# ================================================================ raccolta non bloccante: preanalisi provvisoria
DICITURA_PROVVISORIA = "PREANALISI PROVVISORIA - non consolidata, in attesa di revisione del titolare"
ETICHETTA_GIUDIZIO = "PRELIMINARE / PROVVISORIO"
APPROVATA = "APPROVATA COME PROVVISORIA"
ND = ck.ND
TESTO_RUOLI, TESTO_CR = ck.TESTO_RUOLI, ck.TESTO_CR
MAX_RICHIESTE = 5


def _metriche(pratica, metriche):
    if metriche is not None:
        return metriche or None
    try:
        return json.loads((Path(pratica) / "metriche.json").read_text(encoding="utf-8")) or None
    except (OSError, ValueError):
        return None


def _pct(v):
    return ("%.1f%%" % (v * 100)).replace(".", ",")


def _num(v):
    return ("%.2f" % v).replace(".", ",")


def _sezioni(m, sost, ck_a):
    """Sezioni di calcolo: CALCOLABILE solo se il dato esiste. Un dato mancante non diventa mai zero."""
    crit = {c["codice"]: c for c in sost["criteri"]}
    out = []

    def add(nome, cod, fmt, nota=""):
        c = crit[cod]
        if c["valore"] is None or c["colore"] is None:
            out.append({"sezione": nome, "stato": "NON CALCOLABILE", "valore": ND, "esito": None, "nota": "Mancano i dati necessari: " + ND + "."})
        else:
            out.append({"sezione": nome, "stato": "CALCOLABILE", "valore": fmt(c["valore"]), "esito": c["colore"], "nota": (nota + " " + c["nota"]).strip()})
    add("Margine EBITDA", "margine", _pct)
    add("Rapporto semplificato debito netto/EBITDA (flusso più prudente)", "rapporto", _num)
    add("Patrimonio netto / attivo", "patrimonio", _pct)
    add("Debiti pubblici / attivo", "pubblici", _pct,
        "" if ck_a["A3"]["stato"] == "ricevuto" else "Dato contabile " + ck.FALLBACK_RUOLI + ".")
    if m.get("cassa_verificata"):
        out.append({"sezione": "Flusso di cassa disponibile (tesoreria)", "stato": "CALCOLABILE", "valore": "verificato", "esito": None, "nota": "Verificato dal titolare."})
    else:
        out.append({"sezione": "Flusso di cassa disponibile (tesoreria)", "stato": "NON CALCOLABILE", "valore": ND, "esito": None,
                    "nota": "L'EBITDA non equivale a cassa: servono rendiconto finanziario o movimenti di tesoreria."})
    return out


def _richieste(ck_all, segn, inc_sost):
    """Al massimo 5 richieste, ordinate per effetto sul giudizio."""
    cand = []
    for g in ("A", "B"):
        for v in ck_all[g]:
            if v["stato"] in ("ricevuto", "non pertinente") or not v["suggerita"]:
                continue
            if v["stato"] == "da aggiornare":
                testo = "Versione aggiornata di: " + v["etichetta"]
            elif v["stato"] == "illeggibile":
                testo = "Copia leggibile di: " + v["etichetta"]
            else:
                testo = v["etichetta"]
            if g == "A":
                punt = {"A2": 100, "A3": 60 if "pubblici" in segn else 35, "A4": 55, "A1": 40}[v["id"]]
                effetto = "Rende calcolabili o verificabili i dati di base" if v["id"] == "A2" else "Riduce un limite informativo dichiarato: " + v["fallback"]
                perche = v["fallback"]
            else:
                punt = 70 + 10 * len(v["scenari"])
                effetto = "Riattiva il giudizio sugli scenari: " + "; ".join(v["scenari_nomi"])
                perche = "Criticità: " + str(v["criticita"])
            punt += 15 if v["stato"] in ("da aggiornare", "illeggibile") else 0
            cand.append({"voce": v["id"], "richiesta": testo, "perche": perche, "permette_di_verificare": v["verifica"], "effetto_sul_giudizio": effetto, "_p": punt})
    if inc_sost:
        cand.append({"voce": None, "richiesta": "Chiarimento delle incongruenze sostanziali aperte (n. " + ", ".join(map(str, inc_sost)) + ")",
                     "perche": "I dati coinvolti non quadrano tra loro", "permette_di_verificare": "affidabilità dei numeri decisivi",
                     "effetto_sul_giudizio": "Senza chiarimento i numeri decisivi non possono essere confermati", "_p": 90})
    cand.sort(key=lambda r: -r["_p"])
    out = []
    for i, r in enumerate(cand[:MAX_RICHIESTE], 1):
        r = dict(r)
        r.pop("_p")
        r["ordine"] = i
        out.append(r)
    return out


def _costruisci(pratica, m, percorso_ipotizzabile, soglie):
    reg = _leggi(pratica, "registro", [])
    ricevuti = ck.documenti_ricevuti(pratica)
    ck_all = ck.stato_checklist(pratica, m)
    ck_a = {v["id"]: v for v in ck_all["A"]}
    segn = ck.segnali(m)
    sost = semaforo_v3.sostenibilita(m or {}, soglie)
    usabile = bool(m) and any(c["colore"] for c in sost["criteri"] if c["codice"] != "cassa")
    tipo = "PREANALISI_PROVVISORIA" if (ricevuti and usabile) else "RICOGNIZIONE_FASCICOLO"
    iniz, concl = ck.sufficienza_per_iniziare(pratica, m), ck.sufficienza_per_concludere(pratica, m)
    sosp = ck.sospensioni(pratica, m)
    nomi = {r["id"]: r["nome"] for r in reg}
    dati = [{"dato": d["dato"], "valore": ND if d["valore"] is None else d["valore"], "unita": d.get("unita") or "", "natura": d["natura"],
             "fonte": nomi.get(d["id_documento"], "non indicata"), "pagina": d.get("pagina")} for d in _leggi(pratica, "dati", [])]
    inc = _leggi(pratica, "inc", [])
    inc_sost = [x["id"] for x in inc if x["gravita"] == "SOSTANZIALE" and x["stato"] == "APERTA"]
    crit = [{"tipo": "incongruenza", "testo": x["descrizione"], "gravita": x["gravita"], "stato": x["stato"]} for x in inc]
    crit += [{"tipo": "criticità rilevata", "testo": t, "gravita": "", "stato": "da approfondire"} for t in segn.values()]
    fallback = []
    if ck_a["A3"]["stato"] != "ricevuto":
        fallback.append(TESTO_RUOLI)
    if ck_a["A4"]["stato"] != "ricevuto":
        fallback.append(TESTO_CR)
    d = {"tipo": tipo, "dicitura": DICITURA_PROVVISORIA, "pratica": _leggi(pratica, "pratica")["nome"], "generata_il": _ora(),
         "versione_motore": versione.MOTORE, "impronta": versione.impronta(), "limiti_informativi": list(iniz["limiti"]),
         "checklist": ck_all, "dati_estratti": dati, "criticita": crit, "fallback": fallback,
         "sufficienza": {"per_iniziare": iniz, "per_concludere": concl}, "richieste_prioritarie": _richieste(ck_all, segn, inc_sost),
         "scenari": [], "sezioni": [], "giudizi_preliminari": [], "riquadri": {}}
    for k, nome in ck.SCENARI.items():
        if k in sosp:
            d["scenari"].append({"scenario": nome, "stato": "GIUDIZIO SOSPESO", "motivo": sosp[k], "etichetta": ETICHETTA_GIUDIZIO})
        elif tipo == "PREANALISI_PROVVISORIA":
            d["scenari"].append({"scenario": nome, "stato": "VALUTABILE IN VIA PRELIMINARE", "motivo": ["Nessun approfondimento decisivo mancante tra quelli suggeriti."], "etichetta": ETICHETTA_GIUDIZIO})
        else:
            d["scenari"].append({"scenario": nome, "stato": "NON VALUTABILE", "motivo": ["Documentazione contabile insufficiente per una preanalisi economico-finanziaria."], "etichetta": ETICHETTA_GIUDIZIO})
    stato_concl = "PROVVISORIA - non definitiva: " + ("; ".join(concl["motivi"]) if concl["motivi"] else "in attesa della revisione del titolare")
    if tipo == "PREANALISI_PROVVISORIA":
        d["sezioni"] = _sezioni(m, sost, ck_a)
        for c in sost["criteri"]:
            if c["colore"]:
                d["giudizi_preliminari"].append({"giudizio": c["nome"], "esito": c["colore"], "motivazione": c["nota"], "etichetta": ETICHETTA_GIUDIZIO})
        for v in sost["vicini"]:
            d["criticita"].append({"tipo": "prossimo a una soglia", "testo": "%s: %s (%s %s)" % (v["criterio"], _num(v["valore"]), v["lato"], _num(v["soglia"])), "gravita": "", "stato": "da approfondire"})
        documenti = [{"nome": r["nome"], "disponibile": r["natura"] != "NON DISPONIBILE", "aggiornato": r["natura"] == "AGGIORNATO"} for r in reg]
        decisivi = [{"nome": r["nome"], "disponibile": False} for r in reg if r.get("decisivo") and r["natura"] == "NON DISPONIBILE"]
        visti = {x["nome"] for x in decisivi}
        for sc, mm in sosp.items():
            for v in ck_all["B"]:
                if v["suggerita"] and v["stato"] in ("mancante", "da aggiornare", "illeggibile") and sc in v["scenari"] and v["etichetta"] not in visti:
                    visti.add(v["etichetta"])
                    decisivi.append({"nome": v["etichetta"], "disponibile": False})
        q = semaforo_v3.qualita_dati(documenti, decisivi)
        q["colore"] = {"INSUFFICIENTE": None, "BASSA": "GIALLO"}.get(q["livello"], q["colore"])   # mai rosso per la sola assenza di documenti
        f = semaforo_v3.fattibilita(sost, q, percorso_ipotizzabile, False, None)
        d["riquadri"] = {
            "sostenibilita": {"titolo": "Allerta finanziaria / sostenibilità sui dati storici", "esito": sost["colore"], "dettaglio": sost["etichetta"] + " - calcolata sui soli criteri disponibili", "etichetta": ETICHETTA_GIUDIZIO},
            "qualita_dati": {"titolo": "Qualità dei dati", "esito": q["livello"], "colore": q["colore"], "dettaglio": "Documenti disponibili %d/%d; dati decisivi mancanti: %s" % (q["documenti_disponibili"], q["documenti_totali"], ", ".join(q["decisivi_mancanti"]) or "nessuno")},
            "fattibilita": {"titolo": "Fattibilità", "esito": f["esito"], "colore": f["colore"], "dettaglio": "Provvisoria: la fattibilità non può essere definitiva in questa fase", "etichetta": ETICHETTA_GIUDIZIO},
            "stato_conclusione": {"titolo": "Stato della conclusione", "esito": stato_concl}}
    else:
        d["sezioni"] = [{"sezione": s, "stato": "NON CALCOLABILE", "valore": ND, "esito": None, "nota": "Documentazione contabile o metriche non disponibili."}
                        for s in ("Margine EBITDA", "Rapporto semplificato debito netto/EBITDA", "Patrimonio netto / attivo", "Debiti pubblici / attivo", "Flusso di cassa disponibile (tesoreria)")]
        d["riquadri"] = {
            "sostenibilita": {"titolo": "Allerta finanziaria / sostenibilità sui dati storici", "esito": "ND", "dettaglio": "Non valutabile: " + ND, "etichetta": ETICHETTA_GIUDIZIO},
            "qualita_dati": {"titolo": "Qualità dei dati", "esito": "INSUFFICIENTE", "colore": None, "dettaglio": "Fascicolo troppo scarno per una preanalisi: ricognizione e richieste prioritarie"},
            "fattibilita": {"titolo": "Fattibilità", "esito": "NON CONCLUDENTE", "colore": None, "dettaglio": "Nessuna valutazione possibile con i dati disponibili", "etichetta": ETICHETTA_GIUDIZIO},
            "stato_conclusione": {"titolo": "Stato della conclusione", "esito": stato_concl}}
    d["sezioni_non_valutabili"] = [s["sezione"] + ": " + s["nota"] for s in d["sezioni"] if s["stato"] == "NON CALCOLABILE"] + \
        [x["scenario"] + ": " + "; ".join(x["motivo"]) for x in d["scenari"] if x["stato"] != "VALUTABILE IN VIA PRELIMINARE"]
    return d


def avvia_preanalisi(pratica, metriche=None, nome=None, percorso_ipotizzabile=False, soglie=None, genera_word=True):
    """Avvia la preanalisi SENZA gate. Funziona con fascicolo incompleto o registro vuoto.
    metriche omesse: lette da <pratica>/metriche.json se presente. Registra nel verbale l'avvio, i limiti informativi e la versione del motore."""
    if not (Path(pratica) / FILE["pratica"]).is_file():
        raise ErrorePratica("pratica inesistente: crearla prima (basta il nome di chi la apre)")
    m = _metriche(pratica, metriche)
    d = _costruisci(pratica, m, percorso_ipotizzabile, soglie)
    chi = (nome or "").strip() or "operatore non indicato"
    _verbale(pratica, "AVVIO PREANALISI", "OK", "avviata da %s (%s); limiti informativi: %s; sufficienza per iniziare: sì; per concludere: %s" % (
        chi, d["tipo"], " | ".join(d["limiti_informativi"]) or "nessuno", "sì" if d["sufficienza"]["per_concludere"]["ok"] else "no"))
    chiave = "pre" if d["tipo"] == "PREANALISI_PROVVISORIA" else "ric"
    if genera_word:
        out = genera_preanalisi_word(pratica, d)
        d["documento_word"] = out.name
    d["avviata_da"] = chi
    _scrivi(pratica, chiave, d)
    _verbale(pratica, "PREANALISI PROVVISORIA", "OK", "prodotto %s%s" % (FILE[chiave], (" e " + d["documento_word"]) if d.get("documento_word") else ""))
    return d


def ultima_preanalisi(pratica):
    """Il prodotto piu' recente (preanalisi o ricognizione), o None."""
    c = [x for x in (_leggi(pratica, "pre"), _leggi(pratica, "ric")) if x]
    return max(c, key=lambda x: x["generata_il"]) if c else None


def _file_prodotto(pratica):
    u = ultima_preanalisi(pratica)
    return None if not u else FILE["pre" if u["tipo"] == "PREANALISI_PROVVISORIA" else "ric"]


def stato_approvazione(pratica):
    """None se mai approvata; altrimenti l'approvazione con 'valida' (False se il prodotto e' stato rigenerato dopo l'approvazione)."""
    a = _leggi(pratica, "appr")
    if not a:
        return None
    f = _p(pratica, "pre") if a["file"] == FILE["pre"] else _p(pratica, "ric")
    a = dict(a)
    a["valida"] = f.is_file() and _sha256_file(f) == a["sha256"] and a["file"] == _file_prodotto(pratica)
    return a


def approva_come_provvisoria(pratica, nome, genera_word=True):
    """Il titolare approva la relazione come PROVVISORIA (non e' un consolidamento: non richiede completezza ne' gate). Nome e data nel verbale."""
    try:
        chi = _nome(nome)
    except ErrorePratica:
        _verbale(pratica, "APPROVAZIONE PROVVISORIA", "RIFIUTATO", "nome del titolare mancante")
        raise
    f = _file_prodotto(pratica)
    if not f:
        _verbale(pratica, "APPROVAZIONE PROVVISORIA", "RIFIUTATO", "nessuna preanalisi da approvare")
        raise ErrorePratica("nessuna preanalisi provvisoria da approvare: avviarla prima")
    quando = _ora()
    appr = {"stato": APPROVATA, "approvata_da": chi, "approvata_il": quando, "file": f, "sha256": _sha256_file(Path(pratica) / f),
            "nota": "Approvazione come relazione PROVVISORIA: non è il consolidamento, che resta vincolato al gate."}
    if genera_word:
        d = ultima_preanalisi(pratica)
        appr["documento_word"] = genera_preanalisi_word(pratica, d, approvazione=appr).name
    _scrivi(pratica, "appr", appr)
    _verbale(pratica, "APPROVAZIONE PROVVISORIA", "OK", "%s: %s da %s il %s" % (f, APPROVATA, chi, quando))
    return appr


# ---------------------------------------------------------------- Word: Preanalisi provvisoria / Ricognizione del fascicolo
def _tt(v):
    s = "" if v is None else str(v)
    return s if s.strip() and s.strip().lower() not in ("none", "nan") else "-"


def genera_preanalisi_word(pratica, d, uscita=None, modello=None, approvazione=None):
    from analisi_crisi import word_xml as w
    ric = d["tipo"] == "RICOGNIZIONE_FASCICOLO"
    titolo = "Ricognizione del fascicolo" if ric else "Preanalisi provvisoria"
    P = [w.par(w.run(d["dicitura"], True, "365F91", 26), "Corpo", dopo=60)]
    if approvazione:
        P.append(w.par(w.run(approvazione["stato"] + " da " + approvazione["approvata_da"] + " il " + approvazione["approvata_il"] + ". Non è il consolidamento.", True, "7F6000", 21), "Corpo", dopo=60))
    P += [w.par(w.run(titolo, True, dim=30), "Corpo", dopo=40),
          w.testo("Pratica: %s. Elaborazione del %s. Tutti i giudizi sono %s e non costituiscono attestazione." % (d["pratica"], d["generata_il"], ETICHETTA_GIUDIZIO), dim=19, dopo=60)]

    def tab(intest, larg, righe, vuoto, colori=None):
        P.append(w.tabella([intest] + righe, larg, dim=16, colori=colori) if righe else w.testo(vuoto, dim=17))
    P.append(w.h1("1. Sintesi dei limiti informativi"))
    for l in d["limiti_informativi"] or ["Nessun limite informativo rilevante."]:
        P.append(w.punto(l))
    P.append(w.h1("2. Checklist documentale"))
    for g, tit in (("A", "A. Documenti di partenza"), ("B", "B. Approfondimenti suggeriti dall'analisi")):
        P.append(w.h2(tit))
        if g == "A":
            tab(["Voce", "Raccomandata", "Stato", "Se manca"], [2600, 1200, 1300, 4600],
                [[v["id"] + " " + v["etichetta"], "sì", v["stato"], _tt(v["fallback"])] for v in d["checklist"]["A"]], "")
        else:
            tab(["Voce", "Suggerita", "Stato", "Criticità che la suggerisce", "Scenari per cui è decisiva"], [2300, 900, 1200, 2800, 2500],
                [[v["id"] + " " + v["etichetta"], "sì" if v["suggerita"] else "no", v["stato"], _tt(v["criticita"]) if v["suggerita"] else "-", ", ".join(v["scenari_nomi"])] for v in d["checklist"]["B"]], "")
    P.append(w.h1("3. Dati estratti e fonti"))
    tab(["Dato", "Valore", "Unità", "Natura", "Fonte", "Pag."], [2600, 1500, 800, 1300, 2800, 700],
        [[x["dato"], _tt(x["valore"]), _tt(x["unita"]), x["natura"], _tt(x["fonte"]), _tt(x["pagina"])] for x in d["dati_estratti"]], "Nessun dato estratto: nessun valore è stato assunto o sostituito con zero.")
    P.append(w.h1("4. Criticità e incongruenze"))
    tab(["Tipo", "Descrizione", "Gravità", "Stato"], [1800, 5200, 1300, 1400],
        [[x["tipo"], x["testo"], _tt(x["gravita"]), x["stato"]] for x in d["criticita"]], "Nessuna criticità o incongruenza rilevata con i dati disponibili.")
    P.append(w.h1("5. Calcoli eseguibili"))
    calc = [s for s in d["sezioni"] if s["stato"] == "CALCOLABILE"]
    tab(["Calcolo", "Valore", "Nota"], [3200, 1300, 5200], [[s["sezione"], s["valore"], _tt(s["nota"])] for s in calc], "Nessun calcolo eseguibile con i dati disponibili.")
    P.append(w.h1("6. Giudizi preliminari motivati"))
    giu = d["giudizi_preliminari"]
    tab(["Giudizio", "Esito", "Motivazione", "Stato"], [2600, 1200, 4600, 1300], [[g["giudizio"], g["esito"], g["motivazione"], g["etichetta"]] for g in giu],
        "Nessun giudizio preliminare possibile: " + ND + ".", {(i + 1, 1): g["esito"] for i, g in enumerate(giu)})
    rq = d["riquadri"]
    ini, con = d["sufficienza"]["per_iniziare"], d["sufficienza"]["per_concludere"]
    P.append(w.h2("Indicatori di sufficienza (distinti)"))
    tab(["Indicatore", "Esito", "Dettaglio"], [2600, 1500, 5600],
        [["Sufficienza per INIZIARE", "SÌ", "Si può valutare: " + ("; ".join(ini["valutabile"]) or "solo la ricognizione del fascicolo") + ". Non si può valutare: " + ("; ".join(ini["non_valutabile"]) or "nulla di rilevante") + "."],
         ["Sufficienza per CONCLUDERE", "SÌ" if con["ok"] else "NO", "; ".join(con["motivi"]) or "Nessun ostacolo noto."]], "", {(1, 1): "VERDE", (2, 1): "VERDE" if con["ok"] else "GIALLO"})
    P.append(w.testo("Fattibilità: %s - %s. Qualità dei dati: %s. %s" % (rq["fattibilita"]["esito"], rq["fattibilita"]["dettaglio"], rq["qualita_dati"]["esito"], rq["stato_conclusione"]["esito"]), dim=18))
    P.append(w.h1("7. Sezioni non valutabili e scenari sospesi"))
    for x in d["scenari"]:
        P.append(w.punto("%s: %s. %s" % (x["scenario"], x["stato"], "; ".join(x["motivo"]))))
    for s in d["sezioni"]:
        if s["stato"] == "NON CALCOLABILE":
            P.append(w.punto("%s: %s." % (s["sezione"], ND)))
    P.append(w.h1("8. Richieste documentali prioritarie (massimo 5)"))
    tab(["#", "Richiesta", "Perché", "Che cosa permetterà di verificare"], [400, 3300, 2900, 3100],
        [[r["ordine"], r["richiesta"], r["perche"], r["permette_di_verificare"]] for r in d["richieste_prioritarie"]], "Nessuna richiesta prioritaria.")
    P.append(w.h1("9. Versione del motore"))
    P.append(w.testo("Versione del motore: %s - impronta dei parametri: %s" % (d["versione_motore"], d["impronta"]), dim=16))
    cart = Path(pratica)
    base = ("Ricognizione_fascicolo" if ric else "Preanalisi_provvisoria") + ("_APPROVATA_PROVVISORIA" if approvazione else "")
    out = Path(uscita) if uscita else cart / ("%s_%s.docx" % (base, time.strftime("%Y%m%d-%H%M%S")))
    n = 1
    while out.exists():
        out = out.with_name("%s_v%d%s" % (out.stem.split("_v")[0], n, out.suffix))
        n += 1
    w.salva(modello or MODELLO, "".join(P), out, a4=True)
    return out


def imposta_stato_voce(pratica, voce_id, nuovo_stato, nome, nota=""):
    """Aggiorna lo stato di una voce della checklist (A/B) e lo registra nel verbale. Mai bloccante per il resto della pratica."""
    try:
        r = ck.imposta_stato(pratica, voce_id, nuovo_stato, nome, nota)
    except ck.ErroreChecklist as e:
        _verbale(pratica, "CHECKLIST", "RIFIUTATO", "%s -> %s: %s" % (voce_id, nuovo_stato, e))
        raise ErrorePratica(str(e))
    _verbale(pratica, "CHECKLIST", "OK", "voce %s -> %s da %s" % (voce_id, nuovo_stato, r["da"]))
    return r
