"""Test del semaforo v3 (tre dimensioni, dati decisivi mancanti => conclusione non definitiva). python test_sintetici/test_semaforo_v3.py"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from analisi_crisi import semaforo_v3 as sv
from analisi_crisi import semaforo as v2      # la v2 resta importabile e invariata
assert hasattr(v2, "valuta")

docs_ok = [{"nome": f"d{i}", "disponibile": True, "aggiornato": True} for i in range(5)]
base = {"margine": 0.10, "rapporti": {"a": 2.0}, "pn_su_attivo": 0.2, "pubblici_su_attivo": 0.03, "cassa_verificata": True}

# 1. tutto buono e nessun dato mancante: sostenibilita' VERDE, qualita' ALTA, conclusione definitiva
r = sv.valuta_v3(base, docs_ok, [{"nome": "x", "disponibile": True}], scenari_tutti_valutabili=True, esito_scenari="sufficiente")
assert r["sostenibilita"]["colore"] == "VERDE" and r["qualita_dati"]["livello"] == "ALTA" and r["definitiva"] and r["fattibilita"]["esito"] == "PERCORRIBILE"

# 2. un dato decisivo mancante: conclusione NON definitiva, mai PERCORRIBILE ne' NON PERCORRIBILE
for esito in ("sufficiente", "insufficiente", None):
    r = sv.valuta_v3(base, docs_ok, [{"nome": "tesoreria", "disponibile": False}], scenari_tutti_valutabili=True, esito_scenari=esito)
    assert not r["definitiva"] and r["fattibilita"]["esito"] in ("NON CONCLUDENTE", "CONDIZIONATA") and "NON DEFINITIVA" in r["stato"]
    assert r["qualita_dati"]["livello"] in ("BASSA", "INSUFFICIENTE")
r = sv.valuta_v3(base, docs_ok, [{"nome": "t", "disponibile": False}], percorso_ipotizzabile=True)
assert r["fattibilita"]["esito"] == "CONDIZIONATA"

# 3. rapporto sul flusso PIU' PRUDENTE: il migliore non basta
m = {**base, "rapporti": {"normalizzato": 2.5, "contabile": 8.0}}
assert sv.sostenibilita(m)["colore"] == "ROSSO"
m = {**base, "rapporti": {"normalizzato": 2.5, "contabile": 4.0}}
assert sv.sostenibilita(m)["colore"] == "GIALLO"

# 4. flusso non positivo: ROSSO; dato mancante: NON ROSSO per effetto dell'assenza (colore ND se nessun criterio determinante)
assert sv.sostenibilita({**base, "flusso_non_positivo": True})["colore"] == "ROSSO"
assert sv.sostenibilita({"margine": None, "rapporti": {}, "pn_su_attivo": None})["colore"] == "ND"

# 5. EBITDA non e' cassa: il criterio cassa e' NON VERIFICATO se manca la tesoreria e non entra nel colore
c = [x for x in sv.sostenibilita({**base, "cassa_verificata": False})["criteri"] if x["codice"] == "cassa"][0]
assert "NON VERIFICATO" in c["nota"] and c["colore"] is None

# 6. qualita': documenti non disponibili => INSUFFICIENTE
q = sv.qualita_dati([{"nome": "a", "disponibile": False}, {"nome": "b", "disponibile": False}, {"nome": "c", "disponibile": True, "aggiornato": True}], [])
assert q["livello"] == "INSUFFICIENTE"

# 7. fasce del rapporto
assert [sv.fascia_rapporto(x) for x in (0.5, 2, 4, 9, None)] == ["<=1", "1-3", "3-5", ">5", None]
# 8. soglie sui valori NON arrotondati e segnalazione dei valori prossimi
b = {**base, "rapporti": {"n": 5.0036}}
r1 = sv.sostenibilita(b); assert r1["colore"] == "ROSSO" and r1["vicini"] and "5,0036" in r1["testo_vicini"]
assert sv.sostenibilita({**base, "rapporti": {"n": 4.9999}})["colore"] == "GIALLO"
assert sv.sostenibilita({**base, "rapporti": {"n": 2.0}})["vicini"] == []
# 9. etichetta: il rosso e' un'allerta prudenziale sui dati storici; la sostenibilita' corrente e' non verificata senza situazione corrente
assert "PRUDENZIALE" in r1["etichetta"] and r1["corrente"].startswith("NON VERIFICATA")
assert sv.sostenibilita({**base, "corrente_verificata": True})["corrente"] == "VERIFICATA"
# 10. dataset simulato: dicitura dedicata
rs = sv.valuta_v3(base, docs_ok, [], scenari_tutti_valutabili=True, esito_scenari="sufficiente", dataset_simulato=True)
assert rs["stato"].startswith("VALUTAZIONE COMPLETA sul dataset simulato")
print("OK test_semaforo_v3")
