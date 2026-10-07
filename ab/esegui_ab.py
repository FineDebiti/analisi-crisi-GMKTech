#!/usr/bin/env python3
"""Esperimento A/B Claude vs Qwen locale - strumenti (tutto LOCALE, nessuna chiamata esterna).

Sottocomandi:
  bundle      costruisce il fascicolo IDENTICO per i due sistemi (prova A o B) con impronte e versione del motore
  qwen        esegue il modello locale sul bundle; salva la PRIMA risposta integra (non sovrascrivibile)
  claude      stampa le istruzioni per far eseguire lo stesso bundle a Claude
  registra    registra la risposta grezza di un sistema eseguito altrove (es. Claude) con tempo e configurazione
  valuta      valutazione deterministica di una risposta (errori numerici, di fonte, omissioni, duplicazioni, scenari)
  scheda      produce la scheda A/B CIECA per il titolare (etichette A/B casuali; chiave in file separato)
Regola: nessun sistema vede l'output dell'altro; le risposte non vengono mai corrette: la prima resta agli atti.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
import sys
import time
from pathlib import Path

QUI = Path(__file__).resolve().parent
sys.path.insert(0, str(QUI.parent))
from analisi_crisi import checklist as ck  # noqa: E402
from analisi_crisi import dati_pratica as dp  # noqa: E402
from analisi_crisi import llm_locale as ll  # noqa: E402
from analisi_crisi import pratica as pr  # noqa: E402
from analisi_crisi import semaforo_v3, versione  # noqa: E402


def _scrivi_nuovo(p: Path, contenuto: str):
    if p.exists():
        sys.exit("RIFIUTO: %s esiste già. Le risposte e i bundle non si sovrascrivono (la prima resta agli atti)." % p)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(contenuto, encoding="utf-8")


def _sha(t):
    return hashlib.sha256(t.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------- bundle
def cmd_bundle(a):
    cart = Path(a.cartella).resolve()
    pc = cart / "PRATICA"
    if not (pc / pr.FILE["pratica"]).is_file():
        sys.exit("Cartella senza PRATICA: crea la pratica dall'interfaccia e carica i PDF.")
    out = Path(a.out)
    docs = ll.documenti_pratica(pc, cart)
    sistema = ll.messaggio_sistema()
    if a.prova == "B":
        utente = ll.messaggio_utente_B(docs)
    else:
        campi = dp.carica(pc)["campi"]
        reg = {r["id"]: r["nome"] for r in pr._leggi(pc, "registro", [])}
        verificati = [{"campo": k, "etichetta": dp.CAMPO[k]["etichetta"], "valore": r["valore"], "unita": r.get("unita"), "documento": r.get("id_documento"), "nome_documento": reg.get(r.get("id_documento")),
                       "pagina": r.get("pagina"), "periodo": r.get("esercizio"), "confermato_dal_titolare": True}
                      for k, r in campi.items() if r.get("valore") is not None and r.get("stato") == "FATTO" and k in dp.CAMPO]
        m = dp.calcola_metriche(dp.valori(pc))[0]
        sost = semaforo_v3.sostenibilita(m)
        calcoli = {"calcoli_leggibili": [{"calcolo": x, "risultato": y, "nota": z} for x, y, z in dp.calcola_metriche(dp.valori(pc))[1]],
                   "criteri_del_motore": [{"criterio": c["nome"], "valore": c["valore"], "esito": c["colore"]} for c in sost["criteri"]], "allerta_complessiva": sost["colore"]}
        lista = ck.stato_checklist(pc, m)
        check = [{"id": v["id"], "voce": v["etichetta"], "stato": v["stato"], "scenari": v["scenari_nomi"], "suggerita": v["suggerita"]} for g in ("A", "B") for v in lista[g]]
        idx = [{"id": d["id"], "nome": d["nome"], "tipo": d["tipo"], "pagine": len(d["pagine"])} for d in docs]
        utente = ll.messaggio_utente_A(verificati, calcoli, check, idx)
    messaggi = [{"role": "system", "content": sistema}, {"role": "user", "content": utente}]
    meta = {"prova": a.prova, "creato_il": pr._ora(), "motore": versione.MOTORE, "revisione": versione.REVISIONE, "impronta_motore": versione.impronta(), "parametri": versione.parametri(),
            "impronta_sistema": _sha(sistema), "impronta_utente": _sha(utente), "impronta_messaggi": ll.impronta_prompt(messaggi),
            "documenti": [{"id": d["id"], "nome": d["nome"], "pagine": len(d["pagine"]), "origine_testo": sorted({p["origine"] for p in d["pagine"]})} for d in docs]}
    _scrivi_nuovo(out / "sistema.txt", sistema)
    _scrivi_nuovo(out / "utente.txt", utente)
    _scrivi_nuovo(out / "messaggi.json", json.dumps(messaggi, ensure_ascii=False, indent=1))
    _scrivi_nuovo(out / "documenti.json", json.dumps(docs, ensure_ascii=False))
    _scrivi_nuovo(out / "bundle_meta.json", json.dumps(meta, ensure_ascii=False, indent=1))
    print("Bundle prova %s creato in %s (impronta messaggi %s)" % (a.prova, out, meta["impronta_messaggi"][:16]))


def _carica(b):
    b = Path(b)
    return json.loads((b / "bundle_meta.json").read_text(encoding="utf-8")), json.loads((b / "messaggi.json").read_text(encoding="utf-8"))


# ---------------------------------------------------------------- esecuzione
def _salva_arm(b, arm, grezzo, meta_run):
    d = Path(b) / ("arm_" + arm)
    _scrivi_nuovo(d / "risposta_grezza.txt", grezzo)
    _scrivi_nuovo(d / "run.json", json.dumps(meta_run, ensure_ascii=False, indent=1))
    print("Registrata la PRIMA risposta di '%s' in %s" % (arm, d))


def cmd_qwen(a):
    cfg = ll.leggi_config()
    if not cfg.get("abilitato"):
        sys.exit("Modello locale non abilitato in llm_config.json.")
    meta, messaggi = _carica(a.bundle)
    info = ll.info_modello(cfg)
    try:
        grezzo, mr = ll.chiama(cfg, messaggi)
    except ll.ErroreLLM as e:
        sys.exit(str(e))
    run = {"arm": "qwen", "eseguito_il": pr._ora(), "config": {k: cfg.get(k) for k in ("endpoint", "modello", "etichetta_modello", "quantizzazione", "contesto_configurato", "temperatura", "seed", "max_token")},
           "runtime": info, "meta": mr, "impronta_messaggi": meta["impronta_messaggi"], "impronta_motore": meta["impronta_motore"]}
    _salva_arm(a.bundle, "qwen", grezzo, run)


def cmd_claude(a):
    meta, _ = _carica(a.bundle)
    print("Per l'arm CLAUDE fornisci a Claude SOLO i file di %s:\n  sistema.txt (istruzioni di sistema)  +  utente.txt (messaggio utente)\n"
          "senza altri contesti, senza l'output di Qwen, in una conversazione nuova, senza strumenti. Salva la PRIMA risposta così com'è in un file di testo e registrala con:\n"
          "  python3 ab/esegui_ab.py registra --bundle %s --arm claude --risposta FILE --secondi N --modello \"id esatto\" --configurazione \"descrizione\"\n"
          "Impronta messaggi di riferimento: %s" % (a.bundle, a.bundle, meta["impronta_messaggi"]))


def cmd_registra(a):
    meta, _ = _carica(a.bundle)
    grezzo = Path(a.risposta).read_text(encoding="utf-8")
    run = {"arm": a.arm, "eseguito_il": pr._ora(), "config": {"modello": a.modello, "configurazione": a.configurazione}, "meta": {"secondi": a.secondi, "registrata_da_file": Path(a.risposta).name},
           "impronta_messaggi": meta["impronta_messaggi"], "impronta_motore": meta["impronta_motore"]}
    _salva_arm(a.bundle, a.arm, grezzo, run)


# ---------------------------------------------------------------- valutazione
def _uguali(a, b):
    return a is not None and b is not None and abs(float(a) - float(b)) < 0.005


def valuta_arm(bundle, arm, verita):
    b = Path(bundle)
    meta = json.loads((b / "bundle_meta.json").read_text(encoding="utf-8"))
    run = json.loads((b / ("arm_" + arm) / "run.json").read_text(encoding="utf-8"))
    grezzo = (b / ("arm_" + arm) / "risposta_grezza.txt").read_text(encoding="utf-8")
    docs = json.loads((b / "documenti.json").read_text(encoding="utf-8"))
    r = {"arm": arm, "prova": meta["prova"], "impronta_messaggi_ok": run["impronta_messaggi"] == meta["impronta_messaggi"], "secondi": (run.get("meta") or {}).get("secondi"),
         "token": (run.get("meta") or {}).get("uso_token"), "modello": (run.get("config") or {}).get("modello"), "errori": [], "avvisi": []}
    try:
        ris = ll.estrai_json(grezzo)
        r["json_valido"] = True
    except ll.ErroreLLM as e:
        r.update(json_valido=False)
        r["errori"].append("JSON non valido: %s" % e)
        return r
    dati = [d for d in ris.get("dati") or [] if isinstance(d, dict)]
    verif = ll.verifica_risposta({"dati": dati}, docs)
    tv = {(x["campo"]): x for x in verita.get("dati", [])}
    manc_v = set(verita.get("mancanti", []))
    if meta["prova"] == "A":
        r["violazioni"] = ["'dati' non vuoto nella prova A (estrazione non richiesta)"] if dati else []
    ok_val = err_num = err_fonte = err_per = 0
    trovati, dettaglio = set(), []
    for v in verif:
        c = v.get("campo")
        if c in manc_v and v.get("valore") not in (None, ""):
            r["errori"].append("valore al posto di 'non trovato' (%s=%s)%s" % (c, v.get("valore"), " - ZERO" if v.get("valore") == 0 else ""))
            continue
        if c in tv:
            t = tv[c]
            if v["esito"] in ("RISCONTRATO", "DUPLICATO", "CONFLITTO") or v["esito"] == "NON RISCONTRATO":
                if _uguali(v.get("valore"), t["valore"]):
                    ok_val += 1
                    trovati.add(c)
                else:
                    err_num += 1
                    dettaglio.append("%s: letto %s, atteso %s" % (c, v.get("valore"), t["valore"]))
                if v["esito"] == "NON RISCONTRATO" or str(v.get("documento")) != str(t["documento"]) or str(v.get("pagina")) != str(t["pagina"]):
                    err_fonte += 1
                    dettaglio.append("%s: fonte non corretta (%s)" % (c, v.get("motivo") or "doc/pagina diversi dall'atteso"))
                if str(t.get("periodo", ""))[:4] not in str(v.get("periodo", "")):
                    err_per += 1
    chiavi = [(d.get("campo"), str(d.get("periodo"))[:4]) for d in dati if d.get("valore") is not None]
    r["dati"] = {"attesi": len(tv), "corretti": ok_val, "errori_numerici": err_num, "errori_di_fonte": err_fonte, "errori_di_periodo": err_per,
                 "omessi": sorted(set(tv) - trovati), "duplicati_nel_risultato": len(chiavi) - len(set(chiavi)), "non_riscontrati_dal_codice": sum(1 for v in verif if v["esito"] == "NON RISCONTRATO"),
                 "valori_su_dati_che_dovevano_mancare": sum(1 for v in verif if v.get("campo") in manc_v and v.get("valore") not in (None, "")), "dettaglio": dettaglio}
    ma = set(ris.get("dati_mancanti") or [])
    r["mancanti"] = {"attesi": sorted(manc_v), "segnalati_correttamente": sorted(manc_v & ma), "non_segnalati": sorted(manc_v - ma - {v.get("campo") for v in dati if v.get("valore") is None})}
    inc = [x for x in ris.get("incongruenze") or [] if isinstance(x, dict)]
    r["incongruenze"] = {"proposte": len(inc), "attese": len(verita.get("incongruenze_attese", [])), "possibili_falsi_positivi": max(0, len(inc) - len(verita.get("incongruenze_attese", []))),
                         "elenco": [x.get("descrizione") for x in inc]}
    r["normalizzazioni"] = [x.get("descrizione") for x in ris.get("normalizzazioni") or [] if isinstance(x, dict)]
    sc_v = verita.get("scenari_motore", {})
    sc = {x.get("scenario"): x.get("stato") for x in ris.get("scenari") or [] if isinstance(x, dict)}
    r["scenari"] = {"concordanti_con_il_motore": sum(1 for k, v in sc_v.items() if sc.get(k) == v), "attesi": len(sc_v), "discordanti": {k: {"modello": sc.get(k), "motore": v} for k, v in sc_v.items() if sc.get(k) != v}}
    if meta["prova"] == "B":
        r["scenari"]["nota"] = "Nella prova B il modello non conosce gli stati documentali (inesistente/mancante) usati dal motore: la concordanza non e' confrontabile, valuta la sola coerenza dei motivi."
    rich = [x for x in ris.get("richieste_prioritarie") or [] if isinstance(x, dict)]
    testo = " ".join(str(x.get("richiesta", "")) + " " + str(x.get("perche", "")) for x in rich).lower()
    util = [k for k, kw in verita.get("richieste_utili", {}).items() if any(w in testo for w in kw)]
    r["richieste"] = {"numero": len(rich), "oltre_il_massimo_di_5": max(0, len(rich) - 5), "utili_attese_coperte": util, "utili_attese_non_coperte": sorted(set(verita.get("richieste_utili", {})) - set(util))}
    vietate = [k for k in ris if k.lower() in ("soglie", "parametri", "protocollo", "semaforo", "soglie_modificate")]
    r["rispetto_dei_limiti"] = {"chiavi_su_soglie_o_semafori": vietate, "citazioni_normative_fuori_elenco": bool(re.search(r"\b(art\.?\s*\d+|d\.?lgs\.?|ccii|cassazione|sentenza)\b", json.dumps(ris, ensure_ascii=False), re.I))}
    r["note_per_il_titolare"] = ris.get("note_per_il_titolare")
    return r


def cmd_valuta(a):
    verita = json.loads(Path(a.verita).read_text(encoding="utf-8"))
    res = {}
    for arm in a.arm:
        res[arm] = valuta_arm(a.bundle, arm, verita)
    p = Path(a.bundle) / "valutazione_automatica.json"
    _scrivi_nuovo(p, json.dumps(res, ensure_ascii=False, indent=1)) if not p.exists() else p.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(res, ensure_ascii=False, indent=1))


# ---------------------------------------------------------------- scheda cieca
RUBRICA = [("Fedeltà alle fonti (citazioni e pagine esatte)", "0-3"), ("Correttezza numerica", "0-3"), ("Gestione dei dati mancanti (nessuno zero)", "0-3"),
           ("Qualità delle normalizzazioni (motivate, non applicate)", "0-3"), ("Incongruenze: pertinenti e dimostrate", "0-3"), ("Scenari e giudizi: coerenza con evidenze e motore", "0-3"),
           ("Utilità delle richieste prioritarie", "0-3"), ("Rispetto di mandato, soglie e revisione del titolare", "0-3")]


def _riassunto(v):
    if not v.get("json_valido"):
        return ["- JSON NON VALIDO: " + "; ".join(v["errori"])]
    d = v["dati"]
    return ["- Dati attesi: %d; corretti: %d; errori numerici: %d; errori di fonte: %d; errori di periodo: %d" % (d["attesi"], d["corretti"], d["errori_numerici"], d["errori_di_fonte"], d["errori_di_periodo"]),
            "- Omessi: %s; duplicati: %d; non riscontrati dal codice: %d; valori dove doveva risultare 'non trovato': %d" % (", ".join(d["omessi"]) or "nessuno", d["duplicati_nel_risultato"], d["non_riscontrati_dal_codice"], d["valori_su_dati_che_dovevano_mancare"]),
            "- Mancanti segnalati correttamente: %d/%d" % (len(v["mancanti"]["segnalati_correttamente"]), len(v["mancanti"]["attesi"])),
            "- Incongruenze proposte: %d (attese %d; possibili falsi positivi %d)" % (v["incongruenze"]["proposte"], v["incongruenze"]["attese"], v["incongruenze"]["possibili_falsi_positivi"]),
            "- Scenari concordanti col motore: %s" % (("%d/%d" % (v["scenari"]["concordanti_con_il_motore"], v["scenari"]["attesi"])) if "nota" not in v["scenari"] else "n/c in prova B (valuta la coerenza dei motivi)"),
            "- Richieste: %d (utili attese coperte: %s)" % (v["richieste"]["numero"], ", ".join(v["richieste"]["utili_attese_coperte"]) or "nessuna"),
            "- Soglie/semafori toccati: %s; citazioni normative fuori elenco: %s" % (v["rispetto_dei_limiti"]["chiavi_su_soglie_o_semafori"] or "no", "SÌ" if v["rispetto_dei_limiti"]["citazioni_normative_fuori_elenco"] else "no"),
            "- Tempo di elaborazione: %s s" % v.get("secondi")]


def cmd_scheda(a):
    b = Path(a.bundle)
    meta = json.loads((b / "bundle_meta.json").read_text(encoding="utf-8"))
    val = json.loads((b / "valutazione_automatica.json").read_text(encoding="utf-8"))
    arms = sorted(val)
    rng = random.Random(a.seme)
    ordine = arms[:]
    rng.shuffle(ordine)
    chiave = {"A": ordine[0], "B": ordine[1]} if len(ordine) == 2 else {chr(65 + i): x for i, x in enumerate(ordine)}
    _scrivi_nuovo(b / "CHIAVE_AB_non_aprire_prima_della_revisione.json", json.dumps({"chiave": chiave, "seme": a.seme}, ensure_ascii=False, indent=1))
    righe = ["# Scheda di confronto A/B - prova %s" % meta["prova"], "",
             "Motore: %s (%s) - impronta %s" % (meta["motore"], meta["revisione"], meta["impronta_motore"][:16]),
             "Fascicolo e istruzioni identici (impronta messaggi %s). Le risposte sono etichettate A e B alla cieca: la chiave è in un file separato. Valuta ragionamento ed evidenze, non il solo semaforo.\n" % meta["impronta_messaggi"][:16]]
    for lab in sorted(chiave):
        v = val[chiave[lab]]
        righe += ["## Risposta %s" % lab, "", "Misure automatiche (deterministiche, dal codice):"] + _riassunto(v) + ["",
                  "Prima risposta integra (non modificata): `cieca/risposta_%s.txt`." % lab, ""]
        _scrivi_nuovo(b / "cieca" / ("risposta_%s.txt" % lab), (b / ("arm_" + chiave[lab]) / "risposta_grezza.txt").read_text(encoding="utf-8"))
    righe += ["## Revisione del titolare (compila)", "", "| Criterio | Punteggio A | Punteggio B | Note |", "|---|---|---|---|"]
    righe += ["| %s (%s) |  |  |  |" % (c, s) for c, s in RUBRICA]
    righe += ["", "Tempo di revisione umana A: ____ min    B: ____ min", "Errori sostanziali trovati dal titolare e non rilevati dal codice: A ____  B ____",
              "Preferenza complessiva (A / B / nessuna): ____   Motivo: ____", "", "Dopo la valutazione apri `CHIAVE_AB_non_aprire_prima_della_revisione.json` per sapere quale sistema è A e quale B."]
    out = b / "SCHEDA_CONFRONTO_AB.md"
    _scrivi_nuovo(out, "\n".join(righe))
    print("Scheda cieca scritta in", out)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    s = ap.add_subparsers(dest="cmd", required=True)
    p = s.add_parser("bundle"); p.add_argument("--prova", choices=["A", "B"], required=True); p.add_argument("--cartella", required=True, help="cartella della pratica (quella che contiene PRATICA/ e i PDF)"); p.add_argument("--out", required=True); p.set_defaults(f=cmd_bundle)
    p = s.add_parser("qwen"); p.add_argument("--bundle", required=True); p.set_defaults(f=cmd_qwen)
    p = s.add_parser("claude"); p.add_argument("--bundle", required=True); p.set_defaults(f=cmd_claude)
    p = s.add_parser("registra"); p.add_argument("--bundle", required=True); p.add_argument("--arm", required=True); p.add_argument("--risposta", required=True)
    p.add_argument("--secondi", type=float, required=True); p.add_argument("--modello", required=True); p.add_argument("--configurazione", default=""); p.set_defaults(f=cmd_registra)
    p = s.add_parser("valuta"); p.add_argument("--bundle", required=True); p.add_argument("--verita", required=True); p.add_argument("--arm", nargs="+", default=["claude", "qwen"]); p.set_defaults(f=cmd_valuta)
    p = s.add_parser("scheda"); p.add_argument("--bundle", required=True); p.add_argument("--seme", type=int, default=20261004); p.set_defaults(f=cmd_scheda)
    a = ap.parse_args()
    a.f(a)


if __name__ == "__main__":
    main()
