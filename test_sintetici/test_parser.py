"""Test dei parser (a) e (c) sui PDF fittizi. Uso: .venv/bin/python test_sintetici/test_parser.py"""
import sys
from pathlib import Path

QUI = Path(__file__).resolve().parent
sys.path.insert(0, str(QUI.parent))
sys.path.insert(0, str(QUI))

import genera_bilancio_fittizio as gen  # noqa: E402
import genera_dichiarazione_fittizia as gen_dr  # noqa: E402
from analisi_crisi import parser_dichiarazione  # noqa: E402
from analisi_crisi.comune import DA_VERIFICARE, FATTO, INFERENZA, KO, OK  # noqa: E402
from analisi_crisi.diagnostica import RapportoConValori, rapporto, verifica_senza_valori  # noqa: E402
from analisi_crisi.foglio import csv_incolla, csv_senza_valori  # noqa: E402
from analisi_crisi.parser_bilancio import analizza  # noqa: E402
from analisi_crisi.revisione import html_revisione  # noqa: E402

# chiave del parser -> chiave del generatore
ATTESI = {
    "ce.A1": "A1", "ce.A2": "A2", "ce.A5": "A5", "ce.A": "A", "ce.B6": "B6", "ce.B7": "B7", "ce.B8": "B8", "ce.B9": "B9",
    "ce.B10": "B10", "ce.B11": "B11", "ce.B12": "B12", "ce.B13": "B13", "ce.B14": "B14", "ce.B": "Btot",
    "ce.AB": "AB", "ce.C16": "C16", "ce.C17": "C17", "ce.C": "Ctot", "ce.D": "Dtot", "ce.RAI": "RAI",
    "ce.I20": "I20", "ce.U21": "U21", "sp.tot_attivo": "TOT_ATTIVO", "sp.utile": "U21", "sp.tot_pn": "PN",
    "sp.tot_debiti": "P_D", "sp.tot_passivo": "TOT_PASSIVO",
}
# Voci con etichetta su due righe: ricostruite, quindi INFERENZA.
A_CAPO = ("ce.A2", "ce.B11", "ce.D", "ce.I20")
RIGHE_INPUT = [10, 11, 12, 14, 15, 16, 17, 19, 21, 23]


def _per_chiave(r):
    return {(d["chiave"], d["anno"]): d for d in r["dati"] + r["residui"] + r["controllo"]}


def _celle(r):
    return {(riga["riga"], col): c for riga in r["foglio"] for col, c in riga["celle"].items()}


def test_bilancio_coerente():
    r = analizza(QUI / "bilancio_abbreviato_fittizio.pdf")
    v, dati = gen.valori(), _per_chiave(r)
    assert r["esito"] == "COMPLETATO"
    assert [e["data_chiusura"] for e in r["esercizi"]] == ["2025-12-31", "2024-12-31"]
    assert [e["colonna_excel"] for e in r["esercizi"]] == ["D", "C"]
    assert set(ATTESI) <= {k for k, _ in dati}
    extra = {k for k, _ in dati} - set(ATTESI)
    assert extra and all(k.startswith('sp.') for k in extra), extra  # dettagli SP per modello Aziende
    for chiave, k in ATTESI.items():
        for i, anno in enumerate((-1, -2)):
            d = dati[chiave, anno]
            assert d["valore"] == v[k][i], (chiave, anno)
            assert d["stato"] == (INFERENZA if chiave in A_CAPO else FATTO), (chiave, d["stato"])
            assert d["fonte"]["pagina"] == (3 if chiave.startswith("ce.") else (1 if chiave == "sp.tot_attivo" else 2)), chiave
            assert d["fonte"]["testo_letto"]
    assert all(c["esito"] == OK for c in r["controlli"]), [c for c in r["controlli"] if c["esito"] != OK]
    assert {d["chiave"] for d in r["residui"] if d["chiave"].startswith("ce.")} == {"ce.B12", "ce.B13", "ce.D"}
    assert all(d["chiave"].startswith(("ce.", "sp.")) for d in r["residui"])
    assert all(d["destinazione"] is None for d in r["residui"] + r["controllo"])
    assert [c for c in r["voci_facoltative_assenti"] if c.startswith("ce.")] == ["ce.A23", "ce.A3", "ce.A4", "ce.C15", "ce.C17bis"]
    assert r["righe_non_mappate"] == []
    assert "<table>" in html_revisione(r)


def test_bilancio_foglio():
    r = analizza(QUI / "bilancio_abbreviato_fittizio.pdf")
    v, celle = gen.valori(), _celle(r)
    assert [riga["riga"] for riga in r["foglio"]] == RIGHE_INPUT  # nessuna riga con formule o manuale
    attese = {
        10: ("A1", FATTO), 11: ("A2", INFERENZA), 12: ("A5", FATTO), 14: ("B6", FATTO), 15: ("B7", FATTO),
        16: ("B9", FATTO), 19: ("B10", FATTO), 23: ("I20", INFERENZA),
    }
    for i, col in enumerate(("D", "C")):
        for riga, (k, stato) in attese.items():
            assert celle[riga, col]["valore"] == v[k][i], (riga, col)
            assert celle[riga, col]["stato"] == stato, (riga, col)
        assert celle[17, col]["valore"] == v["B8"][i] + v["B11"][i] + v["B14"][i]
        assert celle[21, col]["valore"] == v["C16"][i] - v["C17"][i]
        assert celle[17, col]["stato"] == celle[21, col]["stato"] == INFERENZA
    assert any("verificare voce" in n.lower() for n in celle[23, "D"]["note"])
    testo = csv_incolla(r)
    righe = testo.strip().splitlines()
    assert righe[0] == "riga;voce;C;D;stato C;stato D;note" and len(righe) == 1 + len(RIGHE_INPUT)
    assert righe[1].startswith(f"10;Ricavi netti (A1);{v['A1'][1]};{v['A1'][0]};FATTO;FATTO")
    verifica_senza_valori(csv_senza_valori(r), r)


def test_bilancio_anomalie():
    r = analizza(QUI / "bilancio_abbreviato_fittizio_anomalie.pdf")
    dati, celle = _per_chiave(r), _celle(r)
    assert dati["ce.B7", -1]["stato"] == INFERENZA  # etichetta senza numero di voce
    assert celle[15, "D"]["stato"] == INFERENZA
    assert dati["ce.B", -1]["stato"] == DA_VERIFICARE  # totale sbagliato nel 2025
    assert dati["ce.B", -2]["stato"] == FATTO
    assert dati["ce.AB", -1]["stato"] == DA_VERIFICARE  # A - B non torna con il totale sbagliato
    # Le componenti mantengono lo stato e ricevono una nota.
    assert dati["ce.B6", -1]["stato"] == FATTO and any("controllo fallito" in n for n in dati["ce.B6", -1]["note"])
    ko = {(c["nome"].split(" =")[0], c["anno"]) for c in r["controlli"] if c["esito"] == KO}
    assert ko == {("Totale costi della produzione", -1), ("Differenza", -1)}, ko
    rapporto(r)


def test_scansione():
    r = analizza(QUI / "scansione_fittizia.pdf")
    assert r["esito"] == "FERMATO: SCANSIONE" and r["dati"] == [] and r["foglio"] == []
    assert "FERMATO" in rapporto(r) and "<h1>" in html_revisione(r)
    assert parser_dichiarazione.analizza(QUI / "scansione_fittizia.pdf")["esito"] == "FERMATO: SCANSIONE"


def test_dichiarazioni():
    regimi = {"professionista": ["RE"], "impresa": ["RG"], "forfettario": ["LM"]}
    for nome, attesi in gen_dr.ATTESI.items():
        r = parser_dichiarazione.analizza(QUI / nome)
        celle = _celle(r)
        assert r["esito"] == "COMPLETATO" and r["esercizi"][0]["periodo_imposta"] == gen_dr.PERIODO, nome
        assert r["regimi"] == regimi[nome.split("_")[-1].removesuffix(".pdf")], (nome, r["regimi"])
        assert {riga for riga, _ in celle} == set(attesi) and {col for _, col in celle} == {"E"}, nome
        for riga, valore in attesi.items():
            assert celle[riga, "E"]["valore"] == valore, (nome, riga)
            assert celle[riga, "E"]["stato"] == FATTO, (nome, riga, celle[riga, "E"])
        assert all(c["esito"] == OK for c in r["controlli"]) and r["controlli"], (nome, r["controlli"])
        assert "<table>" in html_revisione(r)
        rapporto(r, nome)
        verifica_senza_valori(csv_senza_valori(r), r)
        assert csv_incolla(r).splitlines()[0] == "riga;voce;E;stato E;note"
    # Differenza sul rigo RG25 anziché RG26: riconosciuta dalla descrizione, quindi INFERENZA.
    r = parser_dichiarazione.analizza(QUI / "dichiarazione_fittizia_impresa.pdf")
    assert _per_chiave(r)["dr.RG26", None]["stato"] == INFERENZA


def test_guardia_diagnostica():
    r = analizza(QUI / "bilancio_abbreviato_fittizio.pdf")
    for testo in ("ricavi 1.250.000", "ricavi 1250000", r["dati"][0]["fonte"]["testo_letto"]):
        try:
            verifica_senza_valori(testo, r)
        except RapportoConValori:
            continue
        raise AssertionError("la guardia non ha fermato: " + testo)


if __name__ == "__main__":
    gen.genera()
    gen_dr.genera()
    for nome, prova in sorted(globals().items()):
        if nome.startswith("test_"):
            prova()
            print("OK", nome)
