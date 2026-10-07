"""Finto server OpenAI-compatibile SOLO PER TEST DEL CODICE (non e' un modello): risponde con un JSON predefinito, con errori voluti per provare il verificatore."""
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

RISPOSTA = {
    "dati": [
        {"campo": "ricavi", "valore": 1250000, "documento": 1, "pagina": 3, "periodo": "2025-12-31", "citazione": "1) ricavi delle vendite e delle prestazioni 1.250.000 1.120.000", "natura": "FATTO", "motivazione": "prima colonna"},
        {"campo": "patrimonio_netto", "valore": 206300, "documento": 1, "pagina": 2, "periodo": "2025-12-31", "citazione": "Totale patrimonio netto 206.300 143.900", "natura": "FATTO", "motivazione": "prima colonna"},
        {"campo": "debiti_totali", "valore": 479000, "documento": 1, "pagina": 2, "periodo": "2025-12-31", "citazione": "Totale debiti 497.000 541.000", "natura": "FATTO", "motivazione": "ERRORE VOLUTO: numero diverso dalla citazione"},
        {"campo": "debiti_bancari", "valore": 0, "documento": 1, "pagina": 2, "periodo": "2025-12-31", "citazione": "Debiti verso banche 0", "natura": "FATTO", "motivazione": "ERRORE VOLUTO: zero al posto di non trovato, citazione inventata"},
        {"campo": "totale_attivo", "valore": 806500, "documento": 1, "pagina": 2, "periodo": "2025-12-31", "citazione": "Totale attivo 806.500 766.800", "natura": "FATTO", "motivazione": "ERRORE VOLUTO: pagina sbagliata (e' a pag. 1)"},
        {"campo": "ricavi", "valore": 1250000, "documento": 1, "pagina": 3, "periodo": "2025-12-31", "citazione": "1) ricavi delle vendite e delle prestazioni 1.250.000 1.120.000", "natura": "FATTO", "motivazione": "duplicato voluto"},
        {"campo": "ammortamenti", "valore": 40500, "documento": 1, "pagina": 3, "periodo": "2025-12-31", "citazione": "Totale ammortamenti e svalutazioni 40.500 39.000", "natura": "FATTO", "motivazione": "ok"},
        {"campo": "debiti_pubblici", "valore": None, "documento": 1, "pagina": 2, "periodo": "2025-12-31", "citazione": "", "natura": "FATTO", "motivazione": "non trovato"}],
    "dati_mancanti": ["debiti_bancari", "debiti_pubblici", "crediti_soci"],
    "normalizzazioni": [], "incongruenze": [], "duplicazioni": [],
    "scenari": [{"scenario": "Liquidazione del patrimonio", "stato": "GIUDIZIO SOSPESO", "motivi": ["manca elenco creditori"], "dati_usati": ["patrimonio_netto"], "natura": "INFERENZA"}],
    "richieste_prioritarie": [{"ordine": 1, "richiesta": "Estratto di ruolo", "perche": "debiti pubblici non presenti", "riattiva": "transazione"}],
    "note_per_il_titolare": []}


class H(BaseHTTPRequestHandler):
    chiamate = []
    doc_bilancio = 1

    def log_message(self, *a):
        pass

    def _j(self, o):
        b = json.dumps(o).encode()
        self.send_response(200); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)

    def do_GET(self):
        self._j({"data": [{"id": "mock-test-nonmodello"}]})

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        H.chiamate.append(json.loads(self.rfile.read(n)))
        self._j({"id": "mock1", "model": "mock-test-nonmodello", "usage": {"prompt_tokens": 1, "completion_tokens": 1},
                 "choices": [{"message": {"content": "<think>test</think>```json\n" + json.dumps(RISPOSTA).replace('"documento": 1', '"documento": %d' % H.doc_bilancio) + "\n```"}}]})


def avvia(porta=0, doc_bilancio=1):
    H.doc_bilancio = doc_bilancio
    s = HTTPServer(("127.0.0.1", porta), H)
    threading.Thread(target=s.serve_forever, daemon=True).start()
    return s
