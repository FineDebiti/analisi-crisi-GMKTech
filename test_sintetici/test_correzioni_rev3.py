"""Test delle correzioni rev.3: condizioni realmente rilevate, inesistente/non pertinente non sospendono, stato breve, dicitura, euro e periodo. Dati SINTETICI."""
import sys
import tempfile
from pathlib import Path

QUI = Path(__file__).resolve().parent
sys.path.insert(0, str(QUI.parent))
from analisi_crisi import checklist as ck  # noqa: E402
from analisi_crisi import pdf_preanalisi  # noqa: E402
from analisi_crisi import pratica as pr  # noqa: E402

M = {"margine": 0.117, "rapporti": {"a": 3.27}, "pn_su_attivo": 0.256, "pubblici_su_attivo": 0.118, "cassa_verificata": False}


def test_condizioni_reali():
    s = ck.segnali(M)
    assert "margine EBITDA non positivo" not in s["cassa"] and "non verificato" in s["cassa"]
    assert "oltre 3" not in s.get("indebitamento", "") and "3,27" in s["indebitamento"]
    assert "11,8%" in s["pubblici"]
    s2 = ck.segnali(dict(M, margine=-0.02, cassa_verificata=True))
    assert "non positivo" in s2["cassa"] and "non verificato" not in s2["cassa"]


def test_inesistente_non_sospende():
    with tempfile.TemporaryDirectory() as t:
        p = pr.apri_pratica(Path(t) / "P", "X", "Tester")
        sosp = ck.sospensioni(p, M)
        assert any("da accertare se esistono" in x for v in sosp.values() for x in v)
        for vid in ("B4", "B9"):
            ck.imposta_stato(p, vid, "inesistente", "Tester")
        sosp = ck.sospensioni(p, M)
        testo = " ".join(x for v in sosp.values() for x in v)
        assert "Rateazioni" not in testo and "Atti esecutivi" not in testo
        assert "transazione_fiscale" not in sosp
        ck.imposta_stato(p, "B3", "non pertinente", "Tester")
        assert "Elenco analitico" not in " ".join(x for v in ck.sospensioni(p, M).values() for x in v)
        c = ck.sufficienza_per_concludere(p, M)
        assert all(len(x) < 140 for x in c["motivi_brevi"])
        d = pr.avvia_preanalisi(p, metriche=M, nome="Tester", genera_word=False)
        assert d["riquadri"]["stato_conclusione"]["esito"].startswith("Non definitiva")
        assert len(d["riquadri"]["stato_conclusione"]["esito"]) < 400
        dd = dict(d, tipo="PREANALISI_PROVVISORIA")
        assert pr.dicitura(dd, True) != pr.dicitura(dd, False) and "non consolidata" in pr.dicitura(dd, True) and "in attesa" not in pr.dicitura(dd, True)
        assert pr.eur(1250000) == "1.250.000 €" and pr.eur(1234.5) == "1.234,50 €" and pr.periodo_it("2025-12-31") == "31/12/2025"
        b = pdf_preanalisi.genera(d, {"stato": "APPROVATA", "approvata_da": "T", "approvata_il": "2026-10-04T22:00:00"})
        assert b[:5] == b"%PDF-"


if __name__ == "__main__":
    for n, f in list(globals().items()):
        if n.startswith("test_"):
            f()
            print("OK", n)
