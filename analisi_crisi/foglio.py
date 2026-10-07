"""foglio_incolla.csv: le celle di input di flussi_cassa_impresa nell'ordine delle righe Excel.

Solo righe di input: le righe con formule e quelle manuali non compaiono, quindi il CSV va incollato
cella per cella (o riga per riga), non come blocco unico. Nulla viene scritto nell'xlsm.
"""
import csv
import io


def _colonne(r):
    return sorted({c for riga in r["foglio"] for c in riga["celle"]})


def _numero(v):
    return "" if v is None else str(v).replace(".", ",")


def _scrivi(testata, righe):
    buffer = io.StringIO()
    w = csv.writer(buffer, delimiter=";", lineterminator="\n")
    w.writerow(testata)
    w.writerows(righe)
    return buffer.getvalue()


def csv_incolla(r: dict) -> str:
    """Versione con i valori: resta accanto al PDF."""
    colonne = _colonne(r)
    testata = ["riga", "voce", *colonne, *(f"stato {c}" for c in colonne), "note"]
    righe = []
    for riga in sorted(r["foglio"], key=lambda x: x["riga"]):
        celle = [riga["celle"].get(c) for c in colonne]
        note = " ".join(dict.fromkeys(n for c in celle if c for n in c["note"]))
        righe.append([riga["riga"], riga["voce"], *(_numero(c["valore"]) if c else "" for c in celle),
                      *(c["stato"] if c else "" for c in celle), note])
    return _scrivi(testata, righe)


def csv_senza_valori(r: dict) -> str:
    """Versione per la diagnostica: solo cella compilata sì/no e stato."""
    colonne = _colonne(r)
    testata = ["riga", "voce", *(f"compilata {c}" for c in colonne), *(f"stato {c}" for c in colonne)]
    righe = []
    for riga in sorted(r["foglio"], key=lambda x: x["riga"]):
        celle = [riga["celle"].get(c) for c in colonne]
        righe.append([riga["riga"], riga["voce"], *("sì" if c and c["valore"] is not None else "no" for c in celle),
                      *(c["stato"] if c else "" for c in celle)])
    return _scrivi(testata, righe)
