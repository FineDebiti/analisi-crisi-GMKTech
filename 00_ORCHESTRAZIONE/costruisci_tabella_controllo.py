"""Tabella di controllo della revisione v3: correzione richiesta | modifica effettuata | pagina | esito | impedimento.
Le pagine sono lette dai PDF generati (sezione -> pagina). Non contiene valori dei casi reali."""
import re, subprocess, sys
from pathlib import Path
RAD = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAD))
from analisi_crisi import word_xml as w

def pagine(pdf):
    """Restituisce ({sezione: (pagina_inizio, pagina_fine)}, n_pagine, pagina_appendici)."""
    n = int(re.search(r"Pages:\s+(\d+)", subprocess.run(["pdfinfo", pdf], capture_output=True, text=True).stdout).group(1))
    inizio, app, in_testa = {}, None, {}
    for p in range(1, n + 1):
        t = subprocess.run(["pdftotext", "-f", str(p), "-l", str(p), "-layout", pdf, "-"], capture_output=True, text=True).stdout
        righe = [x for x in t.splitlines() if x.strip()]
        for m in re.finditer(r"^\s*(\d)\. [A-Z]", t, re.M):
            if m.group(1) not in inizio:
                inizio[m.group(1)] = p
                in_testa[m.group(1)] = any(re.match(r"\s*\d\. [A-Z]", x) for x in righe[:2])
        if "APPENDICI" in t and app is None:
            app = p
    sez = {}
    chiavi = sorted(inizio)
    for i, k in enumerate(chiavi):
        if i + 1 < len(chiavi):
            nxt = chiavi[i + 1]
            fine = inizio[nxt] - 1 if in_testa[nxt] else inizio[nxt]
        else:
            fine = (app - 1) if app else n
        sez[k] = (inizio[k], max(inizio[k], fine))
    return sez, n, app

def pg(sez, chiavi):
    iv = [sez[k] for k in chiavi if k in sez]
    if not iv:
        return "n.d."
    a_, b_ = min(x[0] for x in iv), max(x[1] for x in iv)
    return f"p. {a_}" if a_ == b_ else f"pp. {a_}-{b_}"

def main(pdf_e, pdf_m, out):
    E, nE, aE = pagine(pdf_e); M, nM, aM = pagine(pdf_m)
    corpo_e = aE - 1; corpo_m = aM - 1
    def due(chiavi): return f"E: {pg(E, chiavi)}\nM: {pg(M, chiavi)}"
    R = [["N.", "Correzione richiesta", "Modifica effettuata", "Pagina", "Esito", "Impedimento o limite residuo"]]
    R += [
     ["1", "Eurocasa: normalizzare gli oneri straordinari della nota integrativa 2021; mostrare ogni rettifica e l'effetto sul margine; se manca il 2022, dichiararne l'impatto sul giudizio.",
      "Tabella di normalizzazione 2021 con quattro rettifiche quantificate (oneri straordinari, contributi, sopravvenienze, vendite di merci da smobilizzo) e margine progressivo riga per riga; due rettifiche non quantificabili elencate. Per il 2022: ipotesi H1 etichettata IPOTESI e impatto sul giudizio in tre punti.",
      f"E: {pg(E, ['4'])}", "APPLICATA CON LIMITE", "La nota non indica l'importo per componente (IMU/TARI, stralci di attivo): l'EBITDA normalizzato 2021 è un limite superiore. Il dettaglio 2022 non esiste: il 2022 non entra nel giudizio come dato."],
     ["2", "Eliminare la classificazione automatica «EBITDA positivo = crisi finanziaria; negativo = crisi industriale» e ricostruire le cause.",
      "Regola assente dal motore v3 (un test automatico la esclude). La sezione 3 ricostruisce le cause da evidenze, con stato FATTO / INFERENZA / IPOTESI e fonte (sette cause per Eurocasa, cinque per Mercurio).",
      due("3"), "APPLICATA", "Le cause derivano solo dai documenti: manca l'intervista al liquidatore o all'imprenditore (indicata come IPOTESI da verificare)."],
     ["3", "Non qualificare come aggiornati documenti del 2020; distinguere data di acquisizione, data del documento, periodo economico.",
      "La sezione 2 riporta le tre date per ogni documento. Ruoli, CAI, CRIF e CTC (ottobre-novembre 2020) e visura (2022) sono STORICO non aggiornato; nessuna relazione usa «AGGIORNATO» per dati del 2020. Corretto l'esito «nessun dato» di CAI, CRIF e CTC, prima presentato senza data.",
      due("2"), "APPLICATA CON LIMITE", "La data di acquisizione è quella di salvataggio nella cartella del caso: la ricezione dal cliente non è tracciata. Serve un registro dei caricamenti nell'app (non ancora costruito)."],
     ["4", "Sostituire «massa passiva = max(bilancio, ruoli)» con una riconciliazione per creditore e posizione; se impossibile, debito provvisorio con omissioni e duplicazioni.",
      "Formula eliminata. Tabella per creditore e posizione, riconciliazione per classe (Eurocasa: scritture 2021 contro ruoli 2020; Mercurio: 2025 contro 2024), stato PROVVISORIA, elenco di omissioni e duplicazioni possibili. Emerso che i ruoli 2020 non sono sommabili alle scritture 2021.",
      due("5"), "APPLICATA CON LIMITE", "Corrispondenza cartella per cartella non dimostrabile (scritture aggregate); per Mercurio nessun estratto di ruolo. Il debito resta PROVVISORIO."],
     ["5", "Mercurio: eliminare gli zeri associati a dati mancanti; verificare ammortamenti 2024, composizione di crediti e liquidità; valutare l'adeguatezza del patrimonio.",
      "«non disponibile» al posto degli zeri (rimanenze, compenso, ruoli, Centrale Rischi). Ammortamenti 2024: voce B10 assente e fondi invariati, quindi zero è un fatto contabile con effetto su risultato e patrimonio (stima). Crediti e liquidità scomposti per voce; patrimonio valutato per adeguatezza (rettificato, attivo di recupero incerto, debito pubblico). Emerse sopravvenienze 2024 che alterano l'EBITDA.",
      f"M: {pg(M, ['4', '5', '6'])}", "APPLICATA CON LIMITE", "Ammortamento 2024 stimato, non documentato; rimanenze non rilevate; il contante richiede un inventario di cassa; il bilancio è provvisorio e non depositato."],
     ["6", "Separare sostenibilità della gestione attuale e fattibilità del risanamento; non concludere «non percorribile» per la formula 50% EBITDA × 5 anni.",
      "Due giudizi distinti nella conclusione, con motivazione. La formula 50% × 5 è resa indicatore informativo non determinante (App. A) e non entra nel giudizio.",
      due("1"), "APPLICATA", "Il modulo semaforo.py (usato dalla v2) non è stato modificato: la sua riforma e dei relativi test è una decisione da approvare (HG-3)."],
     ["7", "Scenari omogenei per data, patrimonio, flussi, fabbisogni e costi; non preferire la liquidazione se il confronto è non valutabile.",
      "Tabella con le sette colonne richieste. Eurocasa: S2 e S3 NON VALUTABILI, nessuna preferenza. Mercurio: liquidazione NON VALUTABILE; scenari di continuità con e senza rientro del prestito. Un test automatico impedisce la preferenza quando il confronto è non valutabile.",
      due("7"), "APPLICATA CON LIMITE", "Per valutare S2 e S3 (Eurocasa) servono perizia e costi di procedura, assenti. I coefficienti di realizzo della v2 non sono più usati."],
     ["8", "Identificare norme e indicazioni ministeriali con fonti precise; qualificare le soglie discrezionali come parametri interni di screening.",
      "Sezione 8: CCII artt. 2, 3, 12, 13, 17, 25-novies; decreto dirigenziale 28/09/2021 (agg. 21/03/2023); CNDCEC ottobre 2019; articoli del codice civile; parametri elencati in App. B come «parametri interni di screening». Errore v2 corretto: il 5% non era una soglia del CCII.",
      due("8"), "PARZIALE", "Testo consolidato vigente non verificato per artt. 12, 17, 25-novies e codice civile (segnati «da verificare»). Tabelle di settore del CNDCEC non acquisite: indici non calcolati."],
     ["9", "Corpo di quattro o cinque pagine, schede e formule in appendice; niente tabelle spezzate, riferimenti senza corrispondenza o variabili non compilate.",
      f"Corpo di {corpo_e} pagine (E) e {corpo_m} (M); appendici A-D; righe non spezzabili, tabelle tenute insieme, formato A4; controllo automatico di segnaposto, None e nan.",
      f"E: pp. 1-{corpo_e}\nM: pp. 1-{corpo_m}", "APPLICATA CON LIMITE", "Impaginazione verificata con LibreOffice (font Aptos sostituito): in Word può slittare di qualche riga. Riferimenti interni verificati a mano."],
     ["10", "Tabella di controllo.", "Questo documento; le pagine sono lette dai PDF generati.", "-", "APPLICATA", "-"],
     ["11", "Tabella DEMO definitiva con i dati ideali.", "Cartella DEMO: tabella dei dati ideali (CSV, DOCX, PDF), caso fittizio completo e relazione DEMO prodotta con lo stesso motore.", "DEMO", "APPLICATA", "Dati fittizi. La definitività richiede la tua approvazione (HG-2)."],
     ["12", "Non richiesto, emerso durante la revisione.", "Mercurio: sopravvenienze 2024 e 2025 alterano l'EBITDA; Eurocasa: oneri diversi 2022 quasi pari alla riduzione dei crediti; liquidità Eurocasa quasi tutta sul conto della procedura esecutiva.", "-", "APPLICATA", "Sono inferenze da confermare con la documentazione."]]
    colori = {}
    for i, riga in enumerate(R[1:], 1):
        colori[(i, 4)] = {"APPLICATA": "VERDE", "APPLICATA CON LIMITE": "GIALLO", "PARZIALE": "GIALLO"}.get(riga[4])
    corpo = (w.par(w.run("TABELLA DI CONTROLLO - REVISIONE v3 DELLE RELAZIONI", True, "365F91", 30), "Corpo", dopo=40)
             + w.testo("Per ogni correzione richiesta: che cosa è stato modificato nel calcolo o nella conclusione, in quale pagina, e che cosa resta impedito. «APPLICATA» significa che cambia un calcolo, una tabella o la conclusione; "
                       "un'avvertenza da sola non è contata come correzione applicata. E = Eurocasa, M = Mercurio. Nessun valore dei casi reali compare in questa tabella.", dim=17, dopo=80)
             + w.tabella(R, [400, 1700, 3050, 1050, 1250, 2250], dim=15, colori=colori, unita=False))
    w.salva(RAD / "Template_Preanalisi_Economico-Finanziaria_CNC.docx", corpo, out, a4=True)
    print("scritto", Path(out).name)

if __name__ == "__main__":
    main(*sys.argv[1:4])
