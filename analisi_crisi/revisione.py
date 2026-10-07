"""Tabella di revisione: un file HTML autonomo, apribile con un doppio clic. Contiene i valori."""
from html import escape
from pathlib import Path

_STILE = """
body{font:14px -apple-system,Helvetica,Arial,sans-serif;margin:24px;color:#1a1a1a;background:#fff}
h1{font-size:20px} h2{font-size:16px;margin-top:28px}
table{border-collapse:collapse;width:100%} th,td{border:1px solid #ccc;padding:5px 8px;text-align:left;vertical-align:top}
th{background:#f0f0f0} td.num{text-align:right;white-space:nowrap;font-variant-numeric:tabular-nums}
.stato{font-weight:600;white-space:nowrap}
.FATTO{background:#e3f4e3} .INFERENZA{background:#fff3cd} .DA-VERIFICARE{background:#fbdcdc}
.OK{background:#e3f4e3} .KO{background:#fbdcdc} .NON-ESEGUIBILE{background:#eee}
.letto{font-family:Menlo,monospace;font-size:12px;color:#444}
button{margin-right:6px;padding:4px 10px} .riquadro{background:#eef4fb;border:1px solid #b9cfe8;padding:6px 12px;margin:10px 0;line-height:1.6} .riquadro .stato{padding:1px 6px} .avviso{background:#fff3cd;padding:8px;border:1px solid #e0c97a;margin:4px 0}
"""

_SCRIPT = """
function salvaApprovazioni(){var a=[];document.querySelectorAll('input.appr:checked').forEach(function(c){a.push(c.dataset.cella);});
var d={documento:document.body.dataset.documento,approvate:a};
var l=document.createElement('a');l.href=URL.createObjectURL(new Blob([JSON.stringify(d,null,1)],{type:'application/json'}));
l.download=document.body.dataset.stem+'_approvazioni.json';l.click();}
function filtra(stato){document.querySelectorAll('tr[data-stato]').forEach(function(r){
r.style.display=(!stato||r.dataset.stato===stato)?'':'none';});}
"""


def _importo(v):
    if v is None:
        return ""
    if isinstance(v, float):
        testo = f"{abs(v):,.2f}".replace(",", "§").replace(".", ",").replace("§", ".")
    else:
        testo = f"{abs(v):,}".replace(",", ".")
    return ("-" if v < 0 else "") + testo


def _classe(stato):
    return stato.replace(" ", "-")


def _tabella_foglio(r):
    colonne = sorted({c for riga in r["foglio"] for c in riga["celle"]})
    testa = "<tr><th>Riga</th><th>Voce</th>" + "".join(f"<th>Col. {c}</th><th>Stato {c}</th>" for c in colonne) + "<th>Note</th></tr>"
    righe = []
    for riga in sorted(r["foglio"], key=lambda x: x["riga"]):
        celle = [riga["celle"].get(c) for c in colonne]
        note = " ".join(dict.fromkeys(n for c in celle if c for n in c["note"]))
        def _casella(col, c):
            if c["stato"] != "DA VERIFICARE" or c["valore"] is None:
                return ""
            return f" <label><input type=checkbox class=appr data-cella=\"{col}{riga['riga']}\"> approvato</label>"
        corpo = "".join(
            f"<td class=num>{_importo(c['valore'])}</td><td class=\"stato {_classe(c['stato'])}\">{c['stato']}{_casella(col, c)}</td>" if c else "<td></td><td></td>"
            for col, c in zip(colonne, celle)
        )
        righe.append(f"<tr><td>{riga['riga']}</td><td>{escape(riga['voce'])}</td>{corpo}<td>{escape(note)}</td></tr>")
    return f"<table>{testa}{''.join(righe)}</table>"


def _tabella_dati(dati):
    righe = []
    for d in dati:
        dest = d["destinazione"]
        cella = "—" if dest is None else f"col. {dest['colonna'] or '?'} · riga {dest['riga'] or '?'}"
        righe.append(
            f"<tr data-stato=\"{escape(d['stato'])}\"><td>{escape(d['voce'])}</td><td>{escape(d['esercizio'] or '?')}</td>"
            f"<td class=num>{_importo(d['valore'])}</td><td class=\"stato {_classe(d['stato'])}\">{escape(d['stato'])}</td>"
            f"<td>{d['fonte']['pagina'] or ''}</td><td class=letto>{escape(d['fonte']['testo_letto'] or '')}</td>"
            f"<td>{escape(cella)}</td><td>{escape(' '.join(d['note']))}</td></tr>"
        )
    testa = "<tr><th>Voce</th><th>Esercizio</th><th>Valore</th><th>Stato</th><th>Pag.</th><th>Testo letto</th><th>Destinazione</th><th>Note</th></tr>"
    return f"<table>{testa}{''.join(righe)}</table>"


def _riquadro(r):
    """Riepilogo in parole semplici: esito dei controlli e significato dei colori."""
    controlli = r.get("controlli", [])
    eseguiti = [c for c in controlli if c["esito"] in ("OK", "KO")]
    ok = sum(1 for c in eseguiti if c["esito"] == "OK")
    if not eseguiti:
        esito = "Nessun controllo aritmetico eseguibile: verifica gli importi sul documento."
    elif ok == len(eseguiti):
        esito = f"<b>Controlli aritmetici: {ok} su {len(eseguiti)} quadrano.</b> Se un importo fosse finito nella riga sbagliata, i totali non quadrerebbero: di norma non serve altro."
    else:
        esito = f"<b>Attenzione: {len(eseguiti) - ok} controlli su {len(eseguiti)} NON quadrano.</b> Verifica gli importi indicati in rosso nei controlli."
    return (
        "<div class=riquadro><p>" + esito + "</p>"
        "<p><span class='stato FATTO'>FATTO</span> letto direttamente dal documento. "
        "<span class='stato INFERENZA'>INFERENZA</span> calcolato da più voci (es. somma) o dedotto: controlla se ti torna. "
        "<span class='stato DA-VERIFICARE'>DA VERIFICARE</span> voce non trovata o dubbia: <b>non viene scritta in Excel</b> "
        "(una cella vuota in Excel vale zero) finché non la approvi con la casella.</p></div>"
    )


def html_revisione(r: dict) -> str:
    doc = r["documento"]
    parti = [
        f"<h1>Revisione — {escape(doc['file'])}</h1>",
        f"<p>Tipo: {escape(doc['tipo'])} · pagine: {doc['pagine']} · esito: <b>{escape(r['esito'])}</b></p>",
    ]
    parti += [f"<div class=avviso>{escape(a)}</div>" for a in r["avvisi"]]
    parti.append(_riquadro(r))
    if r["dati"]:
        parti += ["<h2>Celle di flussi_cassa_impresa (solo righe di input)</h2>",
                  "<p>Le celle DA VERIFICARE si scrivono in Excel solo se spuntate. "
                  "<button onclick=\"salvaApprovazioni()\">Salva approvazioni</button> (file locale, senza valori)</p>",
                  _tabella_foglio(r)]
        parti.append(
            "<h2>Voci lette dal documento</h2>"
            "<p>Mostra: <button onclick=\"filtra('')\">Tutto</button><button onclick=\"filtra('FATTO')\">FATTO</button>"
            "<button onclick=\"filtra('INFERENZA')\">INFERENZA</button><button onclick=\"filtra('DA VERIFICARE')\">DA VERIFICARE</button></p>"
        )
        parti.append(_tabella_dati(r["dati"]))
        if r["residui"]:
            parti += ["<h2>Residui (fuori dalle celle)</h2>", _tabella_dati(r["residui"])]
        parti += ["<h2>Totali e voci di solo controllo (mai scritti nell'Excel)</h2>", _tabella_dati(r["controllo"])]
        righe = "".join(
            f"<tr><td>{escape(c['nome'])}</td><td>{escape(c['esercizio'] or '?')}</td><td class=\"stato {_classe(c['esito'])}\">{c['esito']}</td>"
            f"<td class=num>{_importo(c['atteso'])}</td><td class=num>{_importo(c['ricalcolato'])}</td></tr>"
            for c in r["controlli"]
        )
        parti.append(f"<h2>Controlli aritmetici</h2><table><tr><th>Controllo</th><th>Esercizio</th><th>Esito</th><th>Nel documento</th><th>Ricalcolato</th></tr>{righe}</table>")
        if r["righe_non_mappate"]:
            righe = "".join(f"<tr><td>{x['pagina']}</td><td class=letto>{escape(x['testo'])}</td></tr>" for x in r["righe_non_mappate"])
            parti.append(f"<h2>Voci numerate non mappate</h2><table><tr><th>Pag.</th><th>Testo letto</th></tr>{righe}</table>")
    return (
        f"<!doctype html><html lang=it><head><meta charset=utf-8><title>Revisione {escape(doc['file'])}</title>"
        f"<style>{_STILE}</style></head><body data-documento='{escape(doc['file'])}' data-stem='{escape(Path(doc['file']).stem)}'>{''.join(parti)}<script>{_SCRIPT}</script></body></html>"
    )
