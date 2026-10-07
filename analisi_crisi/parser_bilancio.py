"""Parser (a): bilancio depositato, conto economico art. 2425 c.c. Solo regole, tutto in locale."""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import pdfplumber

from .comune import (peggiore, CONTROLLO, DA_VERIFICARE, EXCEL, FATTO, FOGLIO, INFERENZA, KO, NON_ESEGUIBILE, OK, RESIDUO,
                     SCHEMA, RigaFoglio, cella)

TIPO = "bilancio_depositato"
CE, SP, SP_ATTIVO, SP_PASSIVO = "CE", "SP", "SP_ATTIVO", "SP_PASSIVO"
# Colonne di flussi_cassa_impresa, regime ordinario: C = Anno -2, D = Anno -1. E (previsionale) è manuale.
COLONNA = {-1: "D", -2: "C"}


@dataclass(frozen=True)
class Modello:
    codice: str | None  # numero o lettera della voce, es. "7)"
    regex: str  # sull'etichetta normalizzata, senza codice
    unione: bool = True  # False: vale solo se etichetta e importi sono sulla stessa riga


@dataclass(frozen=True)
class Voce:
    chiave: str
    sezione: str
    nome: str  # etichetta standard, mai letta dal documento
    modelli: tuple[Modello, ...]
    uso: str = EXCEL
    facoltativa: bool = False  # voce spesso assente: se manca non genera un dato DA VERIFICARE


def _v(chiave, sezione, nome, *modelli, uso=EXCEL, facoltativa=False):
    return Voce(chiave, sezione, nome, tuple(Modello(*m) for m in modelli), uso, facoltativa)


# Le voci con sottovoci si leggono dalla riga "Totale ..."; il modello con codice e unione=False
# copre i documenti che riportano l'importo direttamente sulla riga numerata.
# I totali sono formule nell'Excel: si estraggono solo come CONTROLLO e non si scrivono mai.
VOCI = (
    _v("ce.A1", CE, "A1 Ricavi delle vendite e delle prestazioni", ("1)", r"ricavi delle vendite e delle prestazioni")),
    _v("ce.A23", CE, "A2/A3 Variazioni rimanenze prodotti e lavori in corso", (None, r"2\), 3\) variazioni"), facoltativa=True),
    _v("ce.A2", CE, "A2 Variazioni rimanenze prodotti", ("2)", r"variazioni delle rimanenze di prodotti"), facoltativa=True),
    _v("ce.A3", CE, "A3 Variazioni lavori in corso su ordinazione", ("3)", r"variazioni dei lavori in corso"), facoltativa=True),
    _v("ce.A4", CE, "A4 Incrementi di immobilizzazioni per lavori interni", ("4)", r"incrementi di immobilizzazioni"), uso=RESIDUO, facoltativa=True),
    _v("ce.A5", CE, "A5 Altri ricavi e proventi", (None, r"totale altri ricavi e proventi"), ("5)", r"altri ricavi e proventi", False)),
    _v("ce.A", CE, "Totale valore della produzione (A)", (None, r"totale valore della produzione"), uso=CONTROLLO),
    _v("ce.B6", CE, "B6 Materie prime, sussidiarie, di consumo e merci", ("6)", r"per materie prime")),
    _v("ce.B7", CE, "B7 Servizi", ("7)", r"per servizi")),
    _v("ce.B8", CE, "B8 Godimento di beni di terzi", ("8)", r"per godimento di beni di terzi")),
    _v("ce.B9", CE, "B9 Personale", (None, r"totale costi per il personale"), ("9)", r"per il personale", False)),
    _v("ce.B10", CE, "B10 Ammortamenti e svalutazioni", (None, r"totale ammortamenti e svalutazioni"), ("10)", r"ammortamenti e svalutazioni", False)),
    _v("ce.B11", CE, "B11 Variazioni delle rimanenze di materie", ("11)", r"variazioni delle rimanenze di materie")),
    _v("ce.B12", CE, "B12 Accantonamenti per rischi", ("12)", r"accantonamenti per rischi"), uso=RESIDUO),
    _v("ce.B13", CE, "B13 Altri accantonamenti", ("13)", r"altri accantonamenti"), uso=RESIDUO),
    _v("ce.B14", CE, "B14 Oneri diversi di gestione", ("14)", r"oneri diversi di gestione")),
    _v("ce.B", CE, "Totale costi della produzione (B)", (None, r"totale costi della produzione"), uso=CONTROLLO),
    _v("ce.AB", CE, "Differenza tra valore e costi della produzione (A - B)", (None, r"differenza tra valore e costi della produzione"), uso=CONTROLLO),
    _v("ce.C15", CE, "C15 Proventi da partecipazioni", (None, r"totale proventi da partecipazioni"), ("15)", r"proventi da partecipazioni", False), facoltativa=True),
    _v("ce.C16", CE, "C16 Altri proventi finanziari", (None, r"totale altri proventi finanziari"), ("16)", r"altri proventi finanziari", False)),
    _v("ce.C17", CE, "C17 Interessi e altri oneri finanziari", (None, r"totale interessi e altri oneri finanziari"), ("17)", r"interessi e altri oneri finanziari", False)),
    _v("ce.C17bis", CE, "C17-bis Utili e perdite su cambi", ("17-bis)", r"utili e perdite su cambi"), facoltativa=True),
    _v("ce.C", CE, "Totale proventi e oneri finanziari (C)", (None, r"totale proventi e oneri finanziari"), uso=CONTROLLO),
    _v("ce.D", CE, "Totale rettifiche di valore (D)", (None, r"totale (delle )?rettifiche di valore"), uso=RESIDUO),
    _v("ce.RAI", CE, "Risultato prima delle imposte", (None, r"risultato prima delle imposte"), uso=CONTROLLO),
    _v("ce.I20", CE, "20 Imposte sul reddito", (None, r"totale delle imposte sul reddito"), ("20)", r"imposte sul reddito", False)),
    _v("ce.U21", CE, "21 Utile (perdita) dell'esercizio", ("21)", r"utile \(perdita\) dell'esercizio"), uso=CONTROLLO),
    _v("sp.tot_attivo", SP_ATTIVO, "SP Totale attivo", (None, r"totale attivo$"), uso=CONTROLLO),
    _v("sp.utile", SP_PASSIVO, "SP Utile (perdita) dell'esercizio", ("ix -", r"utile \(perdita\) dell'esercizio"), uso=CONTROLLO),
    _v("sp.tot_pn", SP_PASSIVO, "SP Totale patrimonio netto", (None, r"totale patrimonio netto"), uso=CONTROLLO),
    _v("sp.tot_debiti", SP_PASSIVO, "SP Totale debiti", (None, r"totale debiti"), uso=CONTROLLO),
    _v("sp.tot_passivo", SP_PASSIVO, "SP Totale passivo", (None, r"totale passivo$"), uso=CONTROLLO),
    # Dettaglio dello stato patrimoniale (modello Aziende). Facoltative: se assenti non generano dati DA VERIFICARE.
    _v("sp.crediti_soci", SP_ATTIVO, "SP A) Crediti verso soci", ("a)", r"crediti verso soci"), uso=RESIDUO, facoltativa=True),
    _v("sp.imm_immat", SP_ATTIVO, "SP B.I Immobilizzazioni immateriali", ("i -", r"immobilizzazioni immateriali"), (None, r"totale immobilizzazioni immateriali"), uso=RESIDUO, facoltativa=True),
    _v("sp.imm_mat", SP_ATTIVO, "SP B.II Immobilizzazioni materiali", ("ii -", r"immobilizzazioni materiali"), (None, r"totale immobilizzazioni materiali"), uso=RESIDUO, facoltativa=True),
    _v("sp.imm_fin", SP_ATTIVO, "SP B.III Immobilizzazioni finanziarie", ("iii -", r"immobilizzazioni finanziarie"), (None, r"totale immobilizzazioni finanziarie"), uso=RESIDUO, facoltativa=True),
    _v("sp.rimanenze", SP_ATTIVO, "SP C.I Rimanenze", ("i -", r"rimanenze"), (None, r"totale rimanenze"), uso=RESIDUO, facoltativa=True),
    _v("sp.crediti_clienti", SP_ATTIVO, "SP C.II.1 Crediti verso clienti", ("1)", r"verso clienti", False), uso=RESIDUO, facoltativa=True),
    _v("sp.crediti_entro", SP_ATTIVO, "SP C.II Crediti esigibili entro l'esercizio", (None, r"esigibili entro l'esercizio successivo"), uso=RESIDUO, facoltativa=True),
    _v("sp.crediti_oltre", SP_ATTIVO, "SP C.II Crediti esigibili oltre l'esercizio", (None, r"esigibili oltre l'esercizio successivo"), uso=RESIDUO, facoltativa=True),
    _v("sp.disp_liquide", SP_ATTIVO, "SP C.IV Disponibilità liquide", ("iv -", r"disponibilit\w* liquide"), (None, r"totale disponibilit\w* liquide"), uso=RESIDUO, facoltativa=True),
    _v("sp.ratei_att", SP_ATTIVO, "SP D) Ratei e risconti attivi", ("d)", r"ratei e risconti"), uso=RESIDUO, facoltativa=True),
    _v("sp.capitale", SP_PASSIVO, "SP A.I Capitale", ("i -", r"capitale"), uso=RESIDUO, facoltativa=True),
    _v("sp.ris_sovr", SP_PASSIVO, "SP A.II Riserva da sovrapprezzo", ("ii -", r"riserva da so\w*prezzo"), uso=RESIDUO, facoltativa=True),
    _v("sp.ris_riv", SP_PASSIVO, "SP A.III Riserve di rivalutazione", ("iii -", r"riserve di rivalutazione"), uso=RESIDUO, facoltativa=True),
    _v("sp.ris_leg", SP_PASSIVO, "SP A.IV Riserva legale", ("iv -", r"riserva legale"), uso=RESIDUO, facoltativa=True),
    _v("sp.ris_stat", SP_PASSIVO, "SP A.V Riserve statutarie", ("v -", r"riserve statutarie"), uso=RESIDUO, facoltativa=True),
    _v("sp.ris_altre", SP_PASSIVO, "SP A.VI Altre riserve", ("vi -", r"altre riserve"), (None, r"totale altre riserve"), uso=RESIDUO, facoltativa=True),
    _v("sp.ris_cop", SP_PASSIVO, "SP A.VII Riserva operazioni di copertura", ("vii -", r"riserva per operazioni"), uso=RESIDUO, facoltativa=True),
    _v("sp.utili_nuovo", SP_PASSIVO, "SP A.VIII Utili (perdite) portati a nuovo", ("viii -", r"utili \(perdite\) portati a nuovo"), uso=RESIDUO, facoltativa=True),
    _v("sp.fondi", SP_PASSIVO, "SP B) Fondi per rischi e oneri", ("b)", r"fondi per rischi e oneri"), (None, r"totale fondi per rischi e oneri"), uso=RESIDUO, facoltativa=True),
    _v("sp.tfr", SP_PASSIVO, "SP C) TFR", ("c)", r"trattamento di fine rapporto"), uso=RESIDUO, facoltativa=True),
    _v("sp.debiti_entro", SP_PASSIVO, "SP D) Debiti esigibili entro l'esercizio", (None, r"esigibili entro l'esercizio successivo"), uso=RESIDUO, facoltativa=True),
    _v("sp.debiti_oltre", SP_PASSIVO, "SP D) Debiti esigibili oltre l'esercizio", (None, r"esigibili oltre l'esercizio successivo"), uso=RESIDUO, facoltativa=True),
    _v("sp.deb_banche", SP_PASSIVO, "SP D.4 Debiti verso banche", ("4)", r"debiti verso banche", False), uso=RESIDUO, facoltativa=True),
    _v("sp.deb_fornitori", SP_PASSIVO, "SP D.7 Debiti verso fornitori", ("7)", r"debiti verso fornitori", False), uso=RESIDUO, facoltativa=True),
    _v("sp.deb_tributari", SP_PASSIVO, "SP D.12 Debiti tributari", ("12)", r"debiti tributari", False), uso=RESIDUO, facoltativa=True),
    _v("sp.deb_previdenza", SP_PASSIVO, "SP D.13 Debiti verso istituti di previdenza", ("13)", r"debiti verso istituti di previdenza", False), uso=RESIDUO, facoltativa=True),
    _v("sp.deb_altri", SP_PASSIVO, "SP D.14 Altri debiti", ("14)", r"altri debiti", False), uso=RESIDUO, facoltativa=True),
    _v("sp.ratei_pass", SP_PASSIVO, "SP E) Ratei e risconti passivi", ("e)", r"ratei e risconti"), uso=RESIDUO, facoltativa=True),
)


def _righe_foglio(rimanenze):
    """Righe di input di flussi_cassa_impresa. Formule (13,18,20,22,24,31,33) e manuali (28,29,30,32) escluse."""
    return (
        RigaFoglio(10, "Ricavi netti (A1)", (("ce.A1", 1),)),
        RigaFoglio(11, "Variazione rimanenze (A2/A3)", rimanenze, controllo="ce.A"),
        RigaFoglio(12, "Altri ricavi operativi (A5)", (("ce.A5", 1),)),
        RigaFoglio(14, "Materie prime (B6)", (("ce.B6", 1),)),
        RigaFoglio(15, "Servizi (B7)", (("ce.B7", 1),)),
        RigaFoglio(16, "Personale (B9)", (("ce.B9", 1),)),
        RigaFoglio(17, "Altri costi operativi (B8/B11/B14)", (("ce.B8", 1), ("ce.B11", 1), ("ce.B14", 1)), controllo="ce.B"),
        RigaFoglio(19, "Ammortamenti e svalutazioni (B10)", (("ce.B10", 1),)),
        RigaFoglio(21, "Oneri/proventi finanziari netti", (("ce.C15", 1), ("ce.C16", 1), ("ce.C17", -1), ("ce.C17bis", 1)),
                   controllo="ce.C", forza_inferenza=True,
                   nota="Segno: positivo = proventi netti, negativo = oneri netti; verificare la convenzione del foglio."),
        RigaFoglio(23, "Imposte", (("ce.I20", 1),),
                   nota="Verificare voce: il foglio cita la 'voce 22', nell'art. 2425 c.c. vigente le imposte sono la voce 20."),
    )


def _controlli(rimanenze):
    """(nome, chiave del totale, [(chiave del componente, segno)]). Un componente assente vale zero."""
    return (
        ("Totale valore della produzione = A1 + A2/A3 + A4 + A5", "ce.A", (("ce.A1", 1), *rimanenze, ("ce.A4", 1), ("ce.A5", 1))),
        ("Totale costi della produzione = somma B6..B14", "ce.B",
         tuple((k, 1) for k in ("ce.B6", "ce.B7", "ce.B8", "ce.B9", "ce.B10", "ce.B11", "ce.B12", "ce.B13", "ce.B14"))),
        ("Differenza = A - B", "ce.AB", (("ce.A", 1), ("ce.B", -1))),
        ("Totale proventi e oneri finanziari = 15 + 16 - 17 ± 17-bis", "ce.C",
         (("ce.C15", 1), ("ce.C16", 1), ("ce.C17", -1), ("ce.C17bis", 1))),
        ("Risultato prima delle imposte = (A - B) + C + D", "ce.RAI", (("ce.AB", 1), ("ce.C", 1), ("ce.D", 1))),
        ("Utile = risultato prima delle imposte - imposte", "ce.U21", (("ce.RAI", 1), ("ce.I20", -1))),
        ("Totale attivo = Totale passivo", "sp.tot_attivo", (("sp.tot_passivo", 1),)),
        ("Utile dello stato patrimoniale = utile del conto economico", "sp.utile", (("ce.U21", 1),)),
    )


_DATE = re.compile(r"(\d{2})[-/.](\d{2})[-/.](\d{4})\s+(\d{2})[-/.](\d{2})[-/.](\d{4})")
_CIFRE = r"(?:\d{1,3}(?:\.\d{3})+|\d+)(?:,\d{1,2})?"
_NUM = re.compile(rf"\({_CIFRE}\)|-?{_CIFRE}-?")
_VOCE_NUMERATA = re.compile(r"\d+(-bis|-ter)?\)")
_NO = object()


_COD_LETTERA = re.compile(r"^\d{1,2}\.([A-Da-d])(?:\.(\d{1,2}(?:-bis)?))?$")
_COD_NUMERO = re.compile(r"^\d{1,2}\.(\d{2})$")
_TOTALI = {"A": "totale valore della produzione", "B": "totale costi della produzione",
           "C": "totale proventi e oneri finanziari", "D": "totale rettifiche di valore"}
_INIZI_NOTI = ("differenza tra", "risultato prima", "utile (perdita)", "totale")
_BILANCIO_AL = re.compile(r"\bbilancio al (\d{2})/(\d{2})/(\d{4})", re.I)


# Bilancio di verifica: codici di conto dello stato patrimoniale -> etichette standard (voci di sintesi; il dettaglio non si tocca).
# Il testo che segue il codice viene sostituito con l'etichetta standard e lo stato scende a INFERENZA.
_SP_CODICI = {
    "1": "totale attivo", "1.A": "a) crediti verso soci", "1.B.1": "totale immobilizzazioni immateriali", "1.B.2": "totale immobilizzazioni materiali",
    "1.B.3": "totale immobilizzazioni finanziarie", "1.C.1": "totale rimanenze", "1.C.2": "crediti esigibili entro l'esercizio successivo",
    "1.C.4": "totale disponibilità liquide", "1.D": "d) ratei e risconti",
    "2": "totale passivo", "2.A": "totale patrimonio netto", "2.A.1": "i - capitale", "2.A.2": "ii - riserva da sovrapprezzo",
    "2.A.4": "iv - riserva legale", "2.A.6": "vi - altre riserve", "2.A.8": "viii - utili (perdite) portati a nuovo",
    "2.A.9": "ix - utile (perdita) dell'esercizio", "2.B": "totale fondi per rischi e oneri", "2.C": "c) trattamento di fine rapporto",
    "2.D": "totale debiti", "2.E": "e) ratei e risconti",
}


def _traduci(riga, sezione):
    """Bilanci di verifica con codici di conto (es. 3.B.7, 3.20): riporta la riga alla forma numerata art. 2425.

    Le righe di dettaglio (codici più profondi) non si toccano. Restituisce (riga, tradotta).
    """
    parti = riga.split(None, 1)
    if sezione in (SP_ATTIVO, SP_PASSIVO):
        if len(parti) == 2 and parti[0] in _SP_CODICI:
            importi = re.search(r"((?:\s+(?:\(?-?[\d.]+(?:,\d{1,2})?\)?-?|-))+)\s*$", parti[1])
            return _SP_CODICI[parti[0]] + (importi.group(1) if importi else ""), True
        return riga, False
    if sezione != CE:
        return riga, False
    parti = riga.split(None, 1)
    if len(parti) < 2:
        return riga, False
    codice, etichetta = parti
    e = re.sub(r"\s+", " ", etichetta.replace("’", "'")).strip()
    m = _COD_LETTERA.match(codice)
    if m:
        lettera, numero = m.group(1).upper(), m.group(2)
        e = re.sub(r"\b(ed)\b", "e", e, flags=re.I)
        if numero:
            if lettera == "B":
                e = re.sub(r"^costi ", "", e, flags=re.I)
            return f"{numero}) {e}", True
        return f"{_TOTALI[lettera]} {e}", True
    m = _COD_NUMERO.match(codice)
    if m and m.group(1) in ("20", "21", "22"):
        return f"{int(m.group(1))}) {e}", True
    if re.match(r"^\d{1,2}(\.[A-Za-z0-9_-]+)+$", codice) and e.lower().startswith(_INIZI_NOTI):
        return e, True
    return riga, False


def _norm(testo):
    return re.sub(r"\s+", " ", testo.replace("’", "'")).strip().lower()


def _numero(tok):
    if tok == "-":
        return None
    if not _NUM.fullmatch(tok):
        return _NO
    cifre = tok.strip("()-").replace(".", "").replace(",", ".")
    valore = float(cifre) if "." in cifre else int(cifre)
    return -valore if tok[0] in "(-" or tok[-1] == "-" else valore


def _dividi(riga):
    """Separa etichetta e i due importi finali; None se la riga non termina con due importi."""
    parti = riga.split()
    if len(parti) < 3:
        return None
    valori = [_numero(t) for t in parti[-2:]]
    if _NO in valori:
        return None
    return " ".join(parti[:-2]), valori


def _chiave_riga(testo):
    return re.sub(r"\s+", " ", testo).strip()


def _posizioni(pagina):
    """Per ogni riga della pagina, la coordinata destra (x1) di ogni parola. Serve solo per le righe con un solo importo."""
    try:
        parole = pagina.extract_words()
    except Exception:  # la posizione è un aiuto: se manca, le righe con un solo importo restano non lette
        return {}
    righe = []
    for w in sorted(parole, key=lambda w: (round(w["top"]), w["x0"])):
        if righe and abs(righe[-1][0] - w["top"]) <= 3:
            righe[-1][1].append(w)
        else:
            righe.append([w["top"], [w]])
    risultato = {}
    for _, ws in righe:
        ws.sort(key=lambda w: w["x0"])
        risultato[_chiave_riga(" ".join(w["text"] for w in ws))] = [w["x1"] for w in ws]
    return risultato


def _ancore(testo, posizioni):
    """Coordinate destre delle due colonne di importi della pagina, dalle righe con due importi."""
    a1, a2 = [], []
    for riga in testo.splitlines():
        if _dividi(riga.strip()) is None:
            continue
        x1 = posizioni.get(_chiave_riga(riga))
        if x1 and len(x1) == len(riga.split()):
            a1.append(x1[-2])
            a2.append(x1[-1])
    if len(a1) < 3:
        return None
    a1.sort()
    a2.sort()
    return a1[len(a1) // 2], a2[len(a2) // 2]


def _dividi_uno(riga, posizioni, ancore):
    """Riga con un solo importo: lo attribuisce alla colonna per posizione, l'altra colonna vale zero."""
    if ancore is None:
        return None
    parti = riga.split()
    x1 = posizioni.get(_chiave_riga(riga))
    if len(parti) < 2 or not x1 or len(x1) != len(parti):
        return None
    valore = _numero(parti[-1])
    if valore is _NO or valore is None or _numero(parti[-2]) is not _NO:
        return None
    d1, d2 = abs(x1[-1] - ancore[0]), abs(x1[-1] - ancore[1])
    if min(d1, d2) > 12:
        return None
    return " ".join(parti[:-1]), ([valore, 0] if d1 < d2 else [0, valore])


def _abbina(etichetta, sezione, unita):
    for voce in VOCI:
        if voce.sezione != sezione:
            continue
        for m in voce.modelli:
            if unita and not m.unione:
                continue
            if m.codice and re.match(re.escape(m.codice) + r"\s*" + m.regex, etichetta):
                return voce, FATTO
            if re.match(m.regex, etichetta):
                # Etichetta riconosciuta ma senza il numero di voce atteso.
                return voce, (FATTO if m.codice is None else INFERENZA)
    return None


def _sezione(norm, corrente):
    """Restituisce (cambiata, nuova sezione)."""
    codificata = bool(re.match(r"^\d+ ", norm))
    norm = re.sub(r"^[\d.]+ ", "", norm)
    norm = re.sub(r"(\s+[\d.,]+-?)+$", "", norm)
    if codificata and norm in ("attivo", "passivo") and corrente in (None, CE):
        return True, (SP_ATTIVO if norm == "attivo" else SP_PASSIVO)
    if norm == "stato patrimoniale":
        return True, SP
    if norm == "attivo" and corrente in (SP, SP_ATTIVO, SP_PASSIVO):
        return True, SP_ATTIVO
    if norm == "passivo" and corrente in (SP, SP_ATTIVO, SP_PASSIVO):
        return True, SP_PASSIVO
    if norm == "conto economico":
        return True, CE
    if norm.startswith(("nota integrativa", "rendiconto finanziario")):
        return True, None
    return False, corrente


def _leggi_righe(pagine, posizioni=None):
    """Scorre il testo e restituisce (voci trovate, esercizi, righe non mappate, n. righe di dettaglio)."""
    trovati, non_mappate, dettaglio = {}, [], 0
    esercizi, sezione, date_viste = None, None, []
    for n_pagina, testo in pagine:
        pendente = None  # riga di sola etichetta: può essere la prima metà di una voce andata a capo
        pos = (posizioni or {}).get(n_pagina, {})
        ancore = _ancore(testo, pos) if pos else None
        for riga in testo.splitlines():
            grezza = riga.strip()
            if not grezza:
                continue
            m = _DATE.search(grezza)
            if m and esercizi is None:
                g1, m1, a1, g2, m2, a2 = m.groups()
                esercizi = [f"{a1}-{m1}-{g1}", f"{a2}-{m2}-{g2}"]
            if esercizi is None:
                b = _BILANCIO_AL.search(grezza)
                if b:
                    g, mm, a = b.groups()
                    date_viste.append(f"{a}-{mm}-{g}")
                    if len(date_viste) == 2:
                        esercizi = date_viste
            norm = _norm(_DATE.sub("", grezza))
            if not norm:
                pendente = None
                continue
            cambiata, sezione = _sezione(norm, sezione)
            if cambiata and not re.match(r"^[12] (attivo|passivo) [\d.]", norm):  # "1 ATTIVO <importi>": è anche il totale
                pendente = None
                continue
            if sezione is None:
                continue
            originale = grezza
            grezza, tradotta = _traduci(grezza, sezione)
            diviso, posizionale = _dividi(grezza), False
            if diviso is None and sezione == CE:
                diviso = _dividi_uno(originale, pos, ancore)
                posizionale = diviso is not None
                if posizionale:
                    diviso = (_traduci(diviso[0], sezione)[0], diviso[1])
            if diviso is None:
                pendente = grezza
                continue
            etichetta, valori = _norm(diviso[0]), diviso[1]
            esito, unita, letto = _abbina(etichetta, sezione, False), False, originale
            if esito is None and pendente:
                esito = _abbina(_norm(pendente) + " " + etichetta, sezione, True)
                unita = esito is not None
                if unita:
                    letto = pendente + " / " + grezza
            pendente = None
            if esito is None:
                if sezione == CE and _VOCE_NUMERATA.match(etichetta):
                    non_mappate.append({"pagina": n_pagina, "sezione": sezione, "testo": grezza})
                else:
                    dettaglio += 1
                continue
            voce, stato = esito
            note = []
            if posizionale:
                stato = peggiore(stato, INFERENZA)
                note.append("Un solo importo sulla riga: colonna attribuita dalla posizione, l'altra colonna considerata zero.")
            if tradotta and sezione in (SP_ATTIVO, SP_PASSIVO):
                stato = peggiore(stato, INFERENZA)
                note.append("Bilancio di verifica: voce di sintesi riconosciuta dal codice di conto.")
            if unita:
                stato = INFERENZA
                note.append("Etichetta ricostruita da due righe del documento.")
            elif stato == INFERENZA:
                note.append("Etichetta riconosciuta senza il numero di voce atteso.")
            nuovo = {"valori": valori, "stato": stato, "pagina": n_pagina, "testo": letto, "note": note, "unita": unita}
            prec = trovati.get(voce.chiave)
            if prec is None or (prec["unita"] and not unita):
                trovati[voce.chiave] = nuovo
            elif not unita and prec["valori"] != valori:
                prec["stato"] = DA_VERIFICARE
                prec["note"].append(f"Voce letta più volte con importi diversi (anche a pag. {n_pagina}).")
    return trovati, esercizi, non_mappate, dettaglio


def analizza(percorso) -> dict:
    """Estrae il bilancio dal PDF. Non scrive nulla: restituisce il dizionario del JSON."""
    percorso = Path(percorso)
    with pdfplumber.open(percorso) as pdf:
        pagine = [(i, p.extract_text() or "") for i, p in enumerate(pdf.pages, 1)]
        posizioni = {i: _posizioni(p) for i, p in enumerate(pdf.pages, 1)}
    con_testo = [n for n, t in pagine if t.strip()]
    risultato = {
        "schema": SCHEMA,
        "documento": {"file": percorso.name, "tipo": TIPO, "pagine": len(pagine), "pagine_con_testo": con_testo},
        "esito": "COMPLETATO",
        "esercizi": [],
        "foglio": [],
        "dati": [],
        "residui": [],
        "controllo": [],
        "controlli": [],
        "voci_facoltative_assenti": [],
        "righe_non_mappate": [],
        "righe_di_dettaglio_ignorate": 0,
        "avvisi": [],
    }
    if not con_testo:
        risultato["esito"] = "FERMATO: SCANSIONE"
        risultato["avvisi"].append("Nessun testo estraibile: il documento sembra una scansione. OCR non previsto (SPECIFICA.md, regola 11).")
        return risultato
    senza_testo = [n for n, _ in pagine if n not in con_testo]
    if senza_testo:
        risultato["avvisi"].append(f"Pagine senza testo estraibile: {senza_testo}.")

    trovati, esercizi, non_mappate, dettaglio = _leggi_righe(pagine, posizioni)
    risultato["righe_non_mappate"] = non_mappate
    risultato["righe_di_dettaglio_ignorate"] = dettaglio
    if non_mappate:
        risultato["avvisi"].append("Voci numerate del conto economico con importi ma non mappate: i totali possono non quadrare.")

    # Riga 11: se il documento riporta la voce raggruppata "2), 3)", le righe di dettaglio 2) e 3) si ignorano.
    if "ce.A23" in trovati:
        trovati.pop("ce.A2", None)
        trovati.pop("ce.A3", None)
        rimanenze = (("ce.A23", 1),)
    else:
        rimanenze = (("ce.A2", 1), ("ce.A3", 1))
    righe = _righe_foglio(rimanenze)
    riga_di = {k: rf.riga for rf in righe for k, _ in rf.componenti}

    # Ruolo delle due colonne del PDF: l'esercizio più recente è l'Anno -1.
    if esercizi is None:
        anni = [None, None]
        risultato["avvisi"].append("Intestazione con le date degli esercizi non trovata: colonne non attribuibili, tutto DA VERIFICARE.")
    else:
        anni = [-1, -2] if esercizi[0] > esercizi[1] else [-2, -1]
        risultato["esercizi"] = [
            {"colonna_pdf": i + 1, "data_chiusura": esercizi[i], "anno": anni[i], "colonna_excel": COLONNA[anni[i]]} for i in (0, 1)
        ]
    if "ce.A4" in trovati:
        risultato["avvisi"].append("Voce A4 presente: la mappa del foglio non prevede una riga, è riportata tra i residui.")

    per = {}
    for voce in VOCI:
        t = trovati.get(voce.chiave)
        if t is None and voce.facoltativa:
            risultato["voci_facoltative_assenti"].append(voce.chiave)
            continue
        for i in (0, 1):
            dato = {
                "chiave": voce.chiave,
                "voce": voce.nome,
                "esercizio": esercizi[i] if esercizi else None,
                "anno": anni[i],
                "valore": None,
                "stato": DA_VERIFICARE,
                "fonte": {"file": percorso.name, "tipo_documento": TIPO, "pagina": None, "testo_letto": None},
                "destinazione": None,
                "note": [],
            }
            if voce.uso == EXCEL:
                dato["destinazione"] = {"foglio": FOGLIO, "colonna": COLONNA.get(anni[i]), "riga": riga_di[voce.chiave]}
            if t is None:
                dato["note"].append("Voce non trovata nel documento.")
            else:
                dato["valore"] = t["valori"][i]
                dato["stato"] = t["stato"]
                dato["fonte"].update(pagina=t["pagina"], testo_letto=t["testo"])
                dato["note"] = list(t["note"])
                if dato["valore"] is None:
                    dato["stato"] = DA_VERIFICARE
                    dato["note"].append("Importo assente per questo esercizio.")
                if esercizi is None:
                    dato["stato"] = DA_VERIFICARE
            per[voce.chiave, i] = dato
            risultato[{EXCEL: "dati", RESIDUO: "residui", CONTROLLO: "controllo"}[voce.uso]].append(dato)

    def valore(k, i):
        return per[k, i]["valore"] if (k, i) in per else None

    facoltative = {v.chiave for v in VOCI if v.facoltativa}

    def principale(componenti):
        """Prima componente obbligatoria: se manca, il controllo non è eseguibile (evita falsi KO su somme parziali)."""
        return next((k for k, _ in componenti if k not in facoltative), componenti[0][0])

    # Controllo fallito: DA VERIFICARE solo il totale; le componenti mantengono lo stato e ricevono una nota.
    esiti = {}
    for nome, totale, componenti in _controlli(rimanenze):
        for i in (0, 1):
            atteso = valore(totale, i)
            presenti = [k for k, _ in componenti if valore(k, i) is not None]
            esito = {"nome": nome, "chiave": totale, "esercizio": per[totale, i]["esercizio"], "anno": anni[i], "esito": NON_ESEGUIBILE, "atteso": atteso, "ricalcolato": None}
            if atteso is not None and presenti and principale(componenti) in presenti:
                ricalcolato = sum((valore(k, i) or 0) * segno for k, segno in componenti)
                esito["ricalcolato"] = ricalcolato
                esito["esito"] = OK if abs(ricalcolato - atteso) < 0.5 else KO
                if esito["esito"] == KO:
                    per[totale, i]["stato"] = DA_VERIFICARE
                    per[totale, i]["note"].append(f"Controllo fallito: {nome}.")
                    for k in presenti:
                        per[k, i]["note"].append(f"Componente di un controllo fallito: {nome}.")
            esiti[totale, i] = esito["esito"]
            risultato["controlli"].append(esito)

    for rf in righe:
        celle = {}
        for i in (0, 1):
            c = cella(rf, {k: per[k, i] for k, _ in rf.componenti if (k, i) in per}, esiti.get((rf.controllo, i)))
            if anni[i] is None:
                c["stato"] = DA_VERIFICARE
            celle[COLONNA.get(anni[i], f"?{i + 1}")] = c
        risultato["foglio"].append({"riga": rf.riga, "voce": rf.nome, "componenti": [k for k, _ in rf.componenti], "celle": celle})
    from .modello_aziende import celle_aziende
    risultato["modello_aziende"] = celle_aziende(risultato)
    return risultato
