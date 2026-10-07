"""Parti comuni ai parser: stati, usi delle voci e calcolo delle celle di flussi_cassa_impresa."""
from dataclasses import dataclass

SCHEMA = "analisi-crisi/documento-contabile/0.2"
FOGLIO = "flussi_cassa_impresa"
FATTO, INFERENZA, DA_VERIFICARE = "FATTO", "INFERENZA", "DA VERIFICARE"
OK, KO, NON_ESEGUIBILE = "OK", "KO", "NON ESEGUIBILE"
EXCEL, RESIDUO, CONTROLLO = "excel", "residuo", "controllo"
_GRAVITA = {FATTO: 0, INFERENZA: 1, DA_VERIFICARE: 2}


def peggiore(*stati):
    return max(stati, key=_GRAVITA.__getitem__)


@dataclass(frozen=True)
class RigaFoglio:
    """Una riga di input del foglio: le righe con formule o manuali non compaiono mai qui."""
    riga: int
    nome: str
    componenti: tuple  # ((chiave della voce, segno), ...)
    controllo: str | None = None  # totale del documento che conferma le voci assenti
    forza_inferenza: bool = False
    nota: str | None = None


def cella(rf: RigaFoglio, dati: dict, esito_controllo=None) -> dict:
    """Valore e stato di una cella. `dati`: chiave -> dato della colonna; le voci facoltative assenti non ci sono."""
    note = [rf.nota] if rf.nota else []
    presenti = [(dati[k], s) for k, s in rf.componenti if k in dati and dati[k]["valore"] is not None]
    assenti = [k for k, _ in rf.componenti if k not in dati or dati[k]["valore"] is None]
    if not presenti:
        note.append("Nessuna voce trovata nel documento.")
        if esito_controllo == OK:
            note.append("Il totale del documento quadra senza questa voce.")
        return {"valore": None, "stato": DA_VERIFICARE, "note": note}
    valore = sum(d["valore"] * s for d, s in presenti)
    stato = peggiore(*(d["stato"] for d, _ in presenti))
    if len(rf.componenti) > 1:
        formula = " ".join(("+ " if s > 0 else "- ") + k for k, s in rf.componenti).removeprefix("+ ")
        note.append(f"Valore calcolato: {formula}.")
    if assenti and esito_controllo != OK:
        stato = DA_VERIFICARE
        note.append(f"Voci assenti ({', '.join(assenti)}) e totale del documento non confermato.")
    elif any(k in dati for k in assenti):
        stato = peggiore(stato, INFERENZA)
        note.append(f"Voci assenti considerate zero ({', '.join(assenti)}): il totale del documento quadra.")
    if rf.forza_inferenza:
        stato = peggiore(stato, INFERENZA)
    return {"valore": valore, "stato": stato, "note": note}
