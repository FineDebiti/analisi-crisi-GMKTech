"""Relazione di preanalisi v3 (modello CNC): corpo di 4-5 pagine + appendici, da un file caso_v3.json.

Uso:  python relazione_v3.py --caso caso_v3.json --out Relazione.docx [--modello Template.docx] [--anonimizza --legenda legenda.json]

Il file caso_v3.json è prodotto da un 'costruttore' per ciascun caso (legge i JSON dei parser e le informazioni lette
dai documenti, ciascuna con fonte, data e pagina). Il motore NON assegna da solo il giudizio finale e NON classifica
automaticamente la natura della crisi: formatta, calcola le grandezze derivate (normalizzazioni, riconciliazioni,
indicatori) e verifica la coerenza interna. I giudizi sono dell'analista e passano dall'Human Gate (HG-2).
"""
from __future__ import annotations

import html
import json
import re
import sys
from pathlib import Path

from analisi_crisi import word_xml as w

PROGETTO = Path(__file__).resolve().parent
ND = "non disponibile"
COL = {"VERDE": "VERDE", "GIALLO": "GIALLO", "ROSSO": "ROSSO", "ND": None, None: None}
ETICHETTA = {"VERDE": "● VERDE", "GIALLO": "● GIALLO", "ROSSO": "● ROSSO", None: "○ NON CONCLUDENTE"}


# ---------------------------------------------------------------- formattazione
def eur(v, segno=False):
    if v is None:
        return ND
    t = f"{abs(round(v)):,}".replace(",", ".")
    s = "-" if v < 0 and round(v) != 0 else ("+" if segno and v > 0 else "")
    return f"{s}€ {t}"


def pct(v, c=1):
    return ND if v is None else f"{v * 100:.{c}f}".replace(".", ",") + "%"


def rap(v):
    return ND if v is None else f"{v:.1f}".replace(".", ",") + "x"


def data_it(iso):
    return ND if not iso else f"{iso[8:10]}/{iso[5:7]}/{iso[:4]}"


# ---------------------------------------------------------------- calcoli
def normalizza(base, righe):
    """base: {'ricavi','ebitda'}; righe: [{'voce','d_ebitda','d_ricavi',...}]. d_* None = non quantificabile (non entra nel totale).
    Restituisce righe con progressivi e il risultato; 'incompleta' se almeno una rettifica non e' quantificabile."""
    e, r = base["ebitda"], base["ricavi"]
    out, incompleta = [], False
    for x in righe:
        de, dr = x.get("d_ebitda"), x.get("d_ricavi")
        if de is None and dr is None and x.get("quantificabile", True) is False:
            incompleta = True
            out.append({**x, "e": None, "r": None, "m": None, "non_quantificata": True})
            continue
        e += de or 0
        r += dr or 0
        out.append({**x, "e": e, "r": r, "m": (e / r) if r else None, "non_quantificata": False})
    return {"righe": out, "ebitda": e, "ricavi": r, "margine": (e / r) if r else None, "incompleta": incompleta,
            "margine_base": (base["ebitda"] / base["ricavi"]) if base["ricavi"] else None}


def rapporto_semplificato(debito, liquidita, flusso):
    """Indicatore SEMPLIFICATO interno: (debiti - liquidita') / EBITDA. NON e' il test pratico ministeriale (decreto dirigenziale
    23/04/2026), che usa il debito da servire A e i flussi annui B con voci incluse/dedotte specifiche. Le fasce 1, 3 e 5 sono
    quelle indicative del decreto, qui applicate per solo riferimento. Ritorna (debito_netto, rapporto, fascia)."""
    if debito is None or liquidita is None:
        return None, None, "non determinabile"
    netto = debito - liquidita
    if flusso is None or flusso <= 0:
        return netto, None, "flusso non positivo o non disponibile"
    r = netto / flusso
    return netto, r, ("<= 1" if r <= 1 else ("tra 1 e 3" if r <= 3 else ("tra 3 e 5" if r <= 5 else "> 5")))


rapporto_test_pratico = rapporto_semplificato   # alias per compatibilita' con le versioni precedenti (v3/1)

VOCI_TEST_MINISTERIALE = [
    ("A - debito da servire (incluso)", "debito scaduto di ogni natura; debito non corrente fuori dall'ordinaria gestione; debito ristrutturato o rateizzato; debito finanziario anche da leasing; esborsi attesi per TFR oltre gli accantonamenti", "elenco per posizione con scadenze"),
    ("A - debito da servire (dedotto)", "disponibilità liquide utilizzabili; attività finanziarie realizzabili; versamenti dei soci impegnati; crediti non ordinari entro il realizzo", "liquidità utilizzabile e impegni documentati"),
    ("B - flussi annui (base)", "EBITDA normalizzato corrente (o dell'anno precedente se più affidabile), senza componenti straordinarie e con l'effetto pieno delle misure già attuate", "situazione contabile corrente"),
    ("B - flussi annui (dedotto)", "investimenti di mantenimento; imposte annue; interessi su linee escluse dal debito A; ricavi infragruppo problematici", "libro cespiti, piano investimenti, dichiarazioni"),
]


def scheda_test_ministeriale(disponibili=None, numero="A9"):
    """Scheda 'test pratico ministeriale' (decreto dirigenziale 23/04/2026): NON ESEGUITO se mancano le voci di A e B."""
    disponibili = disponibili or {}
    righe = [["Esito", "NON ESEGUITO: dati mancanti. Nessun rapporto ministeriale è attribuito; l'indicatore semplificato non lo sostituisce."],
             ["Riferimento", "Decreto dirigenziale Min. Giustizia 23/04/2026 (Bollettino Ufficiale n. 10, 31/05/2026): rapporto A/B, indicazione di massima, fasce 1, 3 e 5."]]
    for etichetta, testo, doc in VOCI_TEST_MINISTERIALE:
        righe.append([etichetta, f"{testo}. Documento necessario: {doc}. Disponibile: {disponibili.get(doc, 'no')}."])
    return {"titolo": f"{numero}. Test pratico ministeriale (decreto 23/04/2026)", "esito": None, "righe": righe}


def scheda_test_ministeriale_calcolato(a_incluse, a_dedotte, b_base, b_dedotte, natura, fonte, numero="A9"):
    """Test pratico ministeriale ESEGUITO (decreto 23/04/2026): A = debito da servire (voci incluse meno voci dedotte), B = flussi annui
    (base meno deduzioni). Ogni voce e' (etichetta, importo). Fasce indicative 1, 3 e 5."""
    A = sum(v for _, v in a_incluse) - sum(v for _, v in a_dedotte)
    B = b_base[1] - sum(v for _, v in b_dedotte)
    r = (A / B) if B > 0 else None
    fascia = None if r is None else ("<= 1" if r <= 1 else ("tra 1 e 3" if r <= 3 else ("tra 3 e 5" if r <= 5 else "> 5")))
    righe = [["Formula", "A / B (decreto dirigenziale 23/04/2026): prognostico, non diagnostico"]]
    righe += [[f"A (+) {e}", eur(v)] for e, v in a_incluse] + [[f"A (-) {e}", eur(-v)] for e, v in a_dedotte]
    righe += [["A - debito da servire", eur(A)], [f"B (+) {b_base[0]}", eur(b_base[1])]] + [[f"B (-) {e}", eur(-v)] for e, v in b_dedotte]
    righe += [["B - flussi annui", eur(B)], ["Rapporto A/B", rap(r)], ["Fascia indicativa (1, 3, 5)", fascia or "non determinabile"],
              ["Natura e documento", f"{natura}; {fonte}"]]
    return {"titolo": f"{numero}. Test pratico ministeriale (decreto 23/04/2026)", "esito": None, "righe": righe, "A": A, "B": B, "rapporto": r}


def somma(righe, col=1):
    v = [r[col] for r in righe if isinstance(r[col], (int, float))]
    return sum(v) if v else None


def scheda(titolo, num_l, num, den_l, den, formula, natura, fonte, parametro, esito, motivazione, fmt="pct"):
    val = (num / den) if num is not None and den else None
    f = (lambda v: pct(v, 1)) if fmt == "pct" else rap
    return {"titolo": titolo, "esito": esito, "righe": [
        ["Valore assoluto", f"{num_l}: {eur(num)}\n{den_l}: {eur(den)}"], ["Indicatore", f(val)], ["Formula", formula],
        ["Natura e data del dato", natura], ["Documento e pagina", fonte], ["Parametro interno di screening", parametro],
        ["Esito", ETICHETTA[COL[esito]] if esito else "non valutabile"], ["Motivazione", motivazione if val is not None else "Non valutabile: dato mancante. L'assenza del dato non è un giudizio negativo."]]}


# ---------------------------------------------------------------- impaginazione
L_TOT = 9700


def _t(righe, larg, **kw):
    return w.tabella(righe, larg, dim=16, **kw)


def _breve(t, n=170):
    """Prima frase del testo, al massimo n caratteri (il testo completo e' in appendice)."""
    f = t.split(". ")[0].rstrip(".") + "."
    return f if len(f) <= n else f[:n].rsplit(" ", 1)[0] + "..."


def corpo_principale(c):
    P = []
    s = c["soggetto"]
    P.append(w.par(w.run("RELAZIONE DI PREANALISI ECONOMICO-FINANZIARIA", True, "365F91", 30), "Corpo", dopo=20))
    P.append(w.testo(f"{s['nome']} - {s['forma']} - {s['stato']}", dim=21, grassetto=True, dopo=20))
    P.append(w.testo(f"Elaborazione del {data_it(c['elaborazione'])}. Supporto alla decisione, non attestazione. Ogni dato è marcato FATTO (letto in un documento), "
                     "INFERENZA (dedotto da fatti), IPOTESI (non verificata) o DA VERIFICARE. Un dato mancante è scritto \"non disponibile\" e non è mai sostituito da zero.", dim=16, corsivo=True, dopo=60))
    # 1. Conclusione
    k = c["conclusioni"]
    P.append(w.h1("1. Conclusione: sostenibilità, qualità dei dati, fattibilità"))
    righe = [["Giudizio", "Esito", "Motivazione"]]
    colori = {}
    for i, (chiave, nome) in enumerate((("sostenibilita", "Allerta finanziaria / sostenibilità sui dati storici"), ("qualita_dati", "Qualità dei dati"), ("fattibilita", "Fattibilità di un risanamento")), 1):
        g = k[chiave]
        righe.append([nome, g["titolo"], g["testo"]])
        colori[(i, 1)] = COL[g["colore"]]
    P.append(_t(righe, [1800, 2000, 5900], colori=colori))
    P.append(w.misto([("Stato della conclusione: ", True), (k["stato"], False)], dim=18, dopo=30))
    if k.get("corrente"):
        P.append(w.misto([("Sostenibilità corrente: ", True), (k["corrente"], False)], dim=18, dopo=30))
    if k.get("vicini"):
        P.append(w.testo(k["vicini"], dim=17, corsivo=True, dopo=30))
    P.append(w.testo(k["premessa_non_automatica"], dopo=40))
    P.append(w.misto([("Cosa serve per concludere: ", True), (k["serve"], False)], dim=18, dopo=40))
    # 2. Base documentale
    P.append(w.h1("2. Base documentale: acquisizione, data del documento, periodo economico"))
    r = [["Documento", "Acquisizione", "Data documento", "Periodo economico", "Natura del dato"]]
    for d in c["documenti"]:
        r.append([d["nome"], d["acquisizione"], d["data_doc"], d["periodo"], d["natura"]])
    P.append(_t(r, [3300, 1150, 1850, 1700, 1700]))
    P.append(w.testo(c["documenti_nota"], dim=17, dopo=40))
    # 3. Cause
    P.append(w.h1("3. Cause della crisi ricostruite dalle evidenze"))
    r = [["Causa", "Evidenza", "Stato", "Fonte"]] + [list(x) for x in c["cause"]]
    P.append(_t(r, [1900, 4900, 1500, 1400]))
    P.append(w.testo(c["cause_nota"], dim=17, dopo=40))
    # 4. Normalizzazione
    P.append(w.h1("4. Normalizzazione del margine operativo e effetto di ogni rettifica"))
    for n in c["normalizzazioni"]:
        N = normalizza(n["base"], n["righe"])
        n["_N"] = N
        P.append(w.h2(n["titolo"]))
        r = [["Passaggio", "Effetto su EBITDA", "EBITDA progress.", "Ricavi progress.", "Margine", "Stato"]]
        r.append([n["base"]["etichetta"], "-", eur(n["base"]["ebitda"]), eur(n["base"]["ricavi"]), pct(N["margine_base"]), n["base"]["stato"]])
        for x in N["righe"]:
            if x["non_quantificata"]:
                r.append([x["voce"], ND, ND, ND, ND, x["stato"]])
            else:
                r.append([x["voce"], eur(x.get("d_ebitda"), True) if x.get("d_ebitda") is not None else eur(0) if x.get("d_ricavi") is not None else ND,
                          eur(x["e"]), eur(x["r"]), pct(x["m"]), x["stato"]])
        r.append([n["esito_etichetta"], "-", eur(N["ebitda"]), eur(N["ricavi"]), pct(N["margine"]), n["esito_stato"]])
        P.append(_t(r, [3300, 1300, 1300, 1250, 1000, 1550], destra=(1, 2, 3, 4), grassetto_righe=(len(r) - 1,)))
        P.append(w.testo(n["impatto"], dim=17, dopo=40))
    # 5. Debito
    d = c["debiti"]
    P.append(w.h1(f"5. Massa passiva: riconciliazione per creditore e posizione - {d['stato']}"))
    r = [["Creditore / posizione", "Importo", "Data e natura", "Riscontro nei ruoli", "Stato"]] + [[x[0], eur(x[1]), x[2], x[3], x[4]] for x in d["righe"]]
    tot = somma(d["righe"])
    r.append(["Totale delle posizioni", eur(tot), d["data"], f"Bilancio: {eur(d['totale_bilancio'])}; differenza {eur(tot - d['totale_bilancio'] if tot is not None and d['totale_bilancio'] is not None else None)}", "FATTO"])
    P.append(_t(r, [3000, 1250, 2000, 2300, 1150], destra=(1,), grassetto_righe=(len(r) - 1,)))
    if d.get("riconciliazione"):
        r = [d.get("riconciliazione_colonne") or ["Classe", "Scritture contabili", "Estratti di ruolo", "Differenza", "Lettura"]]
        for x in d["riconciliazione"]:
            r.append([x[0], eur(x[1]), eur(x[2]), eur(x[1] - x[2]) if x[1] is not None and x[2] is not None else ND, x[3]])
        P.append(_t(r, [1700, 1400, 1400, 1300, 3900], destra=(1, 2, 3)))
    P.append(w.testo(d["lettura"], dim=17, dopo=30))
    P.append(w.misto([("Possibili omissioni: ", True), (d["omissioni"], False)], dim=17, dopo=20))
    P.append(w.misto([("Possibili duplicazioni: ", True), (d["duplicazioni"], False)], dim=17, dopo=40))
    # 6. Patrimonio
    p = c["patrimonio"]
    P.append(w.h1("6. Adeguatezza del patrimonio (non solo segno)"))
    r = [["Elemento", "Valore", "Lettura"]] + [[x[0], x[1], x[2]] for x in p["righe"]]
    P.append(_t(r, [3300, 1700, 4700], destra=(1,)))
    P.append(w.testo(p["giudizio"], dim=17, dopo=40))
    # 7. Scenari
    sc = c["scenari"]
    P.append(w.h1("7. Scenari omogenei"))
    P.append(w.testo(sc["intestazione"], dim=17, dopo=30))
    r = [["Scenario", "Patrimonio considerato", "Flussi", "Fabbisogno", "Costi", "Indicatore", "Esito"]] + [list(x) for x in sc["righe"]]
    P.append(_t(r, [1450, 1500, 1250, 1350, 1100, 1350, 1700]))
    P.append(w.testo(sc["nota"], dim=17, dopo=40))
    if c.get("tesoreria"):
        t = c["tesoreria"]
        P.append(w.h2(t["titolo"]))
        for tab in t["tabelle"]:
            P.append(_t([tab["intestazione"]] + tab["righe"], tab["larghezze"], destra=tuple(range(1, len(tab["intestazione"]))), grassetto_righe=tuple(tab.get("grassetto", ()))))
        P.append(w.testo(t["nota"], dim=17, dopo=40))
    # 8. Norme
    P.append(w.h1("8. Quadro normativo e parametri"))
    r = [["Riferimento", "Contenuto e uso nel caso (sintesi; testo completo in App. E)", "Verifica del testo"]] + [[x[0], _breve(x[1]), x[2]] for x in c["normativa"]]
    P.append(_t(r, [2900, 4900, 1900]))
    P.append(w.testo(c["parametri_nota"], dim=17, dopo=40))
    # 9. Mancanti
    P.append(w.h1("9. Dati mancanti e loro effetto sul giudizio"))
    r = [["Dato mancante", "Perché serve", "Effetto sul giudizio"]] + [list(x) for x in c["mancanti"]]
    P.append(_t(r, [2600, 3300, 3800]))
    return P


def appendici(c):
    P = [w.par(w.run("APPENDICI", True, "365F91", 30), "Corpo", dopo=60, salto=True)]
    P.append(w.h1("A. Schede degli indicatori di screening"))
    P.append(w.testo(c["schede_nota"], dim=17, dopo=60))
    for s in c["schede"]:
        P.append(w.h2(s["titolo"]))
        colori = {(7, 1): COL.get(s["esito"])} if s.get("esito") and len(s["righe"]) > 6 else {}
        P.append(_t([["Voce", "Contenuto"]] + s["righe"], [2300, 7400], colori={}))
    P.append(w.h1("B. Parametri interni di screening e formule"))
    P.append(w.testo("Non sono soglie di legge: sono parametri interni del professionista, usati per ordinare l'attenzione. Una loro modifica è una decisione del professionista (HG-2). "
                     "Nessun parametro determina da solo la conclusione.", dim=17))
    P.append(_t([["Parametro", "Valore", "Natura"]] + [list(x) for x in c["parametri"]], [4700, 2500, 2500]))
    P.append(w.h1("C. Normalizzazioni: note di dettaglio"))
    for n in c["normalizzazioni"]:
        P.append(w.testo(n["dettaglio"], dim=17, dopo=60))
    P.append(w.h1("E. Quadro normativo: testo completo"))
    P.append(_t([["Riferimento", "Contenuto e uso nel caso", "Verifica del testo"]] + [list(x) for x in c["normativa"]], [2300, 5300, 2100]))
    P.append(w.h1("D. Fonti"))
    for f in c["fonti"]:
        P.append(w.par(w.run("• " + f, dim=16), "Corpo", dopo=10, line=240))
    return P


# ---------------------------------------------------------------- controlli e uscita
def controlla(testo_xml):
    """Nessuna variabile non risolta, nessun None/nan nel documento."""
    visibile = re.sub(r"<[^>]+>", " ", testo_xml)
    errori = re.findall(r"\{[a-zA-Z_][a-zA-Z_0-9]*\}", visibile)
    errori += re.findall(r"\b(None|nan|NaN|undefined)\b", visibile)
    if errori:
        raise RuntimeError("segnaposto non risolti: " + ", ".join(sorted(set(errori))))


def mappa_anonima(c):
    mp, n = {}, 0
    for k, pref in (("nome", "SOCIETA"),):
        n += 1
        mp[c["soggetto"][k]] = f"{pref}-01"
    for i, x in enumerate(c.get("anonimizza", []), 1):
        mp.setdefault(x, f"RIF-{i:02d}")
    return mp


def applica_anonimato(xml, mp):
    for orig in sorted(mp, key=len, reverse=True):
        for forma in {orig, html.escape(orig, quote=False)}:
            xml = re.sub(re.escape(forma), mp[orig], xml, flags=re.IGNORECASE)
    residui = [o for o in mp if re.search(re.escape(o), xml, re.IGNORECASE)]
    if residui:
        raise RuntimeError(f"anonimizzazione incompleta: {len(residui)} termini ancora presenti")
    return xml


def costruisci(c):
    xml = "".join(corpo_principale(c)) + "".join(appendici(c))
    controlla(xml)
    return xml


def main(argv):
    def arg(n, d=None):
        return argv[argv.index(n) + 1] if n in argv else d
    if not (arg("--caso") and arg("--out")):
        print(__doc__)
        return 2
    c = json.loads(Path(arg("--caso")).read_text(encoding="utf-8"))
    xml = costruisci(c)
    if "--anonimizza" in argv:
        mp = mappa_anonima(c)
        xml = applica_anonimato(xml, mp)
        lg = Path(arg("--legenda"))
        if lg.exists():
            raise FileExistsError(lg.name)
        lg.write_text(json.dumps({v: k for k, v in mp.items()}, ensure_ascii=False, indent=1), encoding="utf-8")
    w.salva(arg("--modello", PROGETTO / "Template_Preanalisi_Economico-Finanziaria_CNC.docx"), xml, arg("--out"), a4=True)
    print("Relazione scritta:", Path(arg("--out")).name)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
