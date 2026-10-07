"""Livello OPZIONALE del modello locale (es. Qwen su GMKtec) - HG-3 richiesto dal titolare per l'esperimento A/B.

Principi (Costituzione Agentica):
- il modello PROPONE; il codice VERIFICA (citazione alla lettera sulla pagina indicata, numero presente nella citazione, campo noto);
- nessun calcolo, soglia, parametro o semaforo passa dal modello: restano nel motore deterministico;
- ogni valore applicato nasce "DA VERIFICARE", origine "Proposto dal modello locale", e resta tale finche' il titolare non lo conferma;
- tutto e' LOCALE: l'endpoint deve essere loopback (127.0.0.1 / localhost / ::1); un endpoint diverso e' rifiutato;
- la PRIMA risposta del modello e' conservata integra (llm/run_*.json) e non viene mai riscritta.
Se llm_config.json non esiste o ha "abilitato": false, l'applicazione funziona esattamente come sul Mac (nessuna chiamata).
"""
from __future__ import annotations

import hashlib
import json
import re
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

from analisi_crisi import dati_pratica as dp
from analisi_crisi import pratica as pr
from analisi_crisi import versione

QUI = Path(__file__).resolve().parent
RADICE = QUI.parent
CARTELLA_PROTOCOLLO = RADICE / "protocollo_qwen"
FILE_CONFIG = RADICE / "llm_config.json"
HOST_LOCALI = {"127.0.0.1", "localhost", "::1", "[::1]"}
CONFIG_DEFAULT = {
    "abilitato": False,
    "endpoint": "http://127.0.0.1:8080/v1",     # llama.cpp server; Ollama: http://127.0.0.1:11434/v1; LM Studio: http://127.0.0.1:1234/v1
    "modello": "",                               # id esatto riportato dal runtime (vedi verifica_ambiente)
    "etichetta_modello": "",                     # nome per le schede (es. come indicato dal titolare); NON sostituisce l'id reale
    "quantizzazione": "",                        # dichiarata da chi configura (es. Q4_K_M); il runtime puo' non esporla
    "contesto_configurato": None,                # n_ctx impostato nel runtime
    "temperatura": 0.0,
    "seed": 7,
    "max_token": 6000,
    "timeout_s": 3600,
    "formato_json": True,
}
NATURE_LLM = ("FATTO", "DICHIARAZIONE", "CALCOLO", "INFERENZA", "IPOTESI")


class ErroreLLM(Exception):
    pass


# ---------------------------------------------------------------- configurazione
def leggi_config(percorso=None):
    c = dict(CONFIG_DEFAULT)
    p = Path(percorso) if percorso else FILE_CONFIG
    try:
        c.update(json.loads(p.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        pass
    return c


def endpoint_locale(url):
    """Rifiuta ogni endpoint non loopback: documenti e prompt non devono uscire dalla macchina."""
    h = (urlparse(url).hostname or "").lower()
    if h not in {x.strip("[]") for x in HOST_LOCALI}:
        raise ErroreLLM("Endpoint non locale (%s): rifiutato. Documenti e prompt devono restare su questa macchina." % (h or url))
    return url.rstrip("/")


# ---------------------------------------------------------------- testo dei documenti (con pagina)
def pagine_documento(percorso):
    """[{'pagina','testo','origine'}]. Testo nativo se presente; altrimenti OCR locale (tesseract) con origine 'OCR'. Mai OCR remoto."""
    import pdfplumber
    out, vuote = [], []
    with pdfplumber.open(str(percorso)) as d:
        for i, pg in enumerate(d.pages, 1):
            t = (pg.extract_text() or "").strip()
            if len(t) < 20:
                vuote.append(i)
            out.append({"pagina": i, "testo": t, "origine": "testo"})
    if vuote:
        try:
            from analisi_crisi import ocr
            for n, t in ocr.testo_pagine(percorso, vuote):
                out[n - 1] = {"pagina": n, "testo": t.strip(), "origine": "OCR"}
        except Exception as e:   # OCR non disponibile: la pagina resta vuota e lo si dichiara
            for n in vuote:
                out[n - 1]["avviso"] = "pagina senza testo; OCR non disponibile (%s)" % str(e)[:80]
    return out


def documenti_pratica(pc, cart):
    """Documenti del registro con file presente: [{'id','nome','tipo','periodo','pagine':[...]}]."""
    res = []
    base = Path(cart).resolve()
    for r in pr._leggi(pc, "registro", []):
        if not r.get("sha256"):
            continue
        f = (base / r["nome"]).resolve()
        if base not in f.parents or not f.is_file() or f.suffix.lower() != ".pdf":
            continue
        res.append({"id": r["id"], "nome": r["nome"], "tipo": r.get("tipo"), "periodo": r.get("periodo_economico"), "pagine": pagine_documento(f)})
    return res


def testo_documenti(docs):
    righe = []
    for d in docs:
        for p in d["pagine"]:
            righe.append("[[DOC %s %s | PAG %s | %s]]\n%s" % (d["id"], d["nome"], p["pagina"], p["origine"], p["testo"] or "(pagina senza testo leggibile)"))
    return "\n\n".join(righe)


# ---------------------------------------------------------------- prompt
def _leggi(nome):
    return (CARTELLA_PROTOCOLLO / nome).read_text(encoding="utf-8")


def testo_campi():
    return "\n".join("- `%s` = %s [%s]. %s" % (c["codice"], c["etichetta"], c["unita"] or "si/no", c["aiuto"]) for c in dp.CAMPI_LISTA if c["tipo"] == "num")


def messaggio_sistema():
    """Istruzioni + schema + fonti + esempio sintetico + parametri del motore (SOLA LETTURA). Identico per ogni arm e per ogni prova."""
    es = json.loads(_leggi("ESEMPI.json"))
    esempio = ("### ESEMPIO SINTETICO (non e' la pratica)\n%s\n\nDocumenti dell'esempio:\n%s\n\nRisposta corretta dell'esempio:\n%s" % (
        es["avvertenza"], testo_documenti([{"id": d["id"], "nome": d["nome"], "pagine": [dict(p, origine="testo") for p in d["pagine"]]} for d in es["documenti"]]),
        json.dumps(es["risposta_attesa"], ensure_ascii=False, indent=1)))
    return "\n\n".join([
        _leggi("SISTEMA.md"),
        "## CAMPI NUMERICI ESTRAIBILI (codici ammessi)\n" + testo_campi(),
        "## SCHEMA DELLA RISPOSTA (SCHEMA.json)\n" + _leggi("SCHEMA.json"),
        "## FONTI NORMATIVE VERIFICATE (FONTI.md)\n" + _leggi("FONTI.md"),
        "## PARAMETRI DEL MOTORE (SOLA LETTURA - non modificabili da te)\nVersione: %s - %s\n%s" % (
            versione.MOTORE, versione.REVISIONE, json.dumps(versione.parametri(), ensure_ascii=False, indent=1)),
        esempio])


def messaggio_utente_B(docs):
    """Prova B - percorso completo: dai PDF originali."""
    return ("PROVA B - PERCORSO COMPLETO. Leggi i documenti qui sotto ed estrai i dati, segnala mancanti, incongruenze, duplicazioni, normalizzazioni, "
            "scenari e richieste prioritarie secondo le istruzioni. Nessun dato e' stato verificato dal titolare.\n\n" + testo_documenti(docs))


def messaggio_utente_A(dati_verificati, calcoli, checklist, docs_indice):
    """Prova A - analisi su dati gia' verificati dal titolare (nessuna estrazione: 'dati' resta vuoto)."""
    return ("PROVA A - ANALISI SU DATI VERIFICATI. I dati sotto sono stati verificati dal titolare (`confermato_dal_titolare`): non vanno rimessi in discussione. "
            "Non estrarre dati: lascia `dati` vuoto. Usa i calcoli del codice cosi' come sono. Produci normalizzazioni, incongruenze, duplicazioni, scenari, richieste prioritarie e note.\n\n"
            "### DATI VERIFICATI\n%s\n\n### CALCOLI DEL CODICE (non rifare)\n%s\n\n### STATO DEI DOCUMENTI (checklist, dal titolare/registro)\n%s\n\n### DOCUMENTI IN FASCICOLO\n%s" % (
                json.dumps(dati_verificati, ensure_ascii=False, indent=1), json.dumps(calcoli, ensure_ascii=False, indent=1),
                json.dumps(checklist, ensure_ascii=False, indent=1), json.dumps(docs_indice, ensure_ascii=False, indent=1)))


def impronta_prompt(messaggi):
    return hashlib.sha256(json.dumps(messaggi, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


# ---------------------------------------------------------------- chiamata locale
def _http(url, dati=None, timeout=60):
    rich = urllib.request.Request(url, data=(json.dumps(dati).encode("utf-8") if dati is not None else None),
                                  headers={"Content-Type": "application/json"}, method="POST" if dati is not None else "GET")
    with urllib.request.urlopen(rich, timeout=timeout) as r:   # nessun proxy esterno: endpoint loopback verificato prima
        return json.loads(r.read().decode("utf-8"))


def info_modello(cfg):
    """Id e metadati del modello come li riporta il runtime locale (non quelli dichiarati)."""
    base = endpoint_locale(cfg["endpoint"])
    try:
        m = _http(base + "/models", timeout=15)
        return {"modelli_riportati": [x.get("id") for x in m.get("data", [])], "grezzo": m}
    except (urllib.error.URLError, OSError, ValueError) as e:
        return {"errore": str(e)[:160]}


def chiama(cfg, messaggi):
    """POST /chat/completions sull'endpoint locale. Ritorna (testo_grezzo, meta). Temperatura e seed dalla configurazione (riproducibilita')."""
    base = endpoint_locale(cfg["endpoint"])
    corpo = {"model": cfg.get("modello") or "", "messages": messaggi, "temperature": cfg["temperatura"], "seed": cfg["seed"], "max_tokens": cfg["max_token"], "stream": False}
    if cfg.get("formato_json"):
        corpo["response_format"] = {"type": "json_object"}
    t0 = time.monotonic()
    try:
        r = _http(base + "/chat/completions", corpo, timeout=cfg["timeout_s"])
    except (urllib.error.URLError, OSError, ValueError) as e:
        raise ErroreLLM("Modello locale non raggiungibile su %s: %s" % (base, str(e)[:160]))
    dt = round(time.monotonic() - t0, 2)
    try:
        testo = r["choices"][0]["message"]["content"] or ""
    except (KeyError, IndexError, TypeError):
        raise ErroreLLM("Risposta del modello in formato inatteso.")
    return testo, {"secondi": dt, "uso_token": r.get("usage"), "modello_risposta": r.get("model"), "id_risposta": r.get("id")}


def estrai_json(testo):
    """Isola l'oggetto JSON (anche dopo blocchi <think> o recinti ```). Solleva ErroreLLM se non valido: la risposta grezza resta comunque conservata."""
    t = re.sub(r"<think>.*?</think>", "", testo or "", flags=re.S).strip()
    t = re.sub(r"^```(?:json)?|```$", "", t.strip(), flags=re.M).strip()
    i, j = t.find("{"), t.rfind("}")
    if i < 0 or j < i:
        raise ErroreLLM("La risposta non contiene un oggetto JSON.")
    try:
        o = json.loads(t[i:j + 1])
    except ValueError as e:
        raise ErroreLLM("JSON non valido: %s" % str(e)[:100])
    if not isinstance(o, dict):
        raise ErroreLLM("La risposta JSON non e' un oggetto.")
    return o


# ---------------------------------------------------------------- verifica deterministica delle proposte
_NUM = re.compile(r"\(?-?\d{1,3}(?:\.\d{3})+(?:,\d+)?\)?|\(?-?\d+(?:,\d+)?\)?")


def _norm(s):
    return re.sub(r"\s+", " ", str(s or "")).strip().lower()


def numeri_in_testo(t):
    """Valori numerici (con segno) presenti in un testo italiano: '(2.500)' -> -2500."""
    out = []
    for m in _NUM.finditer(t or ""):
        tok = m.group(0)
        neg = tok.startswith("(") or tok.startswith("-")
        core = tok.strip("()-")
        try:
            v = dp.parse_numero(core)
        except dp.ErroreDati:
            continue
        if v is None:
            continue
        out.append(-abs(v) if neg else v)
    return out


def verifica_proposta(p, pagine):
    """Esito per un dato proposto: RISCONTRATO / NON RISCONTRATO con motivo. pagine = {id_doc: {n: testo}}."""
    cod = p.get("campo")
    if cod not in dp.CAMPO or dp.CAMPO[cod]["tipo"] != "num":
        return "NON RISCONTRATO", "campo non ammesso (%s)" % cod
    if p.get("valore") is None:
        return "MANCANTE", "valore non trovato (resta non disponibile, mai zero)"
    if isinstance(p["valore"], bool) or not isinstance(p["valore"], (int, float)):
        return "NON RISCONTRATO", "valore non numerico"
    try:
        doc, pag = int(p.get("documento")), int(p.get("pagina"))
    except (TypeError, ValueError):
        return "NON RISCONTRATO", "documento o pagina mancanti"
    testo = (pagine.get(doc) or {}).get(pag)
    if testo is None:
        return "NON RISCONTRATO", "documento %s pagina %s inesistente" % (doc, pag)
    cit = _norm(p.get("citazione"))
    if not cit or cit not in _norm(testo):
        return "NON RISCONTRATO", "la citazione non e' presente alla lettera nella pagina indicata"
    ok = any(abs(v) == abs(p["valore"]) and (v < 0) == (p["valore"] < 0) for v in numeri_in_testo(p["citazione"]))
    if not ok:
        return "NON RISCONTRATO", "il valore %s non coincide con alcun numero (col segno) della citazione" % p["valore"]
    anno = re.sub(r"\D", "", str(p.get("periodo") or ""))[:4]
    if anno and anno not in testo:
        return "RISCONTRATO", "ATTENZIONE: il periodo dichiarato (%s) non compare nella pagina" % p.get("periodo")
    return "RISCONTRATO", ""


def verifica_risposta(risposta, docs):
    """Aggiunge a ogni dato esito/motivo e individua conflitti. Non modifica i valori proposti."""
    pagine = {d["id"]: {p["pagina"]: p["testo"] for p in d["pagine"]} for d in docs}
    righe, visti = [], {}
    for p in risposta.get("dati") or []:
        if not isinstance(p, dict):
            continue
        esito, motivo = verifica_proposta(p, pagine)
        riga = dict(p, esito=esito, motivo=motivo)
        chiave = (p.get("campo"), str(p.get("periodo") or "")[:4])
        if esito == "RISCONTRATO":
            if chiave in visti and visti[chiave] != p["valore"]:
                riga["esito"], riga["motivo"] = "CONFLITTO", "stesso campo e periodo con valore diverso (%s)" % visti[chiave]
            elif chiave in visti:
                riga["esito"], riga["motivo"] = "DUPLICATO", "stesso campo, periodo e valore gia' proposti"
            else:
                visti[chiave] = p["valore"]
        righe.append(riga)
    return righe


# ---------------------------------------------------------------- esecuzione e applicazione
def cartella_run(pc):
    d = Path(pc) / "llm"
    d.mkdir(exist_ok=True)
    return d


def esegui_estrazione(pc, cart, chi, cfg=None, chiama_fn=None):
    """Prova B sulla pratica: legge i PDF del registro, interroga il modello locale, verifica, salva run integro e proposte. Ritorna il run."""
    cfg = cfg or leggi_config()
    if not cfg.get("abilitato"):
        raise ErroreLLM("Modello locale non abilitato (llm_config.json: \"abilitato\": true).")
    docs = documenti_pratica(pc, cart)
    if not docs:
        raise ErroreLLM("Nessun PDF nel registro da leggere: carica prima i documenti.")
    messaggi = [{"role": "system", "content": messaggio_sistema()}, {"role": "user", "content": messaggio_utente_B(docs)}]
    ts = time.strftime("%Y%m%d-%H%M%S")
    run = {"id": ts, "prova": "B", "avviato_da": chi, "il": pr._ora(), "motore": versione.MOTORE, "revisione_motore": versione.REVISIONE, "impronta_motore": versione.impronta(),
           "config": {k: cfg.get(k) for k in ("endpoint", "modello", "etichetta_modello", "quantizzazione", "contesto_configurato", "temperatura", "seed", "max_token")},
           "runtime": info_modello(cfg), "impronta_prompt": impronta_prompt(messaggi), "documenti": [{"id": d["id"], "nome": d["nome"], "pagine": len(d["pagine"]),
           "origine_testo": sorted({p["origine"] for p in d["pagine"]})} for d in docs]}
    try:
        grezzo, meta = (chiama_fn or chiama)(cfg, messaggi)
    except ErroreLLM as e:
        run["errore"] = str(e)
        (cartella_run(pc) / ("run_%s.json" % ts)).write_text(json.dumps(run, ensure_ascii=False, indent=1), encoding="utf-8")
        pr._verbale(pc, "MODELLO LOCALE", "KO", "estrazione non riuscita: %s" % e)
        raise
    run["meta"], run["risposta_grezza"] = meta, grezzo      # PRIMA risposta, mai modificata
    try:
        risposta = estrai_json(grezzo)
        run["json_valido"] = True
        run["proposte"] = verifica_risposta(risposta, docs)
        run["risposta"] = {k: v for k, v in risposta.items() if k != "dati"}
    except ErroreLLM as e:
        run["json_valido"], run["errore_json"], run["proposte"], run["risposta"] = False, str(e), [], {}
    (cartella_run(pc) / ("run_%s.json" % ts)).write_text(json.dumps(run, ensure_ascii=False, indent=1), encoding="utf-8")
    (Path(pc) / "proposte_llm.json").write_text(json.dumps(run, ensure_ascii=False, indent=1), encoding="utf-8")
    pr._verbale(pc, "MODELLO LOCALE", "OK" if run["json_valido"] else "KO",
                "estrazione %s: modello %s, %.1f s, %d proposte (%d riscontrate)" % (ts, run["runtime"].get("modelli_riportati") or cfg.get("modello") or "n.d.", meta["secondi"],
                                                                                   len(run["proposte"]), sum(1 for x in run["proposte"] if x["esito"] == "RISCONTRATO")))
    return run


def ultimo_run(pc):
    try:
        return json.loads((Path(pc) / "proposte_llm.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def applica_proposte(pc, indici, chi):
    """Applica ai dati della pratica le proposte RISCONTRATE scelte dall'operatore. Stato sempre DA VERIFICARE, origine 'Proposto dal modello locale'.
    Non sovrascrive un valore diverso gia' presente (lo segnala). Ritorna (applicati, saltati)."""
    run = ultimo_run(pc)
    if not run:
        raise dp.ErroreDati("Nessuna estrazione del modello da applicare.")
    cor = dp.valori(pc)
    righe, saltati = {}, []
    for i in indici:
        if i < 0 or i >= len(run["proposte"]):
            continue
        p = run["proposte"][i]
        if p["esito"] != "RISCONTRATO":
            saltati.append("%s: %s" % (p.get("campo"), p["esito"]))
            continue
        if cor.get(p["campo"]) is not None and cor[p["campo"]] != p["valore"]:
            saltati.append("%s: esiste gia' un valore diverso (%s): correggi a mano se serve" % (p["campo"], dp.fmt_it(cor[p["campo"]])))
            continue
        if cor.get(p["campo"]) == p["valore"]:
            continue
        righe[p["campo"]] = {"valore": dp.fmt_modifica(p["valore"]), "id_documento": str(p["documento"]), "pagina": str(p["pagina"]), "stato": "DA VERIFICARE",
                             "note": ("Proposto dal modello locale (run %s). Citazione: %s" % (run["id"], p.get("citazione") or ""))[:300], "origine": "LLM"}
    mod = dp.salva_valori(pc, righe, chi) if righe else []
    pr._verbale(pc, "MODELLO LOCALE", "OK", "applicate %d proposte del run %s da %s; saltate %d" % (len(mod), run["id"], chi, len(saltati)))
    return mod, saltati
