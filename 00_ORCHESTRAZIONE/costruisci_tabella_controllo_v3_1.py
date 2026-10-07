"""Tabella di controllo v3.1 (la v3 resta conservata): correzione | modifica | pagina | esito | verifica indipendente | effetto residuo sul giudizio.
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

def main(pdf_e, pdf_m, pdf_d, out):
    E, nE, aE = pagine(pdf_e); M, nM, aM = pagine(pdf_m); D, nD, aD = pagine(pdf_d)
    corpo_e, corpo_m, corpo_d = aE - 1, aM - 1, aD - 1
    def due(chiavi): return f"E: {pg(E, chiavi)}\nM: {pg(M, chiavi)}"
    R = [["N.", "Correzione richiesta", "Modifica effettuata", "Pagina", "Esito", "Verifica indipendente", "Effetto residuo sul giudizio"]]
    R += [
     ["1", "Separare il rapporto semplificato debito/EBITDA dal test ministeriale; aggiornare il riferimento al decreto del 23/04/2026.",
      "Indicatore rinominato «rapporto semplificato» (fasce indicative 1, 3, 5 solo di riferimento). Test ministeriale A/B (debito da servire / flussi annui) come scheda separata: NON ESEGUITO in Eurocasa e Mercurio (voci mancanti elencate), ESEGUITO nella DEMO. Riferimento aggiornato al decreto 23/04/2026 (B.U. n. 10 del 31/05/2026), che aggiorna quello del 28/09/2021.",
      due("8") + "\nSchede: App. A, E", "APPLICATA CON LIMITE",
      "Revisore indipendente: decreto, struttura A/B e fasce CONFERMATI su fonte pubblica (ilcaso.it); entrata in vigore NON VERIFICABILE; Bollettino non letto.",
      "Nessun rapporto ministeriale è attribuito ai casi reali: i giudizi si fondano sul solo rapporto semplificato, dichiarato tale. Il test ministeriale richiede situazione corrente, scadenze e libro cespiti."],
     ["2", "Eurocasa: non equiparare importo delle garanzie e debito garantito; non presentare il calo dei crediti come stralcio accertato; riferire il giudizio alla gestione storica.",
      "Garanzie reali: importo dei conti d'ordine distinto dal debito dichiarato assistito da garanzia reale (nota); capienza per i chirografari «non determinabile». Calo dei crediti: causa «non accertata» (incasso, cessione, compensazione o stralcio). Giudizio di sostenibilità riferito a «gestione storica 2021-2022».",
      "E: " + pg(E, ["1", "3", "6"]), "APPLICATA",
      "CONFERMATI i valori (garanzie, debito garantito, calo crediti); corretti rimandi di pagina (scritture p. 15, non p. 13) e un riferimento interno (scheda A7); segnalata la quota di 551 non ripartita dalla nota.",
      "Sostenibilità ROSSO invariata ma ora limitata al 2021-2022; fattibilità NON CONCLUDENTE invariata. Conclusione NON DEFINITIVA: mancano perizia, debito garantito per posizione, tesoreria."],
     ["3", "Mercurio: distinguere incasso, compensazione e recupero degli anticipi; documentare tempi e recuperabilità; verificare la liquidità utilizzabile.",
      "Scenari riscritti: M2 incasso del prestito, M3 compensazione (limite superiore sulle sole controparti note, riduce il debito ma non crea cassa), M4 incasso di prestito e anticipi, M5 liquidazione. Tempi e recuperabilità dichiarati NON DOCUMENTATI (anticipi fermi da tre esercizi, prestito in crescita). Liquidità utilizzabile limitata alla banca; contanti non verificati; rapporto anche con sola banca.",
      "M: " + pg(M, ["1", "6", "7"]), "APPLICATA CON LIMITE",
      "Revisore indipendente: saldi, rapporti (10,8x; 5,0x; 7,7x; 12,2x) e scenari M2-M4 RICALCOLATI e CONFERMATI; corretto un rimando di pagina (T04 p. 2).",
      "Sostenibilità da GIALLO (v3) a ROSSO (flusso più prudente oltre 5); fattibilità CONDIZIONATA e provvisoria. NON DEFINITIVA: prestito, anticipi, tesoreria e ruoli non documentati."],
     ["4", "Eliminare l'equivalenza EBITDA contabile = cassa disponibile; correggere l'ipotesi di duplicazione tra finanziamenti soci e debiti bancari garantiti.",
      "In tutte le relazioni: «l'EBITDA non è cassa»; criterio «flusso di cassa disponibile» NON VERIFICATO e tesoreria tra i dati decisivi. Duplicazione corretta: possibile solo se il conto soci nasce da rate o escussioni pagate dai soci; la semplice garanzia dei soci non duplica il debito.",
      due("1") + "\nM: sez. 5", "APPLICATA CON LIMITE",
      "Verificato nel testo di entrambe le relazioni; nessun numero cambia.",
      "La sostenibilità finanziaria resta non verificata finché mancano estratti conto e rendiconto: effetto dichiarato nello stato «NON DEFINITIVA». Causale del conto soci non acquisita."],
     ["5", "Mantenere la rettifica degli ammortamenti come simulazione finché non verificata sul libro cespiti.",
      "PN rettificato rinominato SIMULAZIONE, con intervallo (massimo e alternativa con il veicolo del 2025) e fuori dal semaforo, che usa il PN contabile. L'EBITDA non cambia.",
      "M: " + pg(M, ["4", "6"]) + "; App. A", "APPLICATA CON LIMITE",
      "Revisore indipendente: importi CONFERMATI. Scoperta nuova: nel 2024 il valore lordo delle immobilizzazioni scende di 19.315,52 senza B10 e senza variazione dei fondi; la simulazione può duplicare una rettifica già avvenuta. Testo corretto.",
      "Il segno del PN rettificato resta non determinato; il semaforo non lo usa. Serve il libro cespiti e il movimento 2024 delle immobilizzazioni."],
     ["6", "DEMO: esplicitare il calcolo del flusso dopo la vendita dell'immobile; integrare scadenze e tesoreria; correggere la regola sui fondi di ammortamento.",
      "Nota di sezione 7 con il calcolo passo per passo (canone, investimenti, imposte, interessi azzerati, proventi che estinguono mutuo e fido); sezione 7-bis con scadenze (scaduto, entro 12 mesi, oltre) e budget trimestrale; regola sui fondi: ammortamento mancante mai dedotto dal confronto dei fondi, incoerenza da chiarire sul libro cespiti.",
      f"DEMO: pp. 1-{corpo_d}", "APPLICATA",
      "Revisore indipendente: S1 15,0%, S2 80,8%, test A/B 11,8x, scadenze e tesoreria RICALCOLATI e CONFERMATI. Corretti: S3 reso omogeneo (stessa liquidità utilizzabile, 76,7%) e data di elaborazione allineata al decreto.",
      "DEMO: sostenibilità ROSSO (era GIALLO), qualità ALTA, fattibilità CONDIZIONATA e definitiva. La DEMO non è ancora approvata (HG-2)."],
     ["7", "Aggiungere alla tabella di controllo la verifica indipendente e l'effetto residuo sul giudizio.",
      "Questo documento: due colonne nuove. La verifica è affidata a un revisore che non ha scritto il motore né i costruttori e ha ricalcolato dalle fonti.",
      "-", "APPLICATA", "Revisione eseguita su tre relazioni; 34 verifiche confermate, 7 discrepanze corrette, 3 punti non verificabili.", "Residui: entrata in vigore del decreto; causa della trasformazione di Eurocasa; Bollettino non letto."],
     ["8", "Nuovo modulo semaforo: sostenibilità, qualità dei dati, fattibilità; dati decisivi mancanti impediscono la conclusione definitiva.",
      "Modulo analisi_crisi/semaforo_v3.py (la v2 resta invariata e importabile). Tre giudizi nella sezione 1 e stato «DEFINITIVA / NON DEFINITIVA». Con un dato decisivo mancante la fattibilità non può essere né percorribile né non percorribile. Rapporto valutato sul flusso più prudente.",
      due("1"), "APPLICATA",
      "Test automatici del modulo (7 gruppi) superati; revisore indipendente: terminologia «semplificato», «simulazione», «NON DEFINITIVA» CONFERMATA nelle relazioni.",
      "Le soglie restano parametri interni; la loro approvazione è una decisione dell'avvocato (HG-2). La riforma del semaforo nell'interfaccia dell'app non è stata fatta (HG-3)."],
     ["9", "Mantenuti i requisiti della v3: corpo di cinque pagine, appendici, tabelle non spezzate, nessuna variabile non compilata.",
      f"Corpo di {corpo_e} pagine (E), {corpo_m} (M), {corpo_d} (DEMO); norme in sintesi nel corpo e testo completo in App. E; tabelle lunghe interrompibili solo tra le righe.",
      f"E: pp. 1-{corpo_e}\nM: pp. 1-{corpo_m}", "APPLICATA CON LIMITE", "Controllo automatico di segnaposto, None e nan superato; test di impaginazione superato.",
      "Impaginazione verificata con LibreOffice (font sostituito): in Word può slittare di qualche riga."]]
    colori = {}
    for i, riga in enumerate(R[1:], 1):
        colori[(i, 4)] = {"APPLICATA": "VERDE", "APPLICATA CON LIMITE": "GIALLO", "PARZIALE": "GIALLO"}.get(riga[4])
    corpo = (w.par(w.run("TABELLA DI CONTROLLO v3.1 - REVISIONE DELLE RELAZIONI", True, "365F91", 30), "Corpo", dopo=40)
             + w.testo("Per ogni correzione: che cosa è stato modificato, dove, l'esito della verifica indipendente e che cosa resta del giudizio. «APPLICATA» significa che cambia un calcolo, una tabella o la conclusione; "
                       "un'avvertenza da sola non è una correzione. E = Eurocasa, M = Mercurio. Nessun valore dei casi reali compare in questa tabella. HG-2 e DEMO restano NON approvate.", dim=17, dopo=80)
             + w.tabella(R, [330, 1350, 2400, 800, 1050, 1850, 1920], dim=14, colori=colori, unita=False))
    w.salva(RAD / "Template_Preanalisi_Economico-Finanziaria_CNC.docx", corpo, out, a4=True)
    print("scritto", Path(out).name)

if __name__ == "__main__":
    main(*sys.argv[1:5])
