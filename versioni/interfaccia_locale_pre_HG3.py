"""Interfaccia web locale di ANALISI CRISI (solo libreria standard, nessuna dipendenza nuova).

Uso:  python interfaccia_locale.py --radice /percorso/CASI [--porta 8765] [--host 127.0.0.1]
- Un caso = una cartella dentro la radice. Si caricano i PDF, si lancia l'estrazione (stessi script della riga di comando),
  si legge il rapporto SENZA valori, si genera la relazione (riservata e, a richiesta, anonimizzata).
- Su rete (host diverso da 127.0.0.1, es. IP Tailscale) il PIN è obbligatorio: variabile d'ambiente ANALISI_PIN.
- I file con valori restano nella radice; il rapporto a video non contiene valori. Nessuna scrittura fuori dalla radice.
"""
import argparse
import hashlib
import hmac
import html
import json
import os
import re
import subprocess
import sys
import time
from email.parser import BytesParser
from email.policy import HTTP
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlparse

PROGETTO = Path(__file__).resolve().parent
PY = sys.executable
NOME_OK = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,59}$")
TIPI = {"bilancio": ["estrai.py", "{pdf}", "bilancio"], "ruoli": ["estrai_ruoli.py", "{pdf}"], "visura": ["estrai_visura.py", "{pdf}"]}
MAX_BYTE = 120 * 1024 * 1024
STATO = {"radice": None, "pin": None, "segreto": os.urandom(16)}

CSS = """:root{--bg:#f6f7f5;--fg:#1d2420;--mu:#5b665f;--ac:#1f5f4a;--bd:#d5dbd6;--pn:#fff;--ok:#1b7a3d;--wa:#9a6a00;--ko:#b3261e}
@media (prefers-color-scheme:dark){:root{--bg:#141a17;--fg:#e8ece9;--mu:#9aa69f;--ac:#6fcf9f;--bd:#2c3731;--pn:#1b231f}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif;padding:20px 16px}
main{max-width:860px;margin:auto}h1{font-size:1.4rem;margin:0 0 4px}h2{font-size:1.05rem;margin:26px 0 8px}
.mu{color:var(--mu);font-size:.9rem}.pn{background:var(--pn);border:1px solid var(--bd);border-radius:8px;padding:14px;margin:10px 0}
a{color:var(--ac)}input,select,button{font:inherit;padding:7px 10px;border:1px solid var(--bd);border-radius:6px;background:var(--pn);color:var(--fg);min-width:0}
button{background:var(--ac);color:var(--bg);border-color:var(--ac);cursor:pointer}form{display:flex;flex-wrap:wrap;gap:8px;align-items:center}
pre{white-space:pre-wrap;overflow-x:auto;background:var(--pn);border:1px solid var(--bd);padding:10px;border-radius:6px;font-size:.82rem}
table{border-collapse:collapse;width:100%}td,th{border-bottom:1px solid var(--bd);padding:6px 4px;text-align:left}.tw{overflow-x:auto}
.av{border-left:4px solid var(--wa);padding:8px 12px;background:var(--pn)}"""


def pagina(titolo, corpo):
    return (f"<!doctype html><html lang='it'><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
            f"<title>{html.escape(titolo)}</title><style>{CSS}</style><main>{corpo}</main></html>").encode()


def token():
    return hmac.new(STATO["segreto"], (STATO["pin"] or "").encode(), hashlib.sha256).hexdigest()


def sicuro(caso, rel=""):
    base = (STATO["radice"] / caso).resolve()
    p = (base / rel).resolve()
    p.relative_to(base)  # solleva ValueError se esce dalla cartella del caso
    return p


def elenco_file(cartella):
    out = []
    for p in sorted(cartella.rglob("*")):
        if p.is_file() and not any(x.startswith(".") for x in p.relative_to(cartella).parts):
            out.append(p.relative_to(cartella))
    return out


def esegui(argv, cwd=PROGETTO, timeout=900):
    inizio = time.time()
    subprocess.run([PY, *argv], cwd=cwd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=timeout)
    nuovi = [f for f in (PROGETTO / "diagnostica").glob("*.md") if f.stat().st_mtime >= inizio - 1]
    return max(nuovi, key=lambda f: f.stat().st_mtime) if nuovi else None


def vista_caso(caso, messaggio=""):
    cart = STATO["radice"] / caso
    righe = "".join(f"<tr><td><a href='/caso/{quote(caso)}/file/{quote(str(r))}'>{html.escape(str(r))}</a></td></tr>" for r in elenco_file(cart))
    pdfs = [r for r in elenco_file(cart) if r.suffix.lower() == ".pdf" and r.parts[0] not in ("CASO", "_estratti")]
    opz_pdf = "".join(f"<option>{html.escape(str(r))}</option>" for r in pdfs)
    estratti = [r.name for r in elenco_file(cart) if r.parts[0] == "_estratti" and r.suffix == ".json" and not r.stem.endswith(("_ruoli", "_visura", "_situazione"))]
    opz_bil = "<option value=''>(nessuno)</option>" + "".join(f"<option>{html.escape(n)}</option>" for n in estratti)
    ruoli = [r.name for r in elenco_file(cart) if r.parts[0] == "_estratti" and r.stem.endswith("_ruoli")]
    visure = [r.name for r in elenco_file(cart) if r.parts[0] == "_estratti" and r.stem.endswith("_visura")]
    opz = lambda l: "<option value=''>(nessuno)</option>" + "".join(f"<option>{html.escape(n)}</option>" for n in l)
    rapporto = ""
    rp = cart / "CASO" / "ultimo_rapporto.md"
    if rp.exists():
        rapporto = f"<h2>Ultimo rapporto (senza valori)</h2><pre>{html.escape(rp.read_text(encoding='utf-8')[:6000])}</pre>"
    msg = f"<p class='av'>{html.escape(messaggio)}</p>" if messaggio else ""
    return pagina(caso, f"""<p><a href='/'>← Casi</a></p><h1>{html.escape(caso)}</h1><p class='mu'>I dati restano su questa macchina. A video non compaiono valori, salvo nei file che scarichi tu.</p>{msg}
<h2>1. Carica un documento</h2><div class='pn'><form method='post' action='/caso/{quote(caso)}/carica' enctype='multipart/form-data'>
<input type='file' name='pdf' accept='.pdf' required><button>Carica</button></form></div>
<h2>2. Estrai</h2><div class='pn'><form method='post' action='/caso/{quote(caso)}/estrai'><select name='pdf' required>{opz_pdf}</select>
<select name='tipo'><option value='bilancio'>Bilancio / bilancio di verifica</option><option value='ruoli'>Estratto di ruolo</option><option value='visura'>Visura camerale</option></select>
<button>Estrai</button></form><p class='mu'>Gli importi letti restano DA VERIFICARE finché non li approvi nella tabella di revisione.</p></div>{rapporto}
<h2>3. Relazione di preanalisi</h2><div class='pn'><form method='post' action='/caso/{quote(caso)}/relazione'>
<label>Bilancio <select name='bilancio'>{opz_bil}</select></label><label>Ruoli <select name='ruoli'>{opz(ruoli)}</select></label><label>Visura <select name='visura'>{opz(visure)}</select></label>
<label>Nome impresa <input name='nome' value='{html.escape(caso)}'></label>
<label><input type='checkbox' name='provvisorio'> Bilancio provvisorio non depositato</label>
<label><input type='checkbox' name='cr' checked> Centrale Rischi non acquisita</label>
<label><input type='checkbox' name='situazione' checked> Situazione contabile aggiornata assente</label>
<label><input type='checkbox' name='anon'> Genera anche la versione anonimizzata</label><button>Genera</button></form></div>
<h2>File del caso</h2><div class='tw'><table>{righe or '<tr><td class=mu>Nessun file.</td></tr>'}</table></div>""")


def vista_home(messaggio=""):
    casi = sorted(d.name for d in STATO["radice"].iterdir() if d.is_dir() and NOME_OK.match(d.name))
    lista = "".join(f"<tr><td><a href='/caso/{quote(c)}'>{html.escape(c)}</a></td></tr>" for c in casi)
    msg = f"<p class='av'>{html.escape(messaggio)}</p>" if messaggio else ""
    return pagina("ANALISI CRISI", f"""<h1>ANALISI CRISI</h1><p class='mu'>Estrazione, revisione, modello Excel e relazione con semaforo. Supporto alla decisione, non attestazione.</p>{msg}
<h2>Nuovo caso</h2><div class='pn'><form method='post' action='/nuovo'><input name='nome' placeholder='NomeCaso (lettere, numeri, - _)' required pattern='[A-Za-z0-9][A-Za-z0-9_\\-]*'><button>Crea</button></form></div>
<h2>Casi</h2><div class='tw'><table>{lista or '<tr><td class=mu>Nessun caso.</td></tr>'}</table></div>""")


def vista_login(errore=False):
    return pagina("Accesso", f"<h1>Accesso</h1>{'<p class=av>PIN errato.</p>' if errore else ''}<form method='post' action='/login'><input type='password' name='pin' autofocus required placeholder='PIN'><button>Entra</button></form>")


class H(BaseHTTPRequestHandler):
    server_version = "AnalisiCrisi"

    def log_message(self, *a):
        pass

    def _invia(self, corpo, codice=200, tipo="text/html; charset=utf-8", extra=()):
        self.send_response(codice)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(corpo)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        for k, v in extra:
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(corpo)

    def _redirect(self, dove, extra=()):
        self.send_response(303)
        self.send_header("Location", dove)
        for k, v in extra:
            self.send_header(k, v)
        self.end_headers()

    def _autenticato(self):
        if not STATO["pin"]:
            return True
        c = self.headers.get("Cookie", "")
        m = re.search(r"ac=([0-9a-f]{64})", c)
        return bool(m) and hmac.compare_digest(m.group(1), token())

    def _corpo(self):
        n = int(self.headers.get("Content-Length") or 0)
        if n > MAX_BYTE:
            raise ValueError("file troppo grande")
        return self.rfile.read(n)

    def _form(self):
        return {k: v[0] for k, v in parse_qs(self._corpo().decode("utf-8", "replace"), keep_blank_values=True).items()}

    def do_GET(self):
        try:
            if not self._autenticato():
                return self._invia(vista_login())
            parti = [unquote(p) for p in urlparse(self.path).path.strip("/").split("/")]
            if parti == [""]:
                return self._invia(vista_home())
            if parti[0] == "caso" and len(parti) == 2 and NOME_OK.match(parti[1]) and (STATO["radice"] / parti[1]).is_dir():
                return self._invia(vista_caso(parti[1]))
            if parti[0] == "caso" and len(parti) >= 4 and parti[2] == "file" and NOME_OK.match(parti[1]):
                p = sicuro(parti[1], "/".join(parti[3:]))
                if p.is_file():
                    tipo = {".html": "text/html; charset=utf-8", ".pdf": "application/pdf", ".md": "text/plain; charset=utf-8", ".csv": "text/csv; charset=utf-8",
                            ".json": "application/json", ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                            ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}.get(p.suffix.lower(), "application/octet-stream")
                    return self._invia(p.read_bytes(), tipo=tipo, extra=[("Content-Disposition", f"inline; filename*=UTF-8''{quote(p.name)}")])
            return self._invia(pagina("Non trovato", "<h1>Non trovato</h1><p><a href='/'>Home</a></p>"), 404)
        except (ValueError, OSError):
            return self._invia(pagina("Errore", "<h1>Richiesta non valida</h1>"), 400)

    def do_POST(self):
        try:
            path = urlparse(self.path).path
            if path == "/login":
                f = self._form()
                if STATO["pin"] and hmac.compare_digest(f.get("pin", ""), STATO["pin"]):
                    return self._redirect("/", [("Set-Cookie", f"ac={token()}; HttpOnly; SameSite=Strict; Path=/")])
                return self._invia(vista_login(True), 403)
            if not self._autenticato():
                return self._invia(vista_login(), 401)
            if path == "/nuovo":
                nome = self._form().get("nome", "")
                if not NOME_OK.match(nome):
                    return self._invia(vista_home("Nome non valido."), 400)
                (STATO["radice"] / nome).mkdir(exist_ok=True)
                return self._redirect(f"/caso/{quote(nome)}")
            m = re.fullmatch(r"/caso/([^/]+)/(carica|estrai|relazione)", path)
            if not m or not NOME_OK.match(unquote(m.group(1))):
                return self._invia(pagina("Non trovato", "<h1>Non trovato</h1>"), 404)
            caso, azione = unquote(m.group(1)), m.group(2)
            cart = STATO["radice"] / caso
            if not cart.is_dir():
                return self._invia(pagina("Non trovato", "<h1>Caso inesistente</h1>"), 404)
            return getattr(self, "_" + azione)(caso, cart)
        except (ValueError, OSError, subprocess.TimeoutExpired) as e:
            return self._invia(pagina("Errore", f"<h1>Operazione non riuscita</h1><p>{html.escape(type(e).__name__)}</p><p><a href='/'>Home</a></p>"), 400)

    def _carica(self, caso, cart):
        corpo = self._corpo()
        msg = BytesParser(policy=HTTP).parsebytes(b"Content-Type: " + self.headers["Content-Type"].encode() + b"\r\n\r\n" + corpo)
        for parte in msg.iter_parts():
            nome = Path(parte.get_filename() or "").name
            if parte.get_param("name", header="content-disposition") == "pdf" and nome.lower().endswith(".pdf"):
                dati = parte.get_payload(decode=True)
                if not dati.startswith(b"%PDF"):
                    return self._invia(vista_caso(caso, "Il file non è un PDF valido."), 400)
                dest = cart / re.sub(r"[^A-Za-z0-9._-]", "_", nome)
                n = 1
                while dest.exists():  # non si sovrascrive mai un documento
                    dest = dest.with_name(f"{dest.stem}_{n}{dest.suffix}")
                    n += 1
                dest.write_bytes(dati)
                return self._invia(vista_caso(caso, f"Caricato: {dest.name}"))
        return self._invia(vista_caso(caso, "Nessun PDF ricevuto."), 400)

    def _estrai(self, caso, cart):
        f = self._form()
        pdf = sicuro(caso, f.get("pdf", ""))
        tipo = f.get("tipo", "")
        if tipo not in TIPI or not pdf.is_file() or pdf.suffix.lower() != ".pdf":
            return self._invia(vista_caso(caso, "Selezione non valida."), 400)
        argv = [a.format(pdf=str(pdf)) for a in TIPI[tipo]]
        rap = esegui(argv)
        (cart / "CASO").mkdir(exist_ok=True)
        testo = rap.read_text(encoding="utf-8") if rap else "Nessun rapporto prodotto: controllare il documento."
        (cart / "CASO" / "ultimo_rapporto.md").write_text(testo, encoding="utf-8")
        return self._invia(vista_caso(caso, f"Estrazione eseguita su {pdf.name}. Rivedi il rapporto e la tabella di revisione."))

    def _relazione(self, caso, cart):
        f = self._form()
        est = cart / "_estratti"
        def scelta(chiave):
            n = Path(f.get(chiave, "")).name
            return (est / n) if n and (est / n).is_file() else None
        bil, ru, vi = scelta("bilancio"), scelta("ruoli"), scelta("visura")
        if not bil:
            return self._invia(vista_caso(caso, "Serve almeno un bilancio estratto."), 400)
        (cart / "CASO").mkdir(exist_ok=True)
        fatti = {"nome": f.get("nome") or caso, "cr": "non_acquisita" if "cr" in f else "acquisita", "situazione_assente": "situazione" in f,
                 "bilancio_provvisorio": "provvisorio" in f, "pignoramenti_non_letti": False, "esiti": []}
        fp = cart / "CASO" / "fatti_caso.json"
        fp.write_text(json.dumps(fatti, ensure_ascii=False, indent=1), encoding="utf-8")
        ts = time.strftime("%Y%m%d-%H%M%S")
        generati = []
        for anon in (False, True) if "anon" in f else (False,):
            out = cart / "CASO" / f"Relazione_{caso}_{'ANONIMIZZATA_' if anon else ''}{ts}.docx"
            argv = ["relazione_caso.py", "--bilancio", str(bil), "--fatti", str(fp), "--out", str(out)]
            if ru:
                argv += ["--ruoli", str(ru)]
            if vi:
                argv += ["--visura", str(vi)]
            if anon:
                argv.append("--anonimizza")
            subprocess.run([PY, *argv], cwd=PROGETTO, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=300)
            if out.exists():
                generati.append(out.name)
                subprocess.run(["soffice", "--headless", "--convert-to", "pdf", "--outdir", str(out.parent), str(out)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=180)
        return self._invia(vista_caso(caso, "Generati: " + ", ".join(generati) if generati else "Relazione non generata: controllare i dati estratti."))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--radice", required=True)
    ap.add_argument("--porta", type=int, default=8765)
    ap.add_argument("--host", default="127.0.0.1")
    a = ap.parse_args()
    STATO["radice"] = Path(a.radice).resolve()
    STATO["radice"].mkdir(parents=True, exist_ok=True)
    STATO["pin"] = os.environ.get("ANALISI_PIN") or None
    if a.host not in ("127.0.0.1", "localhost") and not STATO["pin"]:
        sys.exit("Rete esposta: imposta ANALISI_PIN (variabile d'ambiente) prima di avviare.")
    srv = ThreadingHTTPServer((a.host, a.porta), H)
    print(f"ANALISI CRISI in ascolto su http://{a.host}:{a.porta}  (radice: {STATO['radice'].name})")
    srv.serve_forever()


if __name__ == "__main__":
    main()
