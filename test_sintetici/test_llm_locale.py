"""Test del livello modello locale con un FINTO server (nessun modello reale). Dati SINTETICI."""
import shutil
import sys
import tempfile
from pathlib import Path

QUI = Path(__file__).resolve().parent
sys.path.insert(0, str(QUI.parent))
sys.path.insert(0, str(QUI))
import mock_llm  # noqa: E402
from analisi_crisi import dati_pratica as dp  # noqa: E402
from analisi_crisi import llm_locale as ll  # noqa: E402
from analisi_crisi import pratica as pr  # noqa: E402

DEMO = QUI.parent / "DEMO_PDF"


def test_endpoint_solo_locale():
    for u in ("http://127.0.0.1:8080/v1", "http://localhost:11434/v1", "http://[::1]:1234/v1"):
        ll.endpoint_locale(u)
    for u in ("https://api.example.com/v1", "http://192.168.1.50:8080/v1", "http://100.64.0.2:8080/v1"):
        try:
            ll.endpoint_locale(u)
        except ll.ErroreLLM:
            continue
        raise AssertionError("endpoint non locale accettato: " + u)


def test_estrazione_verifica_e_applicazione():
    srv = mock_llm.avvia()
    cfg = dict(ll.CONFIG_DEFAULT, abilitato=True, endpoint="http://127.0.0.1:%d/v1" % srv.server_port, modello="mock", timeout_s=30)
    with tempfile.TemporaryDirectory() as t:
        cart, pc = dp.crea_pratica(Path(t), "DEMO", "CNC", "Tester"); cart = Path(t) / cart; pc = cart / "PRATICA"
        for f in DEMO.glob("*.pdf"):
            shutil.copy(f, cart / f.name)
        pr.registra_documento(pc, "bilancio_demo.pdf", cart / "bilancio_demo.pdf", "bilancio", periodo="2025")
        # niente lettura automatica: la prova e' sul modello
        run = ll.esegui_estrazione(pc, cart, "Tester", cfg)
        assert run["json_valido"] and run["config"]["seed"] == 7 and "mock-test-nonmodello" in run["runtime"]["modelli_riportati"]
        assert run["risposta_grezza"].startswith("<think>"), "la prima risposta va conservata integra"
        esiti = {(p["campo"], p["motivo"][:12]): p["esito"] for p in run["proposte"]}
        e = [p["esito"] for p in run["proposte"]]
        assert e == ["RISCONTRATO", "RISCONTRATO", "NON RISCONTRATO", "NON RISCONTRATO", "NON RISCONTRATO", "DUPLICATO", "RISCONTRATO", "MANCANTE"], e
        assert mock_llm.H.chiamate[0]["temperature"] == 0.0 and mock_llm.H.chiamate[0]["seed"] == 7
        sistema = mock_llm.H.chiamate[0]["messages"][0]["content"]
        assert "SOGLIE_V3" in sistema and "Mai zero" in sistema and "1.274.500" not in sistema, "esempi sintetici distinti dalla DEMO"
        mod, saltati = ll.applica_proposte(pc, list(range(len(run["proposte"]))), "Tester")
        assert sorted(mod) == ["ammortamenti", "patrimonio_netto", "ricavi"], mod
        assert any("NON RISCONTRATO" in s for s in saltati)
        v = dp.carica(pc)["campi"]
        assert v["ricavi"]["stato"] == "DA VERIFICARE" and v["ricavi"]["origine"] == "LLM" and v["ricavi"]["pagina"] == 3
        assert dp.valori(pc).get("debiti_bancari") is None and dp.valori(pc).get("debiti_totali") is None, "mai zero ne' valori non riscontrati"
        assert dp.ORIGINI["LLM"].startswith("Proposto dal modello locale")


def test_non_abilitato_nessuna_chiamata():
    n0 = len(mock_llm.H.chiamate)
    with tempfile.TemporaryDirectory() as t:
        cart, pc = dp.crea_pratica(Path(t), "X", "CNC", "Tester"); cart = Path(t) / cart; pc = cart / "PRATICA"
        try:
            ll.esegui_estrazione(pc, cart, "Tester", dict(ll.CONFIG_DEFAULT))
        except ll.ErroreLLM:
            pass
        else:
            raise AssertionError("estrazione eseguita con modello non abilitato")
    assert len(mock_llm.H.chiamate) == n0


if __name__ == "__main__":
    for n, f in list(globals().items()):
        if n.startswith("test_"):
            f()
            print("OK", n)
