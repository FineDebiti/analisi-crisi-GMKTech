"""Rapporto di diagnostica SENZA VALORI: solo voci trovate/mancanti, stati, pagine, esiti dei controlli."""
import re
from collections import Counter


class RapportoConValori(Exception):
    """Il rapporto conterrebbe un importo o un testo letto dal documento: non va scritto."""


def rapporto(r: dict, nome_documento: str | None = None) -> str:
    """nome_documento va passato solo per i PDF sintetici; per i file reali resta omesso."""
    doc = r["documento"]
    righe = [
        "# Rapporto di diagnostica (senza valori)",
        "",
        f"- Documento: {nome_documento or '(nome omesso)'}",
        f"- Tipo: {doc['tipo']}",
        f"- Pagine: {doc['pagine']}, di cui con testo estraibile: {len(doc['pagine_con_testo'])}",
        f"- Esito: {r['esito']}",
        f"- Esercizi riconosciuti: {len(r['esercizi'])}",
    ]
    if r.get("regimi"):
        righe.append("- Quadri di reddito riconosciuti: " + ", ".join(r["regimi"]))
    tutti = r["dati"] + r["residui"] + r["controllo"]
    if tutti:
        stati = Counter(d["stato"] for d in tutti)
        righe.append("- Stati delle voci: " + ", ".join(f"{s} = {stati.get(s, 0)}" for s in ("FATTO", "INFERENZA", "DA VERIFICARE")))
        righe += ["", "## Celle di flussi_cassa_impresa", "", "| Riga | Voce | Col. | Compilata | Stato |", "|---|---|---|---|---|"]
        for riga in r["foglio"]:
            for col, c in sorted(riga["celle"].items()):
                righe.append(f"| {riga['riga']} | {riga['voce']} | {col} | {'sì' if c['valore'] is not None else 'no'} | {c['stato']} |")
        righe += ["", "## Voci", "", "| Chiave | Voce | Uso | Anno | Trovata | Stato | Pag. |", "|---|---|---|---|---|---|---|"]
        for uso, dati in (("excel", r["dati"]), ("residuo", r["residui"]), ("controllo", r["controllo"])):
            for d in dati:
                trovata = "sì" if d["fonte"]["pagina"] else "no"
                anno = d["anno"] if d["anno"] is not None else "—"
                righe.append(f"| {d['chiave']} | {d['voce']} | {uso} | {anno} | {trovata} | {d['stato']} | {d['fonte']['pagina'] or ''} |")
        if r["voci_facoltative_assenti"]:
            righe += ["", "Voci facoltative assenti: " + ", ".join(r["voci_facoltative_assenti"])]
        righe += ["", "## Controlli aritmetici", "", "| Controllo | Anno | Esito |", "|---|---|---|"]
        righe += [f"| {c['nome']} | {c['anno'] if c['anno'] is not None else '—'} | {c['esito']} |" for c in r["controlli"]]
        per_pagina = Counter(x["pagina"] for x in r["righe_non_mappate"])
        righe += ["", "## Righe non usate", ""]
        righe.append(f"- Voci numerate del conto economico non mappate: {len(r['righe_non_mappate'])}"
                     + (" (" + ", ".join(f"pag. {p} = {n}" for p, n in sorted(per_pagina.items())) + ")" if per_pagina else ""))
        righe.append(f"- Righe di dettaglio ignorate: {r['righe_di_dettaglio_ignorate']}")
    righe += ["", f"## Avvisi: {len(r['avvisi'])}", ""]
    testo = "\n".join(righe) + "\n"
    verifica_senza_valori(testo, r)
    return testo


def verifica_senza_valori(testo: str, r: dict):
    """Rifiuta il testo se contiene un importo estratto (da 100 in su) o un testo letto dal PDF."""
    tutti = r.get("dati", []) + r.get("residui", []) + r.get("controllo", [])
    for d in tutti:
        letto = d["fonte"]["testo_letto"]
        if letto and letto in testo:
            raise RapportoConValori("testo letto dal documento presente nel rapporto")
    importi = {d["valore"] for d in tutti} | {c.get(k) for c in r.get("controlli", []) for k in ("atteso", "ricalcolato")}
    importi |= {c["valore"] for riga in r.get("foglio", []) for c in riga["celle"].values()}
    # Modello Aziende ed estratti di ruolo: valori numerici e testi letti (creditori, numeri di documento).
    testi = []
    for riga in r.get("modello_aziende", []):
        for c in riga["celle"].values():
            if isinstance(c["valore"], str):
                testi.append(c["valore"])
            else:
                importi.add(c["valore"])
    for d in r.get("documenti", []):
        testi += [d.get("numero"), d.get("ente_letto"), d.get("testo_letto")] + [e["descrizione"] for e in d.get("enti", [])]
        importi |= set(d.get("totali", {}).values()) | set(d.get("importi_letti", []))
        importi |= {x[k] for x in d.get("righe", []) for k in ("carico", "sgravio", "pagato", "residuo")}
    for t in testi:
        if t and len(t) >= 6 and t in testo:
            raise RapportoConValori("testo letto dal documento presente nel rapporto")
    for v in importi:
        if v is None or abs(v) < 100:
            continue
        for forma in {str(int(abs(v))), f"{int(abs(v)):,}".replace(",", ".")}:
            if re.search(rf"(?<![\d.]){re.escape(forma)}(?![\d.])", testo):
                raise RapportoConValori("importo estratto presente nel rapporto")
    for x in r.get("righe_non_mappate", []):
        if x["testo"] in testo:
            raise RapportoConValori("riga del documento presente nel rapporto")
