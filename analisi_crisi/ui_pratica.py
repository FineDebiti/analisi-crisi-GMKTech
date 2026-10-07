"""Schermate della pratica (v3): Pratiche / Registro / Dati / Incongruenze e richieste / Preanalisi. Solo libreria standard (il PDF usa reportlab).

Il modulo non conosce il server: riceve radice, percorso, modulo e cookie e restituisce una risposta (dict). Token, PIN, limiti di
dimensione e controllo dei percorsi restano in interfaccia_locale.py. Ogni testo dinamico passa da E() (escape HTML).
"""
from __future__ import annotations

import hashlib
import html
import re
from http.cookies import SimpleCookie
from pathlib import Path
from urllib.parse import quote

from analisi_crisi import checklist as ck
from analisi_crisi import dati_pratica as dp
from analisi_crisi import pratica as pr

E = lambda x: html.escape("" if x is None else str(x), quote=True)

CSS = """:root{--bg:#f6f7f5;--fg:#1d2420;--mu:#5b665f;--ac:#1f5f4a;--bd:#d5dbd6;--pn:#fff;--ok:#1b7a3d;--wa:#9a6a00;--ko:#b3261e}
@media (prefers-color-scheme:dark){:root{--bg:#141a17;--fg:#e8ece9;--mu:#9aa69f;--ac:#6fcf9f;--bd:#2c3731;--pn:#1b231f}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif;padding:20px 16px}
main{max-width:1000px;margin:auto}h1{font-size:1.4rem;margin:0 0 4px}h2{font-size:1.1rem;margin:26px 0 8px}h3{font-size:1rem;margin:16px 0 6px}
.mu{color:var(--mu);font-size:.9rem}.pn{background:var(--pn);border:1px solid var(--bd);border-radius:8px;padding:14px;margin:10px 0}
a{color:var(--ac)}input,select,button,textarea{font:inherit;padding:6px 9px;border:1px solid var(--bd);border-radius:6px;background:var(--pn);color:var(--fg);min-width:0}
button{background:var(--ac);color:var(--bg);border-color:var(--ac);cursor:pointer}button.sec{background:var(--pn);color:var(--ac)}
form{display:flex;flex-wrap:wrap;gap:8px;align-items:center}
table{border-collapse:collapse;width:100%}td,th{border-bottom:1px solid var(--bd);padding:6px 4px;text-align:left;vertical-align:top}.tw{overflow-x:auto}
nav{display:flex;flex-wrap:wrap;gap:6px;margin:0 0 14px;padding-bottom:10px;border-bottom:1px solid var(--bd)}
nav a{padding:6px 12px;border:1px solid var(--bd);border-radius:6px;text-decoration:none;background:var(--pn)}nav a.on{background:var(--ac);color:var(--bg);border-color:var(--ac)}
.av{border-left:4px solid var(--wa);padding:8px 12px;background:var(--pn)}.ok{border-left:4px solid var(--ok);padding:8px 12px;background:var(--pn)}
.er{border-left:4px solid var(--ko);padding:8px 12px;background:var(--pn);font-weight:600}
.bd{display:inline-block;padding:3px 10px;border-radius:12px;font-weight:700;font-size:.85rem;border:2px solid var(--mu)}.bd.A{border-color:var(--ok);color:var(--ok)}.bd.N{border-color:var(--ko);color:var(--ko)}
.rq{border:2px solid var(--bd);border-left-width:8px;border-radius:8px;padding:10px 14px;margin:10px 0;background:var(--pn)}.rq h3{margin:0 0 4px}
.c-VERDE{border-color:var(--ok)}.c-GIALLO{border-color:var(--wa)}.c-ROSSO{border-color:var(--ko)}.c-ND{border-color:var(--mu)}
.et{font-weight:700}.sm{font-size:.78rem;word-break:break-all}input.n{width:11em;text-align:right}input.p{width:4.5em}input.t{width:14em}ol{padding-left:20px}"""


def pagina(titolo, corpo):
    return ("<!doctype html><html lang='it'><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
            "<title>%s</title><style>%s</style><main>%s</main></html>" % (E(titolo), CSS, corpo)).encode("utf-8")


def resp(body, status=200, headers=(), tipo="text/html; charset=utf-8"):
    return {"status": status, "body": body, "tipo": tipo, "headers": list(headers), "location": None}


def redirect(loc, headers=()):
    return {"status": 303, "body": b"", "tipo": "text/html", "headers": list(headers), "location": loc}


class NonTrovato(Exception):
    pass


def op_da_cookie(header):
    try:
        c = SimpleCookie()
        c.load(header or "")
        return __import__("urllib.parse", fromlist=["unquote"]).unquote(c["op"].value)[:60] if "op" in c else ""
    except Exception:
        return ""


def T(intest, righe, vuoto="Nessun elemento."):
    """Tabella: le celle sono HTML GIA' escapato da chi chiama."""
    if not righe:
        return "<p class='mu'>%s</p>" % E(vuoto)
    return ("<div class='tw'><table><tr>" + "".join("<th>%s</th>" % E(h) for h in intest) + "</tr>"
            + "".join("<tr>" + "".join("<td>%s</td>" % c for c in r) + "</tr>" for r in righe) + "</table></div>")


def opzioni(valori, scelto=None, etichette=None):
    return "".join("<option value='%s'%s>%s</option>" % (E(v), " selected" if v == scelto else "", E((etichette or {}).get(v, v))) for v in valori)


def campo_op(op):
    return "<input name='operatore' class='t' placeholder='Il tuo nome' value='%s' required>" % E(op)


# ---------------------------------------------------------------- struttura comune
PAGINE = (("registro", "Registro"), ("dati", "Dati"), ("incongruenze", "Incongruenze e richieste"), ("preanalisi", "Preanalisi"), ("modello", "Modello locale"))


def intestazione(n, pc, attiva, msg=None, err=None):
    nav = "<nav><a href='/'>Pratiche</a>" + "".join("<a href='/p/%s/%s'%s>%s</a>" % (quote(n), p, " class='on'" if p == attiva else "", E(t)) for p, t in PAGINE) + "</nav>"
    if (pc / pr.FILE["pratica"]).is_file():
        info = pr._leggi(pc, "pratica")
        a = dp.approvazione(pc)
        badge = "<span class='bd %s'>%s</span>" % ("A" if a["stato"] == "APPROVATA" else "N", E(a["stato"]))
        tit = "<h1>%s</h1><p class='mu'>Procedura: %s - stato: %s - ultima modifica: %s &nbsp; %s &nbsp; <a href='/caso/%s'>Vista avanzata</a></p>" % (
            E(info.get("nome") or n), E(info.get("procedura") or "-"), E(info["stato"]), E(dp.dt_it(dp.ultima_modifica(pc))), badge, quote(n))
    else:
        tit = "<h1>%s</h1><p class='mu'>Nessuna pratica aperta per questa cartella.</p>" % E(n)
    m = ("<p class='ok'>%s</p>" % E(msg)) if msg else ""
    m += ("<p class='er'>%s</p>" % E(err)) if err else ""
    return nav + tit + m


def senza_pratica(n, op):
    return ("<div class='pn'><p>Questa cartella non ha ancora una pratica.</p><form method='post' action='/p/%s/apri'>%s<select name='procedura'>%s</select>"
            "<button>Apri la pratica</button></form></div>" % (quote(n), campo_op(op), opzioni(dp.PROCEDURE)))


# ---------------------------------------------------------------- home
def home(radice, op, msg=None, err=None, status=200):
    righe = []
    for p in dp.elenco_pratiche(radice):
        bd = "" if not p["pratica"] else "<span class='bd %s'>%s</span>" % ("A" if p["approvazione"] == "APPROVATA" else "N", E(p["approvazione"]))
        righe.append(["<a href='/p/%s/registro'>%s</a>" % (quote(p["cartella"]), E(p["nome"])), E(p["procedura"]), E(p["stato"]), bd,
                      E(dp.dt_it(p["modifica"])), E(p["documenti"]), "<a href='/caso/%s'>Vista avanzata</a>" % quote(p["cartella"])])
    uso = ["Crea una pratica (nome e tipo di procedura) oppure riaprine una dall'elenco.",
           "In Registro carica i PDF, anche tanti insieme, e controlla tipo, data e periodo di ciascuno.",
           "In Dati controlla i valori letti dal bilancio e inserisci a mano quelli mancanti: un campo vuoto resta \"non disponibile\", mai zero.",
           "In Incongruenze e richieste annota ciò che non quadra e i documenti da chiedere.",
           "In Preanalisi premi \"Avvia preanalisi\", rivedi il risultato, approvalo come provvisorio e scarica il PDF."]
    corpo = ("<h1>ANALISI CRISI</h1><p class='mu'>Preanalisi economico-finanziaria. Supporto alla decisione, non attestazione. I dati restano su questa macchina.</p>"
             + (("<p class='ok'>%s</p>" % E(msg)) if msg else "") + (("<p class='er'>%s</p>" % E(err)) if err else "")
             + "<h2>Come si usa</h2><div class='pn'><ol>" + "".join("<li>%s</li>" % E(x) for x in uso) + "</ol></div>"
             + "<h2>Nuova pratica</h2><div class='pn'><form method='post' action='/pratiche/nuova'><input name='nome' class='t' placeholder='Nome della pratica' required>"
             + "<select name='procedura'>%s</select>%s<button>Crea la pratica</button></form></div>" % (opzioni(dp.PROCEDURE), campo_op(op))
             + "<h2>Pratiche</h2>" + T(["Pratica", "Procedura", "Stato", "Approvazione", "Ultima modifica", "Documenti", ""], righe, "Nessuna pratica: creane una qui sopra."))
    return resp(pagina("ANALISI CRISI", corpo), status)


# ---------------------------------------------------------------- registro
def registro(n, cart, pc, op, msg=None, err=None, status=200):
    corpo = intestazione(n, pc, "registro", msg, err)
    q = quote(n)
    if not (pc / pr.FILE["pratica"]).is_file():
        return resp(pagina(n, corpo + senza_pratica(n, op)), status)
    reg = pr._leggi(pc, "registro", [])
    est = dp.carica(pc)["estrazioni"]
    righe = []
    for r in reg:
        fid = "fd%s" % r["id"]
        if r.get("sha256"):
            e = est.get(str(r["id"]))
            if e:
                lett = "Eseguita: %d campi letti" % len(e["letti"]) if e["esito"] == "ESEGUITA" else "Non riuscita: inserimento manuale"
            else:
                lett = "Da eseguire" if r.get("tipo") == "bilancio" else "Non prevista: inserimento manuale"
            cel_tipo = "<select name='tipo' form='%s'>%s</select>" % (fid, opzioni(dp.TIPI_DOC, r.get("tipo") if r.get("tipo") in dp.TIPI_DOC else "altro"))
            cel_dd = "<input name='data_documento' class='p' style='width:8em' form='%s' value='%s' placeholder='gg/mm/aaaa'>" % (fid, E(dp.data_it(r.get("data_documento"))))
            cel_per = "<input name='periodo' class='p' style='width:7em' form='%s' value='%s'>" % (fid, E(r.get("periodo_economico")))
            cel_nat = "<select name='natura' form='%s'>%s</select>" % (fid, opzioni(dp.NATURE_FILE, r["natura"]))
            azioni = ("<form id='%s' method='post' action='/p/%s/documento'><input type='hidden' name='id' value='%s'><input type='hidden' name='operatore' value='%s'><button class='sec'>Salva</button></form>" % (fid, q, r["id"], E(op))
                      + ("<form method='post' action='/p/%s/rileggi'><input type='hidden' name='id' value='%s'><button class='sec'>Rileggi</button></form>" % (q, r["id"]) if r.get("tipo") == "bilancio" else ""))
            hh = "<span class='sm'>%s</span>" % E(r["sha256"])
            acq = E(dp.dt_it(r["data_acquisizione"]))
        else:
            lett, cel_tipo, cel_dd, cel_per, cel_nat, azioni, hh, acq = "-", E(r.get("tipo")), "-", "-", "NON DISPONIBILE (atteso, mancante)", "", "-", "-"
        righe.append([E(r["id"]), E(r["nome"]), cel_tipo, hh, acq, cel_dd, cel_per, cel_nat, E(lett), azioni])
    carica = ("<h2>Carica i documenti</h2><div class='pn'><form method='post' action='/p/%s/carica' enctype='multipart/form-data'>"
              "<input type='file' name='pdf' accept='.pdf' multiple required><input type='hidden' name='operatore' value='%s'><button>Carica i PDF</button></form>"
              "<p class='mu'>Puoi scegliere più file insieme. Il tipo viene riconosciuto quando possibile: controllalo nella tabella. "
              "La data di acquisizione e l'impronta (hash) le registra il sistema.</p></div>" % (q, E(op)))
    manc = ("<h3>Documento atteso ma mancante</h3><form method='post' action='/p/%s/mancante'><input name='nome_mancante' class='t' placeholder='Es. Estratto di ruolo' required>"
            "<select name='tipo'>%s</select><label><input type='checkbox' name='decisivo'> Decisivo</label><button class='sec'>Segna come mancante</button></form>" % (q, opzioni(dp.TIPI_DOC)))
    lista = ck.stato_checklist(pc, pr._metriche(pc, None))
    rc = []
    for g in ("A", "B"):
        for v in lista[g]:
            rc.append([E(v["id"]), E(v["etichetta"]), "<select name='s_%s'>%s</select>" % (E(v["id"]), opzioni(ck.STATI_VOCE, v["stato"])),
                       E(v["fallback"] if g == "A" else ("Suggerito: " + str(v["criticita"]) if v["suggerita"] else "Non richiesto ora"))])
    chk = ("<h2>Documenti attesi (checklist)</h2><div class='pn'><p class='mu'>Nessun documento è obbligatorio per avviare la preanalisi. "
           "A = documenti di partenza; B = approfondimenti suggeriti dall'analisi.</p><form method='post' action='/p/%s/checklist' style='display:block'>%s"
           "%s<button>Salva gli stati</button></form></div>" % (q, T(["Id", "Voce", "Stato", "Se manca / perché"], rc), campo_op(op)))
    corpo += (carica + "<h2>Registro documentale</h2>" + T(["Id", "Nome", "Tipo", "Hash SHA-256", "Acquisito il", "Data documento", "Periodo", "Natura", "Lettura automatica", ""],
                                                          righe, "Nessun documento: carica i PDF qui sopra.") + manc + chk)
    return resp(pagina(n + " - Registro", corpo), status)


# ---------------------------------------------------------------- dati
def dati(n, cart, pc, op, msg=None, err=None, status=200):
    corpo = intestazione(n, pc, "dati", msg, err)
    q = quote(n)
    if not (pc / pr.FILE["pratica"]).is_file():
        return resp(pagina(n, corpo + senza_pratica(n, op)), status)
    d = dp.carica(pc)
    reg = {r["id"]: r for r in pr._leggi(pc, "registro", [])}
    corpo += "<p class='av'><b>Lettura automatica.</b> %s</p>" % E(dp.NOTA_LETTURA)
    righe, storico = [], []
    for c in dp.CAMPI_LISTA:
        r = d["campi"].get(c["codice"])
        if r and r.get("valore") is not None:
            orig = E(dp.ORIGINI[r["origine"]])
            pv = r.get("precedente")
            if r["origine"] == "CORRETTO" and pv:
                orig += "<br><span class='mu'>Valore precedente: %s (%s). Corretto da %s il %s.</span>" % (E(dp.fmt_it(pv.get("valore"))), E(dp.ORIGINI.get(pv.get("origine"), "")), E(r["da"]), E(dp.dt_it(r["il"])))
            elif r["origine"] in ("OPERATORE", "LLM"):
                orig += "<br><span class='mu'>Da %s il %s.</span>" % (E(r["da"]), E(dp.dt_it(r["il"])))
            righe.append([E(c["etichetta"]), E(dp.fmt_it(r["valore"])), E(c["unita"]), E(dp.data_it(r.get("esercizio"))), E((reg.get(r.get("id_documento")) or {}).get("nome") or "-"),
                          E(r.get("pagina") or "-"), E(r["stato"]), orig, E(r.get("note"))])
        else:
            righe.append([E(c["etichetta"]), "<i>non disponibile</i>", E(c["unita"]), "-", "-", "-", "-", "-", ""])
        for s in (r or {}).get("storico", []):
            storico.append([E(c["etichetta"]), E(dp.fmt_it(s.get("valore"))), E(s.get("stato")), E(dp.ORIGINI.get(s.get("origine"), "")), E(s.get("da")), E(dp.dt_it(s.get("il")))])
    corpo += "<h2>Dati estratti e inseriti</h2>" + T(["Dato", "Valore", "Unità", "Esercizio", "Documento", "Pag.", "Stato", "Origine", "Note"], righe)
    # documenti e lettura automatica
    rd = []
    for r in reg.values():
        if r.get("sha256"):
            e = d["estrazioni"].get(str(r["id"]))
            if e:
                txt = ("Letti %d campi: %s. Non trovati: %s." % (len(e["letti"]), ", ".join(dp.CAMPO[x]["etichetta"] for x in e["letti"]) or "nessuno",
                                                                   ", ".join(dp.CAMPO[x]["etichetta"] for x in e["non_trovati"]) or "nessuno")) if e["esito"] == "ESEGUITA" else ("; ".join(e["avvisi"]) or e["esito"])
            else:
                txt = "Lettura automatica prevista: usa \"Rileggi\" nel Registro." if r.get("tipo") == "bilancio" else "Tipo '%s': non letto automaticamente, inserire i valori a mano." % (r.get("tipo") or "n.d.")
            rd.append([E(r["id"]), E(r["nome"]), E(r.get("tipo")), E(txt)])
    corpo += "<h3>Che cosa è stato letto da ciascun documento</h3>" + T(["Id", "Documento", "Tipo", "Esito"], rd, "Nessun documento caricato.")
    # maschera di inserimento
    docs = {"": "(nessuno)"}
    docs.update({str(r["id"]): "%s - %s" % (r["id"], r["nome"]) for r in reg.values() if r.get("sha256")})
    rm = []
    for c in dp.CAMPI_LISTA:
        cod = c["codice"]
        r = d["campi"].get(cod) or {}
        if c["tipo"] == "sino":
            val = "<select name='v_%s'>%s</select>" % (cod, opzioni(["", "SI", "NO"], r.get("valore") or "", {"": "non disponibile", "SI": "Sì", "NO": "No"}))
        else:
            val = "<input class='n' name='v_%s' value='%s' placeholder='non disponibile' inputmode='decimal'>" % (cod, E(dp.fmt_modifica(r.get("valore"))))
        rm.append(["<b>%s</b><br><span class='mu'>%s</span>" % (E(c["etichetta"]), E(c["aiuto"])), val,
                   "<select name='d_%s'>%s</select>" % (cod, opzioni(list(docs), str(r.get("id_documento") or ""), docs)),
                   "<input class='p' name='g_%s' value='%s'>" % (cod, E(r.get("pagina"))),
                   "<select name='s_%s'>%s</select>" % (cod, opzioni(pr.NATURE_DATO, r.get("stato") or "DA VERIFICARE")),
                   "<input class='t' name='n_%s' value='%s'>" % (cod, E(r.get("note")))])
    corpo += ("<h2>Inserimento manuale assistito</h2><div class='pn'><p class='mu'>Scrivi i numeri come sul documento (anche 1.234,56). "
              "Un campo lasciato vuoto resta \"non disponibile\" e non vale mai zero. Se correggi un valore, il precedente resta nello storico. "
              "Se la preanalisi era già approvata, l'approvazione decade e va rigenerata.</p>"
              "<form method='post' action='/p/%s/dati' style='display:block'>%s<p>%s <button>Salva i dati</button></p></form></div>" % (
                  q, T(["Dato", "Valore", "Fonte (documento)", "Pag.", "Stato", "Note"], rm), campo_op(op)))
    calc = dp.calcola_metriche(dp.valori(pc))[1]
    corpo += "<h2>Calcoli del motore sui dati inseriti</h2>" + T(["Calcolo", "Risultato", "Nota"], [[E(a), E(b), E(c)] for a, b, c in calc])
    corpo += "<details><summary>Storico delle modifiche ai dati</summary>" + T(["Dato", "Valore precedente", "Stato", "Origine", "Da", "Quando"], storico, "Nessuna modifica registrata.") + "</details>"
    return resp(pagina(n + " - Dati", corpo), status)


# ---------------------------------------------------------------- incongruenze e richieste
def incongruenze(n, cart, pc, op, msg=None, err=None, status=200):
    corpo = intestazione(n, pc, "incongruenze", msg, err)
    q = quote(n)
    if not (pc / pr.FILE["pratica"]).is_file():
        return resp(pagina(n, corpo + senza_pratica(n, op)), status)
    inc = pr._leggi(pc, "inc", [])
    ri = []
    for x in inc:
        if x["stato"] == "APERTA":
            az = ("<form method='post' action='/p/%s/inc_risolvi'><input type='hidden' name='id' value='%s'><input name='nota' class='t' placeholder='Nota di risoluzione' required>"
                  "<input type='hidden' name='operatore' value='%s'><button class='sec'>Risolvi</button></form>" % (q, x["id"], E(op)))
        else:
            az = ("<span class='mu'>Risolta da %s il %s: %s</span><form method='post' action='/p/%s/inc_riapri'><input type='hidden' name='id' value='%s'><input name='nota' class='t' placeholder='Motivo' required>"
                  "<input type='hidden' name='operatore' value='%s'><button class='sec'>Riapri</button></form>" % (E(x.get("risolta_da")), E(dp.dt_it(x.get("risolta_il"))), E(x.get("nota_risoluzione")), q, x["id"], E(op)))
        ri.append([E(x["id"]), E(x["descrizione"]), E(x["gravita"]), E(x["stato"]), az])
    bozze = dp.bozze_incongruenze(pc)
    rb = ["<form method='post' action='/p/%s/inc_aggiungi'><input type='hidden' name='descrizione' value='%s'><select name='gravita'>%s</select><input type='hidden' name='operatore' value='%s'><button class='sec'>Conferma come incongruenza</button></form>" % (
        q, E(b["descrizione"]), opzioni(pr.GRAVITA, b["gravita"]), E(op)) for b in bozze]
    corpo += ("<h2>Incongruenze</h2>" + T(["Id", "Descrizione", "Gravità", "Stato", "Azioni"], ri, "Nessuna incongruenza.")
              + "<p class='mu'>Le incongruenze SOSTANZIALI aperte e ogni loro modifica fanno decadere l'approvazione.</p>"
              + "<h3>Aggiungi un'incongruenza</h3><form method='post' action='/p/%s/inc_aggiungi'><input name='descrizione' class='t' style='width:26em' placeholder='Che cosa non quadra' required>"
                "<select name='gravita'>%s</select>%s<button>Aggiungi</button></form>" % (q, opzioni(pr.GRAVITA, "MINORE"), campo_op(op)))
    if bozze:
        corpo += "<h3>Proposte dell'applicazione (da confermare)</h3>" + T(["Proposta", "Gravità", ""], [[E(b["descrizione"]), E(b["gravita"]), f] for b, f in zip(bozze, rb)])
    rich = pr._leggi(pc, "rich", [])
    rr = []
    for x in sorted(rich, key=lambda r: r["priorita"]):
        rr.append([E({1: "1 - alta", 2: "2 - media", 3: "3 - bassa"}[x["priorita"]]), E(x["richiesta"]), E(x["perche"]), E(x["destinatario"]),
                   "<form method='post' action='/p/%s/rich_stato'><input type='hidden' name='id' value='%s'><select name='stato'>%s</select><input type='hidden' name='operatore' value='%s'><button class='sec'>Aggiorna</button></form>" % (
                       q, x["id"], opzioni(pr.STATI_RICH, x["stato"]), E(op))])
    corpo += ("<h2>Richieste documentali</h2>" + T(["Priorità", "Richiesta", "Perché serve", "Destinatario", "Stato"], rr, "Nessuna richiesta.")
              + "<h3>Aggiungi una richiesta</h3><form method='post' action='/p/%s/rich_aggiungi'><input name='richiesta' class='t' placeholder='Documento o informazione' required>"
                "<input name='perche' class='t' placeholder='Perché serve'><input name='destinatario' class='t' placeholder='A chi si chiede'>"
                "<select name='priorita'>%s</select>%s<button>Aggiungi</button></form>" % (q, opzioni(["1", "2", "3"], "2", {"1": "1 - alta", "2": "2 - media", "3": "3 - bassa"}), campo_op(op)))
    return resp(pagina(n + " - Incongruenze e richieste", corpo), status)


# ---------------------------------------------------------------- preanalisi, revisione e approvazione
def _cls(c):
    return "c-" + (c if c in ("VERDE", "GIALLO", "ROSSO") else "ND")


def preanalisi(n, cart, pc, op, msg=None, err=None, status=200):
    corpo = intestazione(n, pc, "preanalisi", msg, err)
    q = quote(n)
    if not (pc / pr.FILE["pratica"]).is_file():
        return resp(pagina(n, corpo + senza_pratica(n, op)), status)
    iniz = ck.sufficienza_per_iniziare(pc, pr._metriche(pc, None))
    limiti = " ".join(iniz["limiti"]) if iniz["limiti"] else "Nessun limite informativo rilevante."
    corpo += ("<div class='pn'><p class='av'><b>Limiti informativi.</b> %s</p><p class='mu'>La preanalisi parte sempre, anche con il fascicolo incompleto: "
              "i dati mancanti restano \"non calcolabili\", mai zero.</p><form method='post' action='/p/%s/avvia'>%s<button>Avvia preanalisi</button></form></div>" % (E(limiti), q, campo_op(op)))
    d = pr.ultima_preanalisi(pc)
    if not d:
        return resp(pagina(n + " - Preanalisi", corpo + "<p class='mu'>Nessuna preanalisi ancora prodotta.</p>"), status)
    a = dp.approvazione(pc)
    agg = dp.preanalisi_aggiornata(pc)
    r = d["riquadri"]
    ini, con = d["sufficienza"]["per_iniziare"], d["sufficienza"]["per_concludere"]
    if not agg:
        corpo += "<p class='er'>I dati sono cambiati dopo l'ultima preanalisi: premi di nuovo \"Avvia preanalisi\" prima di approvare o scaricare.</p>"
    if a["stato"] == "APPROVATA":
        corpo += "<p class='ok'><span class='bd A'>APPROVATA</span> come provvisoria da %s il %s.</p>" % (E(a["approvata_da"]), E(dp.dt_it(a["approvata_il"])))
    else:
        corpo += "<p><span class='bd N'>NON APPROVATA</span></p>"
        if a.get("decaduta"):
            corpo += "<p class='er'>L'approvazione di %s del %s è DECADUTA: %s. Rigenera la preanalisi e approva di nuovo.</p>" % (E(a.get("approvata_da")), E(dp.dt_it(a.get("approvata_il"))), E(a.get("motivo")))
    corpo += "<h2>%s</h2><p class='av'>%s</p>" % ("Ricognizione del fascicolo" if d["tipo"] == "RICOGNIZIONE_FASCICOLO" else "Preanalisi provvisoria", E(pr.dicitura(d, a["stato"] == "APPROVATA")))
    corpo += ("<div class='rq %s'><h3>%s</h3><p><span class='et'>%s</span> - %s</p></div>" % (_cls(r["sostenibilita"]["esito"]), E(r["sostenibilita"]["titolo"]), E(r["sostenibilita"]["esito"]), E(r["sostenibilita"]["dettaglio"]))
              + "<div class='rq %s'><h3>%s</h3><p><span class='et'>%s</span></p><p class='mu'>%s</p></div>" % (_cls(r["qualita_dati"].get("colore")), E(r["qualita_dati"]["titolo"]), E(r["qualita_dati"]["esito"]), E(r["qualita_dati"]["dettaglio"]))
              + "<div class='rq %s'><h3>%s</h3><p><span class='et'>%s</span> - %s</p></div>" % (_cls(r["fattibilita"].get("colore")), E(r["fattibilita"]["titolo"]), E(r["fattibilita"]["esito"]), E(r["fattibilita"]["dettaglio"]))
              + "<div class='rq c-ND'><h3>%s</h3><p><span class='et'>%s</span></p></div>" % (E(r["stato_conclusione"]["titolo"]), E(r["stato_conclusione"]["esito"]))
              + "<div class='rq c-VERDE'><h3>Sufficienza per iniziare</h3><p><span class='et'>SÌ</span></p></div>"
              + "<div class='rq %s'><h3>Sufficienza per concludere</h3><p><span class='et'>%s</span></p><p class='mu'>%s</p></div>" % ("c-VERDE" if con["ok"] else "c-GIALLO", "SÌ" if con["ok"] else "NO", E("; ".join(con.get("motivi_brevi", con["motivi"])))))
    corpo += "<h3>Richieste documentali prioritarie (massimo 5)</h3>" + T(["#", "Richiesta", "Che cosa permetterà di verificare"], [[E(x["ordine"]), E(x["richiesta"]), E(x["permette_di_verificare"])] for x in d["richieste_prioritarie"]], "Nessuna richiesta prioritaria.")
    # revisione
    rv = [[E(x["dato"]), E(pr.eur(x["valore"]) if x["unita"] == "EUR" else x["valore"]), E(x.get("periodo") or "-"), E(x["natura"]), E(x["fonte"]), E(x["pagina"])] for x in d["dati_estratti"]]
    cr = [[E(x["tipo"]), E(x["testo"]), E(x["gravita"]), E(x["stato"])] for x in d["criticita"]]
    corpo += ("<details open><summary><b>Revisione: dati usati e criticità</b></summary>" + T(["Dato", "Valore", "Periodo", "Stato", "Fonte", "Pag."], rv, "Nessun dato registrato.")
              + T(["Tipo", "Descrizione", "Gravità", "Stato"], cr, "Nessuna criticità rilevata con i dati disponibili.") + "</details>")
    corpo += "<h3>Scenari</h3>" + T(["Scenario", "Stato", "Motivo (dettaglio, una sola volta)"], [[E(x["scenario"]), E(x["stato"]), "<br>".join(E(m) for m in x["motivo"])] for x in d["scenari"]], "")
    docs = ["<a href='/p/%s/preanalisi.pdf'>Scarica il PDF</a>" % q]
    if d.get("documento_word"):
        docs.append("<a href='/caso/%s/file/PRATICA/%s'>Scarica il Word (.docx)</a>" % (q, quote(d["documento_word"])))
    if a.get("documento_word"):
        docs.append("<a href='/caso/%s/file/PRATICA/%s'>Word approvato</a>" % (q, quote(a["documento_word"])))
    corpo += ("<p>%s</p><form method='post' action='/p/%s/approva'><input name='titolare' class='t' placeholder='Nome del titolare' required value='%s'><button>Approva come provvisoria</button></form>"
              "<p class='mu'>Motore: %s - impronta dei parametri: <span class='sm'>%s</span></p>" % (" - ".join(docs), q, E(op), E(d["versione_motore"]), E(d["impronta"])))
    return resp(pagina(n + " - Preanalisi", corpo), status)


def _modello(*a, **k):
    from analisi_crisi import ui_modello
    return ui_modello.pagina_modello(*a, **k)


PAG_FN = {"registro": registro, "dati": dati, "incongruenze": incongruenze, "preanalisi": preanalisi, "modello": _modello}
AZIONE_PAG = {"llm_estrai": "modello", "llm_applica": "modello", "apri": "registro", "carica": "registro", "documento": "registro", "rileggi": "registro", "mancante": "registro", "checklist": "registro",
              "dati": "dati", "inc_aggiungi": "incongruenze", "inc_risolvi": "incongruenze", "inc_riapri": "incongruenze", "rich_aggiungi": "incongruenze",
              "rich_stato": "incongruenze", "avvia": "preanalisi", "approva": "preanalisi"}


def _cartella(radice, n):
    if not dp.NOME_OK.match(n or ""):
        raise NonTrovato()
    cart = Path(radice) / n
    if not cart.is_dir():
        raise NonTrovato()
    return cart, cart / "PRATICA"


def non_trovato():
    return resp(pagina("Non trovato", "<h1>Non trovato</h1><p><a href='/'>Torna alle pratiche</a></p>"), 404)


def gestisci_get(radice, parti, query, cookie):
    """parti: percorso gia' decodificato, es. ['p','DEMO','dati']. Ritorna None se il percorso non e' di questo modulo."""
    op = op_da_cookie(cookie)
    msg = query.get("m")
    try:
        if parti == [""]:
            return home(radice, op, msg)
        if parti[0] != "p" or len(parti) not in (2, 3):
            return None
        n = parti[1]
        cart, pc = _cartella(radice, n)
        sotto = parti[2] if len(parti) == 3 else "registro"
        if sotto in PAG_FN:
            return PAG_FN[sotto](n, cart, pc, op, msg)
        if sotto == "preanalisi.pdf":
            d = pr.ultima_preanalisi(pc) if (pc / pr.FILE["pratica"]).is_file() else None
            if not d:
                return resp(pagina("PDF", intestazione(n, pc, "preanalisi") + "<p class='er'>Prima avvia la preanalisi: non c'è ancora nulla da scaricare.</p>"), 404)
            from analisi_crisi import pdf_preanalisi
            body = pdf_preanalisi.genera(d, dp.approvazione(pc), dp.preanalisi_aggiornata(pc))
            return resp(body, 200, [("Content-Disposition", "attachment; filename=\"Preanalisi_%s.pdf\"" % n)], "application/pdf")
        return non_trovato()
    except NonTrovato:
        return non_trovato()


def _ok(n, azione, testo, op):
    h = [("Set-Cookie", "op=%s; Path=/; SameSite=Strict; Max-Age=31536000" % quote(op))] if op else []
    return redirect("/p/%s/%s?m=%s" % (quote(n), AZIONE_PAG[azione], quote(testo)), h)


def gestisci_post(radice, parti, form, cookie, file_fn):
    """Ritorna None se il percorso non e' di questo modulo."""
    op = (form.get("operatore") or "").strip()[:60] or op_da_cookie(cookie)
    try:
        if parti == ["pratiche", "nuova"]:
            try:
                cart, pc = dp.crea_pratica(radice, form.get("nome"), form.get("procedura"), op)
            except pr.ErrorePratica as e:
                return home(radice, op, err=str(e), status=400)
            h = [("Set-Cookie", "op=%s; Path=/; SameSite=Strict; Max-Age=31536000" % quote(op))] if op else []
            return redirect("/p/%s/registro?m=%s" % (quote(cart), quote("Pratica creata. Carica i documenti PDF.")), h)
        if len(parti) != 3 or parti[0] != "p" or parti[2] not in AZIONE_PAG:
            return None
        n, azione = parti[1], parti[2]
        cart, pc = _cartella(radice, n)
        pagina_ = AZIONE_PAG[azione]
        try:
            if azione == "apri":
                if (pc / pr.FILE["pratica"]).is_file():
                    raise pr.ErrorePratica("La pratica esiste già.")
                if form.get("procedura") not in dp.PROCEDURE:
                    raise dp.ErroreDati("Scegli il tipo di procedura.")
                dp.apri(pc, n, form["procedura"], op)
                return _ok(n, azione, "Pratica aperta.", op)
            if not (pc / pr.FILE["pratica"]).is_file():
                raise pr.ErrorePratica("Questa cartella non ha una pratica: aprila prima dal Registro.")
            return _azione(n, cart, pc, azione, form, op, file_fn)
        except pr.ErrorePratica as e:
            return PAG_FN[pagina_](n, cart, pc, op, err=str(e), status=400)
    except NonTrovato:
        return non_trovato()


def _azione(n, cart, pc, azione, form, op, file_fn):
    f = form
    if azione == "carica":
        return _ok(n, azione, _carica(cart, pc, file_fn()), op)
    if azione == "documento":
        i = _intero(f.get("id"))
        dp.aggiorna_documento(pc, i, f.get("tipo"), f.get("data_documento", ""), f.get("periodo", ""), f.get("natura"))
        if f.get("tipo") == "bilancio" and str(i) not in dp.carica(pc)["estrazioni"]:
            dp.estrai_bilancio(pc, cart, i)
        return _ok(n, azione, "Documento aggiornato.", op)
    if azione == "rileggi":
        rep = dp.estrai_bilancio(pc, cart, _intero(f.get("id")))
        return _ok(n, azione, _testo_rep(rep), op)
    if azione == "mancante":
        nome = (f.get("nome_mancante") or "").strip()
        if not nome:
            raise dp.ErroreDati("Scrivi il nome del documento atteso.")
        tipo = f.get("tipo") if f.get("tipo") in dp.TIPI_DOC else "altro"
        with dp.modifica(pc, "documento mancante registrato"):
            pr.registra_documento(pc, nome[:120], None, tipo, decisivo="decisivo" in f)
        return _ok(n, azione, "Documento segnato come atteso e mancante.", op)
    if azione == "checklist":
        att = {v["id"]: v["stato"] for g in ck.stato_checklist(pc, pr._metriche(pc, None)).values() for v in g}
        mod = [(i, f["s_" + i]) for i in att if f.get("s_" + i) in ck.STATI_VOCE and f["s_" + i] != att[i]]
        if not mod:
            return _ok(n, azione, "Nessuna modifica agli stati.", op)
        if not op:
            raise dp.ErroreDati("Scrivi il tuo nome per salvare gli stati.")
        with dp.modifica(pc, "stati della checklist modificati"):
            for i, nuovo in mod:
                pr.imposta_stato_voce(pc, i, nuovo, op)
        return _ok(n, azione, "Stati aggiornati: %d." % len(mod), op)
    if azione == "llm_estrai":
        from analisi_crisi import ui_modello
        return _ok(n, azione, ui_modello.azione_estrai(n, cart, pc, op), op)
    if azione == "llm_applica":
        from analisi_crisi import ui_modello
        sel = [int(k[4:]) for k in f if k.startswith("sel_") and k[4:].isdigit()]
        return _ok(n, azione, ui_modello.azione_applica(n, cart, pc, op, sel), op)
    if azione == "dati":
        righe = {c["codice"]: {"valore": f.get("v_" + c["codice"]), "id_documento": f.get("d_" + c["codice"]), "pagina": f.get("g_" + c["codice"]),
                               "stato": f.get("s_" + c["codice"]), "note": f.get("n_" + c["codice"])} for c in dp.CAMPI_LISTA if ("v_" + c["codice"]) in f}
        mod = dp.salva_valori(pc, righe, op)
        return _ok(n, azione, ("Dati salvati: %d campi modificati." % len(mod)) if mod else "Nessuna modifica ai dati.", op)
    if azione in ("inc_aggiungi",):
        desc = (f.get("descrizione") or "").strip()
        if not desc:
            raise dp.ErroreDati("Scrivi che cosa non quadra.")
        with dp.modifica(pc, "incongruenza aggiunta"):
            pr.aggiungi_incongruenza(pc, desc[:400], [], f.get("gravita"))
        return _ok(n, azione, "Incongruenza aggiunta.", op)
    if azione == "inc_risolvi":
        with dp.modifica(pc, "incongruenza risolta"):
            pr.risolvi_incongruenza(pc, _intero(f.get("id")), op, f.get("nota"))
        return _ok(n, azione, "Incongruenza risolta.", op)
    if azione == "inc_riapri":
        dp.riapri_incongruenza(pc, _intero(f.get("id")), op, f.get("nota"))
        return _ok(n, azione, "Incongruenza riaperta.", op)
    if azione == "rich_aggiungi":
        txt = (f.get("richiesta") or "").strip()
        if not txt:
            raise dp.ErroreDati("Scrivi che cosa chiedere.")
        pr.aggiungi_richiesta(pc, txt[:300], (f.get("perche") or "").strip()[:300], _intero(f.get("priorita"), "Priorità non valida."), (f.get("destinatario") or "").strip()[:120])
        return _ok(n, azione, "Richiesta aggiunta.", op)
    if azione == "rich_stato":
        pr.aggiorna_richiesta(pc, _intero(f.get("id")), f.get("stato"))
        return _ok(n, azione, "Richiesta aggiornata.", op)
    if azione == "avvia":
        d = dp.avvia_preanalisi(pc, nome=op)
        return _ok(n, azione, "Ricognizione del fascicolo prodotta." if d["tipo"] == "RICOGNIZIONE_FASCICOLO" else "Preanalisi provvisoria prodotta.", op)
    if azione == "approva":
        a = dp.approva(pc, f.get("titolare") or "")
        return _ok(n, azione, "Preanalisi %s da %s." % (a["stato"], a["approvata_da"]), (f.get("titolare") or "").strip()[:60] or op)
    raise pr.ErrorePratica("Azione non valida.")


def _intero(v, msg="Richiesta non valida."):
    try:
        return int(v)
    except (TypeError, ValueError):
        raise dp.ErroreDati(msg)


def _testo_rep(rep):
    if rep["esito"] != "ESEGUITA":
        return "Lettura automatica non riuscita: inserisci i valori a mano nella pagina Dati."
    return "Lettura automatica eseguita: %d campi letti, %d non trovati." % (len(rep["letti"]), len(rep["non_trovati"]))


def _carica(cart, pc, files):
    if not files:
        raise dp.ErroreDati("Scegli almeno un file PDF.")
    if not pr._prima_di(pc, "NUMERI_VERIFICATI"):
        raise pr.ErrorePratica("Il registro è bloccato perché la pratica è avanzata: riaprila dalla vista avanzata.")
    hashes = {r["sha256"] for r in pr._leggi(pc, "registro", []) if r.get("sha256")}
    esiti = []
    for nome, dati in files:
        nome_s = Path(nome or "").name
        if not nome_s.lower().endswith(".pdf") or not dati.startswith(b"%PDF"):
            esiti.append("%s: non è un PDF valido" % (nome_s or "file"))
            continue
        h = hashlib.sha256(dati).hexdigest()
        if h in hashes:
            esiti.append("%s: già presente (stesso contenuto)" % nome_s)
            continue
        dest = cart / re.sub(r"[^A-Za-z0-9._-]", "_", nome_s)
        k = 1
        while dest.exists():   # non si sovrascrive mai un documento
            dest = dest.with_name("%s_%d%s" % (dest.stem.rsplit("_", 1)[0] if k > 1 else dest.stem, k, dest.suffix))
            k += 1
        dest.write_bytes(dati)
        tipo = dp.riconosci_tipo_pdf(dest)
        with dp.modifica(pc, "documento caricato"):
            riga = pr.registra_documento(pc, dest.name, dest, tipo, None, None, "STORICO")
        hashes.add(h)
        if tipo == "bilancio":
            rep = dp.estrai_bilancio(pc, cart, riga["id"])
            esiti.append("%s: bilancio, %s" % (dest.name, _testo_rep(rep)))
        else:
            esiti.append("%s: registrato come '%s' (dati da inserire a mano)" % (dest.name, tipo))
    return "Caricamento: " + "; ".join(esiti)
