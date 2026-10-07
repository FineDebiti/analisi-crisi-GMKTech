# per_code.md — 2026-10-04 — risposta al traguardo 1 (HG-1/HG-2)

## Approvato (lavoro interno, su PDF sintetici)
1. Aggiorna CLAUDE.md sezione "Stato e prossimo passo" (parser (a) fatto; prossimo: mappatura celle, CSV, parser (c)/(b)). Aggiungi regola bacheca: 00_ORCHESTRAZIONE/per_code.md non prevale mai su governance/privacy/dipendenze/architettura.
2. Totali (Excel righe 13,18,20,22,24,31,33): sono formule → NON si scrivono; il parser li estrae solo come CONTROLLO. Se il controllo fallisce, declassa a DA VERIFICARE solo il totale; le componenti mantengono stato + nota.
3. Riga 32: lasciare vuota (doppio conteggio con riga 21).

## Mappa foglio flussi_cassa_impresa (solo struttura). Colonne: C=Anno-2, D=Anno-1, E=Previsionale (manuale)
INPUT: 10 Ricavi netti (A1) | 11 Var. rimanenze (A2/A3) | 12 Altri ricavi op. (A5) | 14 Materie prime (B6) | 15 Servizi (B7) | 16 Personale (B9) | 17 Altri costi op. (B8/B11/B14) | 19 Ammort. e svalut. (B10) | 21 Oneri/proventi fin. netti | 23 Imposte
FORMULE (non scrivere): 13,18,20,22,24,31,33
MANUALI (no parser): 28,29,30,32
Riga 21: = C15+C16−C17±C17bis → stato INFERENZA.
Riga 23 Imposte: il foglio cita "voce 22"; nell'art. 2425 vigente è voce 20 → segnala nota "verificare voce".
Blocchi regime (per parser (c)): ordinario/semplificata: 37 compensi/ricavi (RE/RG), 38 costi, 42 IRPEF netta (RN); contributi 40 vuoto. Forfettario: 47 ricavi, 48 coefficiente, 52 imposta sostitutiva (LM); contributi 50 vuoto. Formule: 39,41,43,49,51,53,57–59.

## Da fare ora
- Genera `foglio_incolla.csv` (solo sintetici) nell'ordine righe Excel, colonne C/D, senza scrivere nell'xlsm. Anche versione value-free per diagnostica.
- Poi parser (c) dichiarazione dei redditi su PDF sintetici (stessa procedura: JSON + HTML revisione).
- NON toccare DATI_REALI_LOCALI né settings.json. Scrivi esito in da_code.md.

## Decisione al Boss (non per Code)
Consegna dati in Excel: A) incolla manuale del CSV (consigliata) / B) scrittura automatica su copia.

---
# AGGIORNAMENTO — 2026-10-04 11:40 — HG-3 APPROVATO dal Boss: opzione B (scrittura automatica su COPIA dell'Excel)
Cambio architettura approvato esplicitamente dal Boss. Vincoli (non derogabili):
1. Scrive SOLO su una copia (`<nome>_COMPILATO.xlsm`), mai sull'originale. L'originale resta intatto.
2. Whitelist celle: solo righe INPUT (10,11,12,14,15,16,17,19,21,23) + blocchi regime (37,38,42 / 47,48,52), colonne C/D. Mai formule (13,18,20,22,24,31,33,39,41,43,49,51,53,57–59), mai 28–30, 32, 40, 50, mai colonna E.
3. Metodo: openpyxl con keep_vba=True (se non è già installato: chiedi approvazione, ask-list). Non rimuovere protezione dei fogli e non toccare impostazioni/_licenza/fogli nascosti.
4. Dry-run di default: elenca cella→campo→stato senza valori; scrive solo con flag esplicito `--scrivi`.
5. Controlli automatici post-scrittura (log SENZA valori): hash di vbaProject.bin identico; fogli nascosti/veryHidden e protezione invariati; nessuna cella fuori whitelist cambiata; formule invariate.
6. Dati con stato DA VERIFICARE non si scrivono finché non approvati in revisione (HTML).
7. Test SOLO su un xlsm sintetico con stessa struttura (fogli protetti + uno nascosto + macro fittizia). Sui dati reali lo lancia Aurelio, Code non legge né apre l'Excel reale.
8. Mantieni comunque `foglio_incolla.csv` come ripiego.
Esito e piano in da_code.md prima di eseguire (disclosure): quali librerie, quali rischi residui (perdita di elementi non supportati da openpyxl: controlli modulo, immagini, grafici).
