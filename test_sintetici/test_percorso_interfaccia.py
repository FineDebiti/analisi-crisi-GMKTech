"""Percorso completo dell'interfaccia a livello HTTP, come farebbe il browser (urllib, cookie, multipart). SOLO dati sintetici.

Nessun file toccato a mano: pratica -> PDF -> registro -> dati estratti -> inserimento e correzione -> preanalisi -> approvazione -> PDF
-> modifica che fa decadere l'approvazione -> rigenera e riapprova -> riavvio del server -> persistenza.
"""
import http.cookiejar
import io
import json
import re
import sys
import tempfile
import threading
import urllib.error
import urllib.parse
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

QUI = Path(__file__).resolve().parent
sys.path.insert(0, str(QUI.parent))
sys.path.insert(0, str(QUI))

import genera_pdf_demo as gpd  # noqa: E402
import interfaccia_locale as il  # noqa: E402
from analisi_crisi import pratica as pr  # noqa: E402


class Browser:
    def __init__(self, base):
        self.base = base
        self.jar = http.cookiejar.CookieJar()
        self.op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))

    def _esegui(self, req):
        try:
            with self.op.open(req) as r:
                return r.status, r.read(), r.headers
        except urllib.error.HTTPError as e:
            return e.code, e.read(), e.headers

    def get(self, path):
        return self._esegui(urllib.request.Request(self.base + path))

    def testo(self, path):
        s, b, _ = self.get(path)
        return s, b.decode("utf-8", "replace")

    def post(self, path, dati):
        s, b, _ = self._esegui(urllib.request.Request(self.base + path, data=urllib.parse.urlencode(dati).encode(), method="POST"))
        return s, b.decode("utf-8", "replace")

    def carica(self, path, files, extra=None):
        conf = "----DEMO"
        corpo = b""
        for k, v in (extra or {}).items():
            corpo += ("--%s\r\nContent-Disposition: form-data; name=\"%s\"\r\n\r\n%s\r\n" % (conf, k, v)).encode()
        for nome, dati in files:
            corpo += ("--%s\r\nContent-Disposition: form-data; name=\"pdf\"; filename=\"%s\"\r\nContent-Type: application/pdf\r\n\r\n" % (conf, nome)).encode() + dati + b"\r\n"
        corpo += ("--%s--\r\n" % conf).encode()
        s, b, _ = self._esegui(urllib.request.Request(self.base + path, data=corpo, method="POST", headers={"Content-Type": "multipart/form-data; boundary=" + conf}))
        return s, b.decode("utf-8", "replace")


def avvia(radice):
    il.CONFIG = il.PROGETTO / "config_motore.json"
    il.STATO.update(radice=Path(radice), pin=None)
    srv = ThreadingHTTPServer(("127.0.0.1", 0), il.H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, "http://127.0.0.1:%d" % srv.server_address[1]


def testo_pdf(byte):
    import pdfplumber
    with pdfplumber.open(io.BytesIO(byte)) as doc:
        return " ".join((p.extract_text() or "") for p in doc.pages)


def campi_dati(**kv):
    """Modulo della pagina Dati: valori per codice campo (testo come lo scriverebbe l'operatore)."""
    f = {"operatore": "Avv. Rossi"}
    for k, v in kv.items():
        if isinstance(v, tuple):
            f["v_" + k], f["d_" + k], f["g_" + k], f["s_" + k] = v
        else:
            f["v_" + k] = v
    return f


def test_percorso_completo():
    with tempfile.TemporaryDirectory() as tmp:
        radice, pdfdir = Path(tmp) / "casi", Path(tmp) / "pdf"
        radice.mkdir()
        gpd.genera(pdfdir)
        srv, base = avvia(radice)
        b = Browser(base)
        try:
            # 0. pagina iniziale: "Come si usa", elenco vuoto
            s, h = b.testo("/")
            assert s == 200 and "Come si usa" in h and h.count("<li>") == 5 and "Nuova pratica" in h
            # 1. creazione pratica DEMO (con nome ostile: tutto con escape)
            s, h = b.post("/pratiche/nuova", {"nome": "DEMO", "procedura": "CNC", "operatore": "Avv. Rossi"})
            assert s == 200 and "Pratica creata" in h and "Procedura: CNC" in h and "NON APPROVATA" in h
            assert b.post("/pratiche/nuova", {"nome": "DEMO", "procedura": "CNC"})[0] == 400                     # nome già usato
            assert b.post("/pratiche/nuova", {"nome": "X", "procedura": "BOH"})[0] == 400
            s, h = b.post("/pratiche/nuova", {"nome": "<b>ostile</b>", "procedura": "LC"})
            assert s == 200 and "<b>ostile</b>" not in h and "&lt;b&gt;ostile&lt;/b&gt;" in h
            # 2. caricamento di 3 PDF in una volta, poi uno alla volta
            files = [(f.name, f.read_bytes()) for f in sorted(pdfdir.glob("*.pdf"))]
            assert b.carica("/p/DEMO/carica", [], {"operatore": "Avv. Rossi"})[0] == 400                        # nessun file: messaggio comprensibile
            s, h = b.carica("/p/DEMO/carica", files[:2], {"operatore": "Avv. Rossi"})                           # altro_demo + bilancio_demo insieme
            assert s == 200 and "Caricamento" in h and "bilancio_demo.pdf" in h
            s, h = b.carica("/p/DEMO/carica", files[2:], {"operatore": "Avv. Rossi"})                           # visura da sola
            assert s == 200 and "visura_demo.pdf" in h
            s, h = b.carica("/p/DEMO/carica", files[:1], {})
            assert "già presente" in h                                                                          # stesso contenuto: non si duplica
            assert b.carica("/p/DEMO/carica", [("falso.pdf", b"non un pdf")], {})[1].count("non è un PDF valido") >= 1
            # 3. registro: id, nome, tipo, hash, data di acquisizione, data documento, periodo, natura
            s, h = b.testo("/p/DEMO/registro")
            assert s == 200 and re.search(r"[0-9a-f]{64}", h) and "Hash SHA-256" in h and "Acquisito il" in h and "Data documento" in h and "Periodo" in h and "Natura" in h
            reg = json.loads((radice / "DEMO" / "PRATICA" / "registro_documentale.json").read_text(encoding="utf-8"))
            assert len(reg) == 3 and {r["tipo"] for r in reg} == {"bilancio", "visura", "altro"}
            assert all(r["data_acquisizione"] and r["sha256"] for r in reg)
            idb = next(r["id"] for r in reg if r["tipo"] == "bilancio")
            assert next(r for r in reg if r["id"] == idb)["periodo_economico"] == "2025"                         # dal parser
            idv = next(r["id"] for r in reg if r["tipo"] == "visura")
            s, h = b.post("/p/DEMO/documento", {"id": str(idv), "tipo": "visura", "data_documento": "15/01/2026", "periodo": "2026", "natura": "AGGIORNATO"})
            assert s == 200 and "15/01/2026" in h
            assert b.post("/p/DEMO/documento", {"id": str(idv), "tipo": "visura", "data_documento": "31/02/2026", "natura": "STORICO"})[0] == 400
            s, h = b.post("/p/DEMO/mancante", {"nome_mancante": "Estratto di ruolo", "tipo": "ruolo", "decisivo": "on"})
            assert s == 200 and "NON DISPONIBILE" in h and "Estratto di ruolo" in h
            s, h = b.post("/p/DEMO/checklist", {"s_A4": "mancante", "s_B1": "da aggiornare", "operatore": "Avv. Rossi"})
            assert s == 200 and "Stati aggiornati" in h
            # 4. dati estratti: origine automatica e nota onesta
            s, h = b.testo("/p/DEMO/dati")
            assert s == 200 and h.count("Estratto automaticamente") >= 7 and "Lettura automatica: solo il BILANCIO" in h and "NON sono letti automaticamente" in h
            assert "non disponibile" in h and "FATTO" in h
            dv = json.loads((radice / "DEMO" / "PRATICA" / "dati_valori.json").read_text(encoding="utf-8"))["campi"]
            assert dv["ricavi"]["valore"] == 1250000 and dv["ricavi"]["origine"] == "AUTO" and dv["ricavi"]["pagina"] == 3 and dv["totale_attivo"]["id_documento"] == idb
            assert "debiti_pubblici" not in dv and "liquidita_utilizzabile" not in dv                              # mai inventati
            # 5. inserimento manuale: formato italiano, vuoto = non disponibile (mai zero)
            s, h = b.post("/p/DEMO/dati", campi_dati(debiti_pubblici="12abc"))
            assert s == 400 and "non è un numero valido" in h
            s, h = b.post("/p/DEMO/dati", {**campi_dati(debiti_pubblici=("150.000,50", str(idb), "3", "FATTO"), liquidita_utilizzabile=("30.000", "", "", "DA VERIFICARE"),
                                                         debiti_bancari="200.000"), "n_debiti_pubblici": "somma letta a mano"})
            assert s == 200 and "Dati salvati: 3" in h and "Inserito dall&#x27;operatore" in h and "150.000,50" in h
            assert b.post("/p/DEMO/dati", campi_dati(crediti_soci=("5.000", "", "", "FATTO")))[0] == 400            # FATTO senza documento
            assert b.post("/p/DEMO/dati", campi_dati(operatore=""))[0] in (200, 400)
            dv = json.loads((radice / "DEMO" / "PRATICA" / "dati_valori.json").read_text(encoding="utf-8"))["campi"]
            assert "crediti_soci" not in dv and dv["debiti_pubblici"]["valore"] == 150000.5 and dv["debiti_pubblici"]["origine"] == "OPERATORE"
            met = json.loads((radice / "DEMO" / "PRATICA" / "metriche.json").read_text(encoding="utf-8"))               # generato dal sistema
            assert met["crediti_soci_su_attivo"] is None and abs(met["margine"] - 146000 / 1250000) < 1e-9 and met["pubblici_su_attivo"] is not None
            assert abs(met["rapporti"]["EBITDA ultimo esercizio"] - (497000 - 30000) / 146000) < 1e-9
            # 6. correzione di un valore: storico (precedente, autore, data) nel verbale a catena
            s, h = b.post("/p/DEMO/dati", campi_dati(patrimonio_netto=("210.000", str(idb), "2", "FATTO")))
            assert s == 200 and "Dati salvati: 1" in h
            s, h = b.testo("/p/DEMO/dati")
            assert "Corretto dall&#x27;operatore" in h and "Valore precedente: 206.300" in h and "Avv. Rossi" in h
            pc = radice / "DEMO" / "PRATICA"
            verb = json.loads((pc / "verbale.json").read_text(encoding="utf-8"))
            assert any(r["controllo"] == "DATO DECISIVO" and "206.300 -> 210.000" in r["dettaglio"] and "Avv. Rossi" in r["dettaglio"] for r in verb)
            assert pr.verifica_verbale(pc)["ok"]
            # 7. preanalisi: prima non c'è nulla da scaricare
            assert b.get("/p/DEMO/preanalisi.pdf")[0] == 404
            s, h = b.post("/p/DEMO/avvia", {"operatore": "Avv. Rossi"})
            assert s == 200 and "Preanalisi provvisoria prodotta" in h
            for t in ("Allerta finanziaria / sostenibilità sui dati storici", "Qualità dei dati", "Fattibilità", "Stato della conclusione", "Sufficienza per iniziare", "Sufficienza per concludere"):
                assert "<h3>%s</h3>" % t in h, t
            assert h.count("<div class='rq ") == 6 and "Richieste documentali prioritarie (massimo 5)" in h and "NON APPROVATA" in h and "Limiti informativi" in h
            assert "<tr><td>6</td>" not in h
            # PDF della bozza
            s, pdf, hd = b.get("/p/DEMO/preanalisi.pdf")
            assert s == 200 and pdf.startswith(b"%PDF") and "application/pdf" in hd["Content-Type"]
            t = testo_pdf(pdf)
            assert "PREANALISI PROVVISORIA" in t and "NON APPROVATA - bozza" in t and "Preanalisi Crisi v1.0-pilota" in t and "Impronta parametri" in t
            # 8. approvazione come provvisoria
            assert b.post("/p/DEMO/approva", {"titolare": " "})[0] == 400
            s, h = b.post("/p/DEMO/approva", {"titolare": "Avv. Bianchi"})
            assert s == 200 and "<span class='bd A'>APPROVATA</span>" in h and "Avv. Bianchi" in h
            t = testo_pdf(b.get("/p/DEMO/preanalisi.pdf")[1])
            assert "APPROVATA COME PROVVISORIA da Avv. Bianchi" in t and "NON APPROVATA" not in t
            assert list(pc.glob("Preanalisi_provvisoria_*.docx")) and "Scarica il Word" in h
            # 9. modifica di un dato decisivo: l'approvazione decade e lo si vede
            s, h = b.post("/p/DEMO/dati", campi_dati(patrimonio_netto=("215.000", str(idb), "2", "FATTO")))
            assert s == 200
            s, h = b.testo("/p/DEMO/preanalisi")
            assert "<span class='bd N'>NON APPROVATA</span>" in h and "DECADUTA" in h and "I dati sono cambiati dopo l'ultima preanalisi" in h
            s, pdf, _ = b.get("/p/DEMO/preanalisi.pdf")
            t = testo_pdf(pdf)
            assert "NON APPROVATA - bozza" in t and "decaduta" in t and "dati sono stati modificati" in t
            s, h = b.post("/p/DEMO/approva", {"titolare": "Avv. Bianchi"})
            assert s == 400 and "I dati sono cambiati" in h                                                       # va rigenerata prima
            assert any(r["controllo"] == "APPROVAZIONE DECADUTA" for r in json.loads((pc / "verbale.json").read_text(encoding="utf-8")))
            # rigenera e riapprova
            assert b.post("/p/DEMO/avvia", {})[0] == 200
            s, h = b.post("/p/DEMO/approva", {"titolare": "Avv. Bianchi"})
            assert s == 200 and "<span class='bd A'>APPROVATA</span>" in h
            # incongruenza SOSTANZIALE: decade; gestione completa dalla schermata
            s, h = b.post("/p/DEMO/inc_aggiungi", {"descrizione": "Totali che non tornano", "gravita": "SOSTANZIALE"})
            assert s == 200 and "Totali che non tornano" in h and "NON APPROVATA" in h
            assert b.post("/p/DEMO/inc_risolvi", {"id": "1", "nota": ""})[0] == 400
            s, h = b.post("/p/DEMO/inc_risolvi", {"id": "1", "nota": "Verificato col cliente"})
            assert s == 200 and "Verificato col cliente" in h and "Riapri" in h
            assert b.post("/p/DEMO/inc_riapri", {"id": "1", "nota": "Dubbio nuovo"})[0] == 200
            assert b.post("/p/DEMO/inc_risolvi", {"id": "1", "nota": "Chiarito"})[0] == 200
            s, h = b.post("/p/DEMO/rich_aggiungi", {"richiesta": "Estratti conto 2025", "perche": "Riscontro con CR", "priorita": "1", "destinatario": "Cliente"})
            assert s == 200 and "Estratti conto 2025" in h and "1 - alta" in h
            s, h = b.post("/p/DEMO/rich_stato", {"id": "1", "stato": "INVIATA"})
            assert s == 200 and "INVIATA" in h
            assert b.post("/p/DEMO/avvia", {})[0] == 200
            assert "<span class='bd A'>APPROVATA</span>" in b.post("/p/DEMO/approva", {"titolare": "Avv. Bianchi"})[1]
            (radice / "stato.txt").write_text("ok")
        finally:
            srv.shutdown()
            srv.server_close()
        # 10. riavvio del server: tutto è ancora li'
        srv, base = avvia(radice)
        b = Browser(base)
        try:
            s, h = b.testo("/")
            assert "DEMO" in h and "APPROVATA" in h and "CNC" in h
            s, h = b.testo("/p/DEMO/registro")
            assert "bilancio_demo.pdf" in h and "visura_demo.pdf" in h and "altro_demo.pdf" in h and "Estratto di ruolo" in h and "15/01/2026" in h
            s, h = b.testo("/p/DEMO/dati")
            assert "Corretto dall&#x27;operatore" in h and "215.000" in h and "Valore precedente: 210.000" in h and "Estratto automaticamente" in h and "Inserito dall&#x27;operatore" in h
            s, h = b.testo("/p/DEMO/incongruenze")
            assert "Chiarito" in h and "Estratti conto 2025" in h and "INVIATA" in h
            s, h = b.testo("/p/DEMO/preanalisi")
            assert "<span class='bd A'>APPROVATA</span>" in h and "Avv. Bianchi" in h and h.count("<div class='rq ") == 6
            t = testo_pdf(b.get("/p/DEMO/preanalisi.pdf")[1])
            assert "APPROVATA COME PROVVISORIA" in t and "NON APPROVATA" not in t
            assert pr.verifica_verbale(radice / "DEMO" / "PRATICA")["ok"]
            # la vista avanzata resta raggiungibile
            assert b.get("/caso/DEMO")[0] == 200
        finally:
            srv.shutdown()
            srv.server_close()


def test_bozze_incongruenze_e_fascicolo_vuoto():
    with tempfile.TemporaryDirectory() as tmp:
        radice = Path(tmp) / "casi"
        radice.mkdir()
        srv, base = avvia(radice)
        b = Browser(base)
        try:
            b.post("/pratiche/nuova", {"nome": "VUOTA", "procedura": "LC", "operatore": "T"})
            # nessun blocco per fascicolo incompleto: preanalisi subito, senza documenti e senza dati
            s, h = b.post("/p/VUOTA/avvia", {})
            assert s == 200 and "Ricognizione del fascicolo" in h
            met = json.loads((radice / "VUOTA" / "PRATICA" / "metriche.json").read_text(encoding="utf-8"))
            assert met["margine"] is None and met["rapporti"] == {} and met["pn_su_attivo"] is None                   # nessuno zero inventato
            # valori incoerenti -> bozza di incongruenza da confermare
            s, h = b.post("/p/VUOTA/dati", campi_dati(totale_attivo="100.000", patrimonio_netto="80.000", debiti_totali="60.000"))
            assert s == 200
            s, h = b.testo("/p/VUOTA/incongruenze")
            assert "Proposte dell'applicazione" in h and "Conferma come incongruenza" in h
            s, h = b.post("/p/VUOTA/inc_aggiungi", {"descrizione": "Il totale attivo è inferiore a patrimonio netto + debiti: il totale attivo non può essere minore (verificare i valori).", "gravita": "SOSTANZIALE"})
            assert s == 200 and "Proposte dell'applicazione" not in h
            # errori comprensibili e percorsi
            assert b.get("/p/NONESISTE/dati")[0] == 404 and b.get("/p/..%2Fx/dati")[0] in (400, 404)
            assert b.post("/p/VUOTA/dati", campi_dati(ricavi="1.2.3"))[0] == 400
        finally:
            srv.shutdown()
            srv.server_close()


def prova():
    for nome, f in sorted(globals().items()):
        if nome.startswith("test_"):
            f()
            print("OK", nome)


if __name__ == "__main__":
    prova()
