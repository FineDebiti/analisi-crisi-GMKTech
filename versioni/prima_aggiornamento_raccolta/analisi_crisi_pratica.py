"""Pratica: registro documentale, gate di verifica dei numeri, versione del motore, parametri usati, verbale a catena di hash.

Una pratica e' una cartella con: pratica.json, registro_documentale.json, dati_estratti.json, incongruenze.json,
richieste_prioritarie.json, numeri_decisivi.json, verbale.json (solo append, hash a catena), parametri_usati.json,
valutazione_v3.json (scritta solo a gate superato). Supporto alla decisione, non attestazione.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from datetime import datetime
from pathlib import Path

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
        "param": "parametri_usati.json", "val": "valutazione_v3.json"}
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
