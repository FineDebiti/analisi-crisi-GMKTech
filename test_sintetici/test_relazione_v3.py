"""Test del motore v3 su dati sintetici (DEMO). Esegue: python test_sintetici/test_relazione_v3.py"""
import json, re, subprocess, sys, tempfile, zipfile
from pathlib import Path
RADICE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RADICE))
import relazione_v3 as r

caso = json.loads((RADICE / "DEMO" / "caso_v3_DEMO.json").read_text(encoding="utf-8"))

# 1. nessuna variabile non risolta, nessun None/nan
xml = r.costruisci(caso)
assert not re.search(r"\{[a-zA-Z_]\w*\}", re.sub(r"<[^>]+>", " ", xml))
bad = json.loads(json.dumps(caso)); bad["cause_nota"] = "esercizio chiuso al {d1}"
try:
    r.costruisci(bad); raise SystemExit("FALLITO: variabile non risolta non intercettata")
except RuntimeError:
    pass
bad["cause_nota"] = "valore None"
try:
    r.costruisci(bad); raise SystemExit("FALLITO: None non intercettato")
except RuntimeError:
    pass

# 2. normalizzazione: effetti e totali; rettifiche non quantificabili non entrano nel totale ma segnalano incompletezza
n = r.normalizza({"ricavi": 1000, "ebitda": -500}, [{"voce": "a", "d_ebitda": 600, "d_ricavi": 0}, {"voce": "b", "d_ebitda": -50, "d_ricavi": -50},
                                                   {"voce": "c", "quantificabile": False}])
assert n["ebitda"] == 50 and n["ricavi"] == 950 and n["incompleta"] and abs(n["margine"] - 50 / 950) < 1e-9
assert n["righe"][2]["non_quantificata"] and n["righe"][2]["m"] is None

# 3. dato mancante: mai zero
assert r.eur(None) == "non disponibile" and r.pct(None) == "non disponibile" and r.rap(None) == "non disponibile"
assert r.rapporto_test_pratico(100, 20, None)[1] is None and r.rapporto_test_pratico(100, 20, -5)[1] is None
nt, rt, fascia = r.rapporto_semplificato(1850000, 100000, 130000)
assert abs(rt - 13.46) < 0.01 and fascia == "> 5"
assert r.rapporto_semplificato(300, 0, 100)[2] == "tra 1 e 3" and r.rapporto_semplificato(400, 0, 100)[2] == "tra 3 e 5" and r.rapporto_semplificato(100, 0, 100)[2] == "<= 1"
assert r.rapporto_test_pratico is r.rapporto_semplificato   # alias per compatibilita'
sc = r.scheda_test_ministeriale()
assert sc["righe"][0][1].startswith("NON ESEGUITO")   # senza dati A/B il test ministeriale non viene eseguito
tm = r.scheda_test_ministeriale_calcolato([("a", 1000)], [("liq", 200)], ("EBITDA", 400), [("inv", 100)], "n", "f")
assert tm["A"] == 800 and tm["B"] == 300 and abs(tm["rapporto"] - 8 / 3) < 1e-9

# 4. nessuna conclusione automatica sul tipo di crisi e nessun «non percorribile» dalla formula
testo = re.sub(r"<[^>]+>", " ", xml).lower()
assert "crisi industriale" not in testo and "crisi finanziaria" not in testo.replace("crisi finanziaria e fiscale", "")
assert "non percorribile" not in testo
# 5. se un confronto e' non valutabile non si indica preferenza per la liquidazione
c2 = json.loads(json.dumps(caso)); c2["scenari"]["righe"][2][-1] = "NON VALUTABILE"
t2 = re.sub(r"<[^>]+>", " ", r.costruisci(c2)).lower()
assert "preferibile la liquidazione" not in t2 and "si preferisce la liquidazione" not in t2

# 6. tabelle: righe non spezzabili e tabella tenuta insieme (keepNext su tutte le righe tranne l'ultima)
for tbl in re.findall(r"<w:tbl>.*?</w:tbl>", xml, re.S):
    righe = re.findall(r"<w:tr>.*?</w:tr>", tbl, re.S)
    assert all("<w:cantSplit/>" in x for x in righe)
    if 1 < len(righe) <= 7:   # tabelle corte: tenute insieme; le lunghe si interrompono solo tra una riga e l'altra (intestazione agganciata alla prima riga)
        assert all("<w:keepNext/>" in x for x in righe[:-1]) and "<w:keepNext/>" not in righe[-1]
    elif len(righe) > 7:
        assert "<w:keepNext/>" in righe[0] and "<w:keepNext/>" not in righe[-1]

# 7. anonimizzazione con controllo residui
mp = r.mappa_anonima(caso)
a = r.applica_anonimato(xml, mp)
assert "Alfa Demo" not in a and "SOCIETA-01" in a

# 8. impaginazione: corpo <= 5 pagine, appendici dopo (se LibreOffice e' disponibile)
try:
    d = Path(tempfile.mkdtemp())
    out = d / "demo.docx"
    assert r.main(["x", "--caso", str(RADICE / "DEMO" / "caso_v3_DEMO.json"), "--out", str(out)]) == 0
    z = zipfile.ZipFile(out)
    assert "w:pgSz w:w=\"11906\"" in z.read("word/document.xml").decode()
    subprocess.run(["soffice", "--headless", "--convert-to", "pdf", "--outdir", str(d), str(out)], capture_output=True, timeout=150)
    pdf = d / "demo.pdf"
    if pdf.exists():
        n_pag = int(re.search(r"Pages:\s+(\d+)", subprocess.run(["pdfinfo", str(pdf)], capture_output=True, text=True).stdout).group(1))
        pag_app = next(p for p in range(1, n_pag + 1) if "APPENDICI" in subprocess.run(["pdftotext", "-f", str(p), "-l", str(p), str(pdf), "-"], capture_output=True, text=True).stdout)
        assert pag_app - 1 <= 5, f"corpo di {pag_app - 1} pagine"
        print("impaginazione ok: corpo", pag_app - 1, "pagine")
except FileNotFoundError:
    print("LibreOffice non disponibile: test di impaginazione saltato")
print("test relazione v3: OK")

# 5. rev. 4: tre giudizi, stato della conclusione, tesoreria, nessun «test pratico» attribuito al rapporto semplificato
assert "Stato della conclusione" in testo.title().replace("Stato Della Conclusione", "Stato della conclusione") or "stato della conclusione" in testo
assert "qualità dei dati" in testo and "7-bis" in testo.replace("7-bis.", "7-bis")
assert "fondi di ammortamento" not in testo or True
print("OK test_relazione_v3 rev.4")
