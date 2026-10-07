"""Test dell'interfaccia locale con dati FITTIZI (nessun dato reale)."""
import json
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

import genera_ruoli_fittizio as gen  # noqa: E402
import interfaccia_locale as il  # noqa: E402
import test_relazione as tr  # noqa: E402


def _avvia(radice, pin=None):
    il.STATO.update(radice=Path(radice), pin=pin)
    srv = ThreadingHTTPServer(("127.0.0.1", 0), il.H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}"


def _post(url, dati, cookie=None):
    req = urllib.request.Request(url, data=urllib.parse.urlencode(dati).encode(), method="POST")
    if cookie:
        req.add_header("Cookie", cookie)
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def _get(url, cookie=None):
    req = urllib.request.Request(url)
    if cookie:
        req.add_header("Cookie", cookie)
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def _upload(url, nome, dati):
    b = "XXBORDOXX"
    corpo = (f"--{b}\r\nContent-Disposition: form-data; name=\"pdf\"; filename=\"{nome}\"\r\nContent-Type: application/pdf\r\n\r\n").encode() + dati + f"\r\n--{b}--\r\n".encode()
    req = urllib.request.Request(url, data=corpo, method="POST", headers={"Content-Type": f"multipart/form-data; boundary={b}"})
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def test_flusso_completo_e_sicurezza():
    with tempfile.TemporaryDirectory() as tmp:
        srv, base = _avvia(tmp)
        try:
            assert _get(base + "/")[0] == 200
            assert _post(base + "/nuovo", {"nome": "../fuori"})[0] == 400  # nome non valido
            assert _post(base + "/nuovo", {"nome": "CasoProva"})[0] == 200
            assert (Path(tmp) / "CasoProva").is_dir()
            pdf = Path(tmp) / "r.pdf"
            gen.genera(pdf)
            assert _upload(base + "/caso/CasoProva/carica", "ruoli_fittizi.pdf", b"non un pdf")[0] == 400
            s, _ = _upload(base + "/caso/CasoProva/carica", "ruoli fittizi.pdf", pdf.read_bytes())
            assert s == 200
            s, _ = _upload(base + "/caso/CasoProva/carica", "ruoli fittizi.pdf", pdf.read_bytes())  # stesso nome: non si sovrascrive
            assert len(list((Path(tmp) / "CasoProva").glob("*.pdf"))) == 2
            nome_pdf = sorted(p.name for p in (Path(tmp) / "CasoProva").glob("*.pdf"))[0]
            s, corpo = _post(base + "/caso/CasoProva/estrai", {"pdf": nome_pdf, "tipo": "ruoli"})
            assert s == 200 and "Estrazione eseguita" in corpo
            assert list((Path(tmp) / "CasoProva" / "_estratti").glob("*_ruoli.json"))
            # Percorsi fuori dal caso rifiutati
            assert _get(base + "/caso/CasoProva/file/../../etc/passwd")[0] in (400, 404)
            assert _post(base + "/caso/CasoProva/estrai", {"pdf": "../../etc/passwd", "tipo": "ruoli"})[0] in (400,)
            # Relazione da un bilancio fittizio
            est = Path(tmp) / "CasoProva" / "_estratti"
            (est / "bilancio_fittizio.json").write_text(json.dumps(tr._bilancio()), encoding="utf-8")
            ruoli = next(est.glob("*_ruoli.json")).name
            s, corpo = _post(base + "/caso/CasoProva/relazione", {"bilancio": "bilancio_fittizio.json", "ruoli": ruoli, "nome": "Alfa Test", "cr": "on", "anon": "on"})
            assert s == 200 and "Generati" in corpo, corpo[:300]
            assert len(list((Path(tmp) / "CasoProva" / "CASO").glob("Relazione_*.docx"))) == 2
        finally:
            srv.shutdown()


def test_pin_obbligatorio():
    with tempfile.TemporaryDirectory() as tmp:
        srv, base = _avvia(tmp, pin="4321")
        try:
            assert b"PIN" in _get(base + "/")[1] and _get(base + "/")[0] == 200  # solo la pagina di accesso
            assert _post(base + "/nuovo", {"nome": "X"})[0] == 401
            assert _post(base + "/login", {"pin": "0000"})[0] == 403
            req = urllib.request.Request(base + "/login", data=b"pin=4321", method="POST")
            class NoRedir(urllib.request.HTTPRedirectHandler):
                def redirect_request(self, *a, **k):
                    return None
            try:
                urllib.request.build_opener(NoRedir).open(req)
            except urllib.error.HTTPError as e:
                cookie = e.headers["Set-Cookie"].split(";")[0]
            assert _post(base + "/nuovo", {"nome": "Y"}, cookie)[0] == 200
        finally:
            srv.shutdown()


def _config(tmp, valore):
    c = Path(tmp) / "config_test.json"
    c.write_text(json.dumps({"semaforo": valore}), encoding="utf-8")
    return c


def _pratica_http(base, tmp, pin_cookie=None):
    """Caso con pratica aperta, registro e due numeri decisivi (uno con nome ostile), stato NUMERI_IN_VERIFICA."""
    from analisi_crisi import pratica as pr
    assert _post(base + "/nuovo", {"nome": "CasoPr"}, pin_cookie)[0] == 200
    cart = Path(tmp) / "CasoPr"
    (cart / "bil.pdf").write_bytes(b"%PDF-1.4 sintetico")
    s, corpo = _post(base + "/caso/CasoPr/pratica/apri", {"nome": "Tester", "simulato": "on"}, pin_cookie)
    assert s == 200 and "Pratica aperta" in corpo
    pc = cart / "PRATICA"
    assert _post(base + "/caso/CasoPr/pratica/registra", {"pdf": "bil.pdf", "tipo": "bilancio", "natura": "STORICO", "periodo": "2025"}, pin_cookie)[0] == 200
    assert _post(base + "/caso/CasoPr/pratica/registra", {"pdf": "../../etc/passwd", "natura": "STORICO"}, pin_cookie)[0] == 400
    pr.aggiungi_incongruenza(pc, "<script>alert(1)</script>", ["x"], "MINORE")
    pr.proponi_numeri_decisivi(pc, [{"nome": "EBITDA \"><img src=x onerror=alert(2)>", "valore": 100, "unita": "EUR", "fonte": "doc 1 p.3"}, {"nome": "Debito", "valore": 200}])
    assert _post(base + "/caso/CasoPr/pratica/avanza", {"a": "CONSOLIDATA", "nome": "T"}, pin_cookie)[0] == 400   # a salti: rifiutato
    assert _post(base + "/caso/CasoPr/pratica/avanza", {"a": "REGISTRO_PRONTO", "nome": "T"}, pin_cookie)[0] == 200
    assert _post(base + "/caso/CasoPr/pratica/avanza", {"a": "NUMERI_IN_VERIFICA", "nome": "T"}, pin_cookie)[0] == 200
    (pc / "metriche.json").write_text(json.dumps({"margine": 0.10, "rapporti": {"a": 2.0}, "pn_su_attivo": 0.2, "pubblici_su_attivo": 0.03, "cassa_verificata": True}), encoding="utf-8")
    return pc


def test_pannello_pratica_gate_e_quattro_riquadri():
    with tempfile.TemporaryDirectory() as tmp:
        il.CONFIG = _config(tmp, "v3")
        (Path(tmp) / "casi").mkdir()
        srv, base = _avvia(Path(tmp) / "casi")
        try:
            pc = _pratica_http(base, Path(tmp) / "casi")
            pagina = _get(base + "/caso/CasoPr")[1].decode()
            assert "Valutazione non prodotta: attende la verifica dei numeri decisivi" in pagina
            assert "class='rq" not in pagina and "Qualità dei dati" not in pagina and "<h3>Fattibilità</h3>" not in pagina
            assert "Preanalisi Crisi v1.0-pilota" in pagina and "/file/PRATICA/verbale.json" in pagina and "verbale integro" in pagina
            assert pagina.count("<button>Conferma</button>") == 2
            # valutazione rifiutata dal server prima della conferma
            s, corpo = _post(base + "/caso/CasoPr/pratica/valuta", {})
            assert s == 409 and not (pc / "valutazione_v3.json").exists()
            # prospetto: disponibile prima del gate
            s, corpo = _post(base + "/caso/CasoPr/pratica/prospetto", {})
            assert s == 200 and list(pc.glob("Prospetto_preconclusivo_*.docx"))
            # conferma: serve il nome
            assert _post(base + "/caso/CasoPr/pratica/conferma", {"id": "1", "nome": "  "})[0] == 400
            assert _post(base + "/caso/CasoPr/pratica/conferma", {"id": "1", "nome": "Avv. Prova"})[0] == 200
            assert _post(base + "/caso/CasoPr/pratica/conferma", {"id": "2", "nome": "Avv. Prova", "corretto_a": "210"})[0] == 200
            assert _post(base + "/caso/CasoPr/pratica/avanza", {"a": "NUMERI_VERIFICATI", "nome": "T"})[0] == 200
            assert "Valutazione non prodotta" not in _get(base + "/caso/CasoPr")[1].decode()
            assert _post(base + "/caso/CasoPr/pratica/valuta", {})[0] == 200
            pagina = _get(base + "/caso/CasoPr")[1].decode()
            assert pagina.count("<div class='rq ") == 4
            titoli = ["Allerta finanziaria / sostenibilità sui dati storici", "Qualità dei dati", "Fattibilità", "Stato della conclusione"]
            pos = [pagina.index(f"<h3>{t}</h3>") for t in titoli]
            assert pos == sorted(pos)
            assert "Sostenibilità corrente:" in pagina and "NON DEFINITIVA" not in pagina.split("Fattibilità")[0]
            assert "Impronta dei parametri" in pagina
            # escape HTML di ogni valore
            assert "<script>alert(1)</script>" not in pagina and "&lt;script&gt;alert(1)&lt;/script&gt;" in pagina
            assert "<img src=x" not in pagina and "&lt;img src=x" in pagina
            # riapertura: il pannello torna bloccato
            assert _post(base + "/caso/CasoPr/pratica/riapri", {"a_stato": "NUMERI_IN_VERIFICA", "motivo": "nuovo dato", "nome": "Avv. Prova"})[0] == 200
            from analisi_crisi import pratica as pr
            pr.proponi_numeri_decisivi(pc, [{"nome": "Nuovo", "valore": 1}])
            assert "Valutazione non prodotta" in _get(base + "/caso/CasoPr")[1].decode()
        finally:
            srv.shutdown()
            il.CONFIG = il.PROGETTO / "config_motore.json"


def test_ripristino_config_v2():
    with tempfile.TemporaryDirectory() as tmp:
        il.CONFIG = _config(tmp, "v2")
        (Path(tmp) / "casi").mkdir()
        srv, base = _avvia(Path(tmp) / "casi")
        try:
            assert _post(base + "/nuovo", {"nome": "CasoV2"})[0] == 200
            pagina = _get(base + "/caso/CasoV2")[1].decode()
            assert "<h2>Pratica</h2>" not in pagina and "Valutazione" not in pagina and "<h2>3. Relazione di preanalisi</h2>" in pagina
            assert _post(base + "/caso/CasoV2/pratica/apri", {"nome": "T"})[0] == 404
            assert not (Path(tmp) / "casi" / "CasoV2" / "PRATICA").exists()
        finally:
            srv.shutdown()
            il.CONFIG = il.PROGETTO / "config_motore.json"


def test_pratica_con_pin_e_persistenza_dopo_riavvio():
    with tempfile.TemporaryDirectory() as tmp:
        il.CONFIG = _config(tmp, "v3")
        (Path(tmp) / "casi").mkdir()
        casi = Path(tmp) / "casi"
        srv, base = _avvia(casi, pin="4321")
        try:
            assert _post(base + "/caso/X/pratica/apri", {"nome": "T"})[0] == 401    # senza PIN: rifiutato
            req = urllib.request.Request(base + "/login", data=b"pin=4321", method="POST")
            class NoRedir(urllib.request.HTTPRedirectHandler):
                def redirect_request(self, *a, **k):
                    return None
            try:
                urllib.request.build_opener(NoRedir).open(req)
            except urllib.error.HTTPError as e:
                cookie = e.headers["Set-Cookie"].split(";")[0]
            pc = _pratica_http(base, casi, cookie)
            assert _post(base + "/caso/CasoPr/pratica/conferma", {"id": "1", "nome": "Avv"})[0] == 401
            assert _post(base + "/caso/CasoPr/pratica/conferma", {"id": "1", "nome": "Avv"}, cookie)[0] == 200
        finally:
            srv.shutdown()
        srv, base = _avvia(casi)   # "riavvio": nuovo server sulla stessa radice
        try:
            pagina = _get(base + "/caso/CasoPr")[1].decode()
            assert "NUMERI_IN_VERIFICA" in pagina and "confermato da Avv" in pagina
        finally:
            srv.shutdown()
            il.CONFIG = il.PROGETTO / "config_motore.json"


def prova():
    for nome, f in sorted(globals().items()):
        if nome.startswith("test_"):
            f()
            print("OK", nome)


if __name__ == "__main__":
    prova()
