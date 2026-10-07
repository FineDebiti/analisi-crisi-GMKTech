# da_code.md — 2026-10-04 — esito su per_code.md (traguardo 1, HG-1/HG-2)

Solo PDF sintetici. `DATI_REALI_LOCALI`, `.claude/settings.json` e l'xlsm non sono stati toccati. Nessuna nuova dipendenza. Nessun valore reale in questo file.

## Eseguito
| Punto di per_code.md | Esito |
|---|---|
| 2. Totali come CONTROLLO, mai scritti | FATTO. Le righe 13, 18, 20, 22, 24, 31, 33 non compaiono nel foglio. Controllo fallito: DA VERIFICARE solo il totale, componenti con stato invariato + nota. |
| 3. Riga 32 vuota | FATTO. Anche 28, 29, 30 non compaiono. |
| Mappa flussi_cassa_impresa | FATTO. Righe di input 10, 11, 12, 14, 15, 16, 17, 19, 21, 23; colonne C = Anno -2, D = Anno -1. Riga 21 = C15 + C16 − C17 ± C17-bis, sempre INFERENZA. Riga 23 con nota "verificare voce". |
| foglio_incolla.csv | FATTO. Accanto al PDF, in `_estratti/<nome>_foglio_incolla.csv`; versione senza valori in `diagnostica/<rapporto>_foglio.csv`. Nulla viene scritto nell'xlsm. |
| Parser (c) dichiarazione dei redditi | FATTO su tre PDF sintetici (professionista RE, impresa RG, forfettario LM): JSON + HTML di revisione + CSV. Colonna E. Righe 37, 38, 42 oppure 47, 48, 52; 40 e 50 vuote con avviso. |

Test: 6 su 6 superati (`.venv/bin/python test_sintetici/test_parser.py`).

## Non eseguito: punto 1 (CLAUDE.md)
CLAUDE.md vieta di modificare CLAUDE.md senza approvazione esplicita, e la bacheca non prevale su CLAUDE.md. Serve un "sì" di Aurelio in chat. Testo proposto (il file passa da 26 a 27 righe):

- Nuova riga in Costituzione Agentica: "La bacheca `00_ORCHESTRAZIONE/per_code.md` non prevale mai su governance, privacy, dipendenze e architettura."
- Stato: "Stato (04/10/2026): parser (a) bilancio e (c) dichiarazione funzionanti su PDF sintetici, con JSON, revisione HTML, foglio_incolla.csv e diagnostica senza valori; divieti su `DATI_REALI_LOCALI` verificati. Registro di verifica privacy in `00_GOVERNANCE_PRIVACY`."
- Prossimo passo: "Diagnostica senza valori su un documento reale (la lancia Aurelio); poi parser (b) situazione contabile."

## Scelte fatte (INFERENZA, da confermare)
- Il CSV contiene solo le righe di input, quindi non va incollato come blocco unico: sovrascriverebbe le formule intermedie.
- Riga 11: usa la voce raggruppata "2), 3)" se presente, altrimenti A2 + A3. Voci assenti: cella vuota, DA VERIFICARE.
- Righe calcolate (11, 17, 21): stato peggiore tra le componenti; INFERENZA se una voce attesa manca ma il totale del documento quadra, DA VERIFICARE se non quadra.
- Etichetta spezzata su due righe del PDF: la voce è ricostruita e diventa INFERENZA.
- Voce A4 (incrementi di immobilizzazioni): la mappa non le assegna una riga, va tra i residui con avviso.
- Utile (voce 21 del conto economico): solo controllo, nessuna cella.

## DA VERIFICARE
- Segno della riga 21: il parser dà positivo = proventi netti, negativo = oneri netti.
- Riga 48: il coefficiente è riportato in percentuale (es. 78); il formato della cella non è noto.
- Numeri di rigo della dichiarazione (RE6, RE20, RE21, RG12, RG24, RG26, RN26, LM22-27, LM34, LM39): presi dalla conoscenza del modello, non verificati sul modello dell'anno. Se la descrizione è su un rigo diverso il dato diventa INFERENZA.
- Impaginazione: le dichiarazioni sintetiche hanno una riga per rigo e non riproducono il modello ministeriale; il bilancio sintetico imita la resa XBRL. La tenuta sui documenti reali si saprà solo dalla diagnostica senza valori.
- Più quadri di reddito nello stesso PDF (RE + RG): celle 37 e 38 DA VERIFICARE, scelta manuale.

## Come si lancia
`.venv/bin/python estrai.py <percorso.pdf> [bilancio|dichiarazione]` — il tipo è riconosciuto dal testo; a video non compare alcun valore.

## File
- Nuovi: `analisi_crisi/comune.py`, `analisi_crisi/foglio.py`, `analisi_crisi/parser_dichiarazione.py`, `test_sintetici/genera_dichiarazione_fittizia.py`.
- Modificati: `analisi_crisi/parser_bilancio.py`, `analisi_crisi/revisione.py`, `analisi_crisi/diagnostica.py`, `estrai.py`, `test_sintetici/genera_bilancio_fittizio.py`, `test_sintetici/test_parser.py`.
- In `diagnostica/` restano tre rapporti del primo giro (ore 11:29) nel formato precedente: si possono eliminare.

## In attesa del Boss
Consegna dei dati in Excel: A) incolla manuale del CSV, oppure B) scrittura automatica su copia. Il CSV attuale serve l'opzione A.

---
# AGGIUNTA — 2026-10-04 — HG-3 (opzione B): piano prima di eseguire

CLAUDE.md aggiornato con il testo proposto sopra, dopo il "sì" di Aurelio in chat (27 righe).

## Librerie
- `openpyxl` con `keep_vba=True` per la scrittura: NON è installato nel `.venv`. È una nuova dipendenza: chiedo approvazione ad Aurelio e non la installo prima.
- Tutto il resto usa solo la libreria standard di Python (`zipfile`, `xml.etree`, `hashlib`): generatore dell'xlsm sintetico, dry-run, controlli post-scrittura.

## Cosa faccio subito (senza openpyxl)
1. xlsm sintetico con la struttura richiesta: fogli protetti, uno nascosto e uno veryHidden, protezione della cartella, macro fittizia (`vbaProject.bin` finto), un pulsante collegato alla macro, formule (anche una condivisa), celle manuali già compilate.
2. Whitelist e dry-run: elenco cella -> campo -> stato -> azione, senza valori.
3. Controlli post-scrittura indipendenti da openpyxl, provati su copie manomesse apposta.
4. Codice di scrittura pronto ma NON provato finché openpyxl non è approvato.

## File che creo
- `analisi_crisi/excel_scrittura.py` (whitelist, piano, scrittura sulla copia)
- `analisi_crisi/excel_verifica.py` (controlli post-scrittura, solo libreria standard)
- `compila_excel.py` (comando: dry-run di default, `--scrivi` per scrivere)
- `test_sintetici/genera_excel_fittizio.py` e `test_sintetici/test_excel.py`
- Prodotti: `test_sintetici/Fittizio.xlsm`, `Fittizio_COMPILATO.xlsm`, log in `diagnostica/scrittura_<data>.md`

## Regole applicate
- Si scrive solo su `<nome>_COMPILATO.xlsm`; se esiste già il comando si ferma. Hash dell'originale controllato prima e dopo.
- Whitelist: foglio `flussi_cassa_impresa`, righe 10, 11, 12, 14, 15, 16, 17, 19, 21, 23, 37, 38, 42, 47, 48, 52, colonne C e D.
- Non si scrive: stato DA VERIFICARE, cella vuota, cella che contiene una formula, cella bloccata in un foglio protetto. FATTO e INFERENZA si scrivono.
- La protezione non viene mai rimossa; nessun altro foglio viene modificato.

## Rischi residui
- openpyxl riscrive l'intero file: può perdere controlli modulo e ActiveX, immagini, grafici, forme, impostazioni di stampa. Con `keep_vba` conserva `vbaProject.bin` e in parte i pulsanti; l'xlsm sintetico contiene un pulsante proprio per misurarlo.
- I valori memorizzati delle formule vengono eliminati: Excel ricalcola all'apertura.
- Formule condivise: openpyxl le riscrive come formule singole; il controllo "formule invariate" su quelle celle verifica solo che la formula ci sia ancora.
- Il `vbaProject.bin` sintetico è finto: l'xlsm serve ai test automatici e Excel potrebbe non aprirlo.
- La struttura dell'xlsm sintetico è una mia ricostruzione (INFERENZA): l'Excel reale non l'ho mai visto.

## Punti da decidere
- CONFLITTO sulla colonna: il vincolo 2 ammette solo C e D e vieta E, ma la specifica mette le dichiarazioni (righe 37-52) in colonna E. Applico il vincolo alla lettera: i dati delle dichiarazioni NON vengono scritti e restano nel CSV. Serve dire in quale colonna vanno.
- Approvazione dei DA VERIFICARE (vincolo 6): l'HTML di revisione oggi è di sola lettura. Finché non esiste un modo per registrare l'approvazione, quelle celle restano non scritte.
- Alternativa senza nuove dipendenze (cambio di metodo, quindi da approvare): modificare solo l'XML del foglio dentro lo zip e copiare tutto il resto byte per byte. Elimina il rischio di perdere pulsanti, immagini e grafici.

---
# AGGIUNTA — 2026-10-04 — HG-3: esito della parte eseguita

Solo Excel sintetico (`test_sintetici/Fittizio.xlsm`). `DATI_REALI_LOCALI`, `settings.json` e l'Excel reale non sono stati toccati. Nulla è stato installato.

| Parte | Esito |
|---|---|
| xlsm sintetico (6 fogli protetti, uno nascosto, uno veryHidden, macro finta, pulsante, formule) | FATTO |
| Whitelist e dry-run senza valori (`compila_excel.py`, default) | FATTO, provato |
| Controlli post-scrittura (libreria standard) | FATTO, provati su 12 copie manomesse: ogni manomissione fa fallire solo il controllo corrispondente |
| Scrittura con openpyxl (`--scrivi`) | Codice scritto, NON PROVATO: openpyxl non è installato |

Test: 5 superati, 1 saltato (la scrittura) in `test_sintetici/test_excel.py`; i 6 test dei parser restano superati.

Controlli post-scrittura implementati: `vbaProject.bin` identico; nomi, ordine e visibilità dei fogli; protezione dei fogli e della cartella; nomi definiti; formule invariate; nessuna cella cambiata fuori dalla whitelist; celle previste scritte con il valore atteso; nessun elemento perso (pulsanti, immagini, grafici); originale con lo stesso hash prima e dopo. Se un controllo fallisce la copia viene rinominata `_COMPILATO_DA_SCARTARE`.

In attesa di Aurelio:
1. Approvazione per installare `openpyxl` nel `.venv` (oppure scelta dell'alternativa senza dipendenze descritta nel piano).
2. Colonna delle dichiarazioni: con la whitelist attuale (solo C e D) i dati dei parser (c) non vengono scritti.
3. Come registrare l'approvazione dei DA VERIFICARE.

---
# AGGIUNTA — 2026-10-04 — Orchestratore (chat) — variazione di ruolo dichiarata (Art. 4/7), richiesta dal Boss
Il Boss ha chiesto all'orchestratore di procedere direttamente, senza passaggi manuali. Ambito: sviluppo e test SOLO su file sintetici, nessun accesso a DATI_REALI_LOCALI né a settings.json.
Eseguito (HG-3 già approvato dal Boss: opzione B, metodo XML, whitelist C/D + E blocchi regime, approvazioni):
- `analisi_crisi/excel_scrittura.py`: scrittura per modifica diretta dell'XML del foglio, nessuna nuova dipendenza; resto del file identico byte per byte; ricalcolo completo all'apertura; whitelist C/D righe 10–23 e E righe 37,38,42 | 47,48,52 (un solo blocco per volta); rifiuto di formule, celle bloccate e celle assenti.
- `compila_excel.py --approvazioni <file>`; `revisione.py`: casella "approvato" per le celle DA VERIFICARE + pulsante "Salva approvazioni" (JSON senza valori).
- Test: test_excel 7/7 OK (inclusa scrittura reale su Fittizio.xlsm e dichiarazione in colonna E); test_parser 6/6 OK. Pulsante HTML non provato in browser (INFERENZA: JS semplice).
- Nota: nella VM di lavoro non è possibile eliminare file; un log di prova resta in `diagnostica/` (scrittura_20261004-095809.md, senza valori).
Prossimo: spostamento DATI_REALI_LOCALI fuori da Documents (richiede approvazione Boss su nuovo percorso e deny di settings.json).

---
# AGGIUNTA — 2026-10-04 12:3x — Orchestratore — spostamento DATI_REALI_LOCALI (approvato dal Boss)
- Spostata (mv, nessuna lettura dei file) da `~/Documents/ANALISI CRISI/DATI_REALI_LOCALI` a `~/Riservato_AnalisiCrisi/DATI_REALI_LOCALI` (permessi 700). Contenuto verificato solo per nome: 2 file.
- `settings.json`: aggiunti deny Read/Edit/Bash sul nuovo percorso (mantenuti i vecchi). Copia e hash in `00_GOVERNANCE_PRIVACY/settings_2026-10-04_v2_dopo_spostamento.*`.
- `CLAUDE.md`: aggiornato il percorso nelle regole privacy.
- DA FARE: rifare i 4 test di blocco in una NUOVA sessione Code (le impostazioni si rileggono all'avvio) e aggiornare il registro. Solo dopo, uso di dati reali.

---
# AGGIUNTA — 2026-10-04 — Code — 4 test di blocco sul nuovo percorso `~/Riservato_AnalisiCrisi/DATI_REALI_LOCALI`
- Test 1 — `ls` in shell sulla cartella: BLOCCATO
- Test 2 — Read di `CIVETTA_COMPLETO.pdf`: BLOCCATO
- Test 3 — script Python con solo `open()`: BLOCCATO
- Test 4 — `cat` in shell su `CIVETTA_COMPLETO.pdf`: BLOCCATO

---
# AGGIUNTA — 2026-10-04 — Orchestratore — registro privacy aggiornato
4 test BLOCCATO sul nuovo percorso. Creato `00_GOVERNANCE_PRIVACY/Registro_verifica_privacy_2026-10-04_Addendum_spostamento.pdf` (con hash settings v2). Via libera ai dati reali alle condizioni di CLAUDE.md (parser lanciato solo da Aurelio, a Claude solo diagnostica senza valori).

---
# AGGIUNTA — 2026-10-04 13:4x — Orchestratore — HG-2 approvato dal Boss ("sì, A")
Il Boss ha esteso all'orchestratore (chat) il lancio del parser su dati reali, alle condizioni: stdout scartato, lettura SOLO del rapporto in `diagnostica/` (senza valori); mai aprire `_estratti/`, JSON, HTML, CSV con valori. Accesso alla cartella riservata concesso dal Boss tramite richiesta di permesso (sessione). File di prova: `TEST_bilancio_01.pdf`. CLAUDE.md aggiornato (Claude Code non lancia il parser).

---
# AGGIUNTA — 2026-10-04 13:5x — Orchestratore — primo test su bilancio reale (TEST_bilancio_01.pdf)
Letti solo rapporto e CSV senza valori in `diagnostica/`. Esito: COMPLETATO; 3 pagine con testo; 2 esercizi; 36 FATTO, 0 INFERENZA nelle voci, 16 DA VERIFICARE (voci assenti nel documento); 16/16 controlli aritmetici OK o NON ESEGUIBILE (quello su proventi/oneri finanziari, voci assenti); 0 avvisi; 0 voci non mappate. Dry-run Excel: 14 celle da scrivere, 6 non scritte (righe 11, 21, 23: nessun valore nel documento, cella vuota = zero nel foglio). Verifica umana dei valori contro il PDF: ancora da fare (Aurelio, tramite `_estratti/TEST_bilancio_01_revisione.html`).

---
# AGGIUNTA — 2026-10-04 14:3x — Orchestratore — batteria su bilanci reali + prima variante "bilancio di verifica"
Letti solo rapporti senza valori. Copiati in DATI_REALI_LOCALI come TEST_bilancio_02..05 (Eurocasa 2020, 2021; Mercurio provvisorio 2024, 2025).
- 01–03 (bilanci depositati): COMPLETATO, 16/16 controlli quadrano (02, 03). Parser (a) affidabile su questa classe.
- 04–05 (Mercurio, "bilancio di verifica" da gestionale, codici di conto tipo 3.B.7, due colonne esercizio, voci non numerate): inizialmente 0 esercizi riconosciuti, tutto DA VERIFICARE. Aggiunta traduzione dei codici (3.A.1→1), 3.B.7→7), 3.20→20), totali 3.A/3.B/3.C), riconoscimento "Bilancio al gg/mm/aaaa", intestazione "N CONTO ECONOMICO". Ora: 2 esercizi, 21 voci FATTO, righe 10,12,14,15,16,23 lette; totale A quadra.
- Residui: righe 11, 19 (B10, B11) non lette perché su una riga con UN SOLO importo (colonna non attribuibile dal solo testo → serve la posizione x delle parole); RAI/AB/C non letti (etichette diverse); controllo totale B e utile = RAI − imposte falliscono per questo. Totali per questo tipo di documento restano DA VERIFICARE.
- Test sintetici: parser 6/6, excel 7/7 (da rieseguire dopo ogni modifica).
Prossimo: lettura per posizione delle righe con un solo importo; etichette RAI/AB.

---
# AGGIUNTA — 2026-10-04 15:0x — Orchestratore — parser (a) esteso al "bilancio di verifica" (Mercurio) — esiti senza valori
Modifiche a `parser_bilancio.py` (nessuna nuova dipendenza): traduzione codici di conto (3.A.1, 3.B.7, 3.20, 3.AB…), date "Bilancio al gg/mm/aaaa", intestazione "N CONTO ECONOMICO", lettura per POSIZIONE delle righe con un solo importo (colonna attribuita dalle coordinate, altra colonna = 0, stato INFERENZA), controlli eseguiti solo se presente la prima componente obbligatoria.
Esiti sui 5 bilanci reali di prova (36/44/38/24/22 voci FATTO; controlli OK 14/16/14/8/7): i 3 bilanci depositati restano 0 KO; i 2 provvisori di Mercurio leggono ricavi, altri ricavi, materie, servizi, personale, B14, imposte, utile; B10 assente nel documento (non contabilizzato); restano KO su "RAI" e "A−B" perché la gestione finanziaria (C) non è letta → i totali restano DA VERIFICARE (nessuna scrittura errata). 
Test sintetici: parser 6/6; excel 7/7.
Da fare: lettura della gestione finanziaria (C15–C17) nei bilanci di verifica; poi parser (b) vero e proprio su situazioni contabili senza codici art. 2425.

---
# AGGIUNTA — 2026-10-04 14:2x — HG-3 APPROVATO dal Boss: "ok, due modelli" (cambio architettura)
- Modello AZIENDE (nuovo): `modelli/Modello_Aziende_Valutazione_Crisi_Template.xlsx` (xlsx, nessuna macro/protezione; fogli: dashboard, anagrafica_azienda, bilancio_sp, bilancio_ce, indici_bilancio, flussi_cassa, allerta_ccii, passivo_creditori, scenario_riparto, documenti).
- Modello PERSONE/DITTE INDIVIDUALI (esistente): Traietti (xlsm, motore Riparto LC), foglio flussi_cassa_impresa.
- Estrattore unico; per ciascun modello una MAPPA CELLE. Stesse colonne C=Anno-2, D=Anno-1, E=corrente/previsionale. Regole invariate (solo copia, whitelist, dry-run, controlli, DA VERIFICARE solo se approvato).
- Aggiunta richiesta: semaforo di fattibilità con regole fisse e soglie da fissare con il Boss (valutazione prospettica, supporto alla decisione, non attestazione). Interfaccia web interna su Mac mini via Tailscale: dopo la stabilizzazione del motore.
- Non serve più la copia vuota del motore Traietti per le aziende.

## 2026-10-04 — Modello Aziende (orchestratore, chat)
- test_parser 6/6 e test_excel 7/7 OK (test aggiornati: voci sp.* di dettaglio ammesse come residui/extra).
- Dry-run + scrittura su copia del template Aziende con bilancio sintetico: OK, 5 controlli copia valida, originale intatto.
- Dry-run su TEST_bilancio_01..05 (solo conteggi, nessun valore): celle da scrivere 38/44/42/18/20 su 56; non scritte 18/12/14/38/36.
- Aperto: 04 e 05 (bilanci di verifica Mercurio) -> SP non rilevato ("N ATTIVO N N") e gestione finanziaria C15-C17 non letta.

## 2026-10-04 — Nuovi documenti consegnati (orchestratore)
- Salvati in Riservato_AnalisiCrisi/DATI_REALI_LOCALI/NUOVI_CASI/{Eurocasa, Campioni_generici}. Le 3 copie Banca d'Italia di Eurocasa sono identiche (stesso hash).
- Parser dichiarazioni (c) corretto su UNICO 2025 reale (PF forfettario LM): importi con centesimi staccati, etichette Impresa/Autonomo davanti al rigo. Esito: 5 voci FATTO, 2 controlli aritmetici OK. test_parser 6/6.
- Documenti scansionati (non leggibili senza OCR): 10 pignoramenti Eurocasa, ACQ_RES, 2 estratti di ruolo campione. OCR non previsto da SPECIFICA regola 11 -> serve decisione HG-3 (nuova dipendenza).
- Testo nativo: bilancio provvisorio (parser b), CR visura, CAI, CRIF, CTC, visura camerale, estratti di ruolo Riscossione (428 pag.).

## 2026-10-04 — OCR (HG-3 approvato opzione A) e parser estratti di ruolo
- Nessuna dipendenza Python nuova: usa tesseract/pdftoppm già installati + ita.traineddata scaricato in ~/tessdata (VM). Modulo analisi_crisi/ocr.py (raddrizza le pagine ruotate). Sul Mac va installato tesseract + lingua italiana se si lancia lì.
- analisi_crisi/parser_ruoli.py (testo nativo "Estratto Ruolo Semplificato", Riscossione): Eurocasa = 77 documenti (53 cartelle + 24 avvisi di addebito), 13 gruppi; controlli aritmetici tutti OK (componenti=totale documento 77/77, residuo righe=totale tributi 76/76 + 1 non eseguibile, somma documenti=totale debito 13/13).
- analisi_crisi/ocr_ruoli.py (scansioni): campioni A (3 documenti) e B (10 documenti) riconosciuti, tutto DA VERIFICARE.
- estrai_ruoli.py: JSON in _estratti, diagnostica senza valori in diagnostica/ruoli_*.md.
- Aperto: mappatura nel modello Aziende (scaduto tributario/previdenziale, per classe), CRIF/CTC/CAI/visura camerale, bilancio provvisorio (parser b), pignoramenti Eurocasa (OCR), semaforo, Word.

## 2026-10-04 — Estratti di ruolo collegati al modello Aziende
- excel_scrittura: nuovi fogli passivo_creditori (righe 17-41, col B-F) e allerta_ccii (C22); scrittura di testi (inlineStr); NUOVA regola: non si sovrascrive una cella che contiene già un dato (RIFIUTATA: già un dato).
- modello_aziende.celle_ruoli: una riga per ente creditore (classe "Privilegio generale - tributi e contributi" = INFERENZA, da rivedere per sanzioni/interessi), riga oneri di riscossione (classe DA VERIFICARE), rapporto scaduto/attivo in C22.
- assembla_caso.py unisce più estrazioni in un file; estrai_ruoli.py --bilancio per l'attivo. diagnostica.verifica_senza_valori esteso (ruoli, modello_aziende).
- Test: test_ruoli 4/4, test_parser 6/6, test_excel 7/7.
- Eurocasa: caso in NUOVI_CASI/Eurocasa/CASO (bilancio 2022/2021 + 77 documenti di ruolo): 114 celle scritte, 19 non scritte, copia valida, originale intatto.
- 2026-10-04 visura camerale: parser_visura + estrai_visura.py + celle_anagrafica; Eurocasa: visura segnala variazione denominazione (S.r.l. in liquidazione -> S.n.c.), da verificare. CAI = Centrale d'Allarme Interbancaria (assegni), non Centrale Rischi: 'Soggetto non presente in archivio'. CRIF e CTC negative.

## 2026-10-04 — Visura camerale e situazione contabile
- parser_visura.py + estrai_visura.py + modello_aziende.celle_anagrafica (foglio anagrafica_azienda C6,7,9,10,11,13,16,24). Eurocasa: 9 campi, 8 celle; AVVISO: il Registro riporta variazione di denominazione (S.r.l. in liquidazione -> S.n.c.) e liquidazione dal 2021: verificare forma giuridica in vigore.
- parser_situazione.py + estrai_situazione.py + modello_aziende.celle_situazione (bilancio provvisorio a due colonne, conti MM/GG/CCC). Campione generico: 29 mastri, 5 controlli aritmetici OK, 25 celle INFERENZA. Mappa dei mastri = piano dei conti dello studio del campione: da confermare per altri gestionali.
- Test sintetici: test_visura, test_situazione, test_ruoli 4/4, test_parser 6/6, test_excel 7/7.
- CAI Eurocasa = Centrale d'Allarme Interbancaria (assegni/carte): "soggetto non presente in archivio"; NON è la Centrale Rischi. CRIF e CTC: nessuna segnalazione.
- Aperto: parser Centrale Rischi (campione generico), pignoramenti OCR, semaforo di fattibilità, riepilogo Word, correzioni template, test su dichiarazione impresa (ordinaria), Eurocasa: scegliere quale bilancio/colonne.
- Decisioni di Aurelio (2026-10-04): Eurocasa trasformata da S.r.l. a S.n.c. per erosione del capitale (denominazione e forma giuridica confermate = FATTO); Centrale Rischi mai pervenuta (passivo bancario da acquisire); classe dei ruoli lasciata "privilegio generale tributi e contributi" finché non si distinguono tributo, sanzioni e interessi.

## 2026-10-04 — Semaforo di fattibilità e relazione Word
- analisi_crisi/semaforo.py (regole fisse e soglie dichiarate in SOGLIE; verdetto ROSSO se un criterio critico è rosso o due criteri rossi), word_xml.py (docx dal modello CNC senza librerie), relazione_caso.py. Soglie scelte dall'orchestratore ("procedi"): EBITDA>=8% verde, ricavi -5%/-20%, scaduto/attivo 5%/20%, copertura continuità 60%/30%, 50% EBITDA per 5 anni, realizzo liquidità 100% crediti 50% rimanenze 40% immobilizzazioni materiali 30%, costi procedura 15%. Da approvare/correggere da Aurelio (HG-2).
- Test: test_relazione 2/2; totale suite: parser 6, excel 7, ruoli 4, situazione 1, visura 1, relazione 2.
- Eurocasa: Relazione_Eurocasa_preanalisi.docx in NUOVI_CASI/Eurocasa/CASO (cartella riservata). Semaforo finale ROSSO, tutti i 7 criteri rossi (letti solo i colori, non i valori).

## Relazione v2 (richiesta avvocato 16:01) - orchestratore
- relazione_caso.py riscritto: schede per ogni semaforo (valore assoluto, %, formula, natura STORICO/AGGIORNATO/STIMA e data, documento e pagina, soglia, motivazione); quadro iniziale con i numeri che sostengono ciascun giudizio.
- Dato mancante = "non disponibile" (mai zero, nessun giudizio negativo automatico). Rimossi i default `or 0`.
- Opzione --anonimizza: codici coerenti per denominazione, nominativi, CF, REA, PEC, sede, nomi file; importi invariati; legenda separata nella cartella riservata; controllo anti-residui.
- Test: 23 OK (6+7+4+1+1+4). Generati Relazione_Eurocasa_preanalisi_v2.docx e Relazione_Eurocasa_ANONIMIZZATA.docx (+ legenda). Valori reali NON letti dall'orchestratore.
- Da approvare (HG-2): formato schede e soglie.

## 2026-10-04 16:3x - Caso Mercurio in automatico (orchestratore)
- INCIDENTE di governance (Art. 12): in una verifica della struttura di TEST_bilancio_05 ho stampato a video alcuni totali reali (il mascheramento copriva solo importi con centesimi). Causa: regex incompleta. Impatto: valori visti dall'orchestratore, non scritti in alcun file. Correttivo: nelle ispezioni si maschera ogni cifra tranne il codice conto. Verifica: nessuna stampa successiva con importi.
- parser_bilancio.py (bilancio di verifica): segno negativo in coda ("1.998-"), codici SP 1.x/2.x tradotti in voci standard (stato INFERENZA), intestazione "1 ATTIVO <importi>" letta anche come totale. Esiti 04 e 05: attivo = passivo OK, tutti i controlli OK o non eseguibili (C15-C17 senza proventi), 0 KO. Resta DA VERIFICARE ce.U21.
- Caso Mercurio creato in NUOVI_CASI/Mercurio (bilancio provvisorio 2025, con 2024 come anno precedente). Excel Aziende: copia compilata valida; 22 celle non scritte per assenza di valore.
- relazione_caso.py: ruoli e visura opzionali (assenti = "non disponibile"), dicitura "bilancio di verifica provvisorio (non depositato)", Centrale Rischi "non acquisita".
- Relazione Mercurio (riservata + anonimizzata + legenda): semaforo ROSSO, guidato dal criterio capacità (critico); scaduto e best-interest non disponibili. Valori non letti.
- Test: parser 6, excel 7, ruoli 4, visura 1, situazione 1, relazione 5: tutti OK.

## 2026-10-04 16:5x - Interfaccia A (locale) e B (artifact) - HG-3 approvato dal Boss ("creali entrambi")
- A: interfaccia_locale.py (solo libreria standard, nessuna dipendenza nuova). Casi = cartelle in una radice; upload PDF (mai sovrascrive), estrazione con gli script esistenti, rapporto senza valori a video, relazione riservata e anonimizzata. Su rete richiede PIN (rifiuta l'avvio senza). Percorsi bloccati dentro la cartella del caso. Avvio: Avvia_Interfaccia.command.
- Test sintetici test_interfaccia.py: 2 OK (flusso completo, percorsi fuori cartella rifiutati, PIN). Non lanciata su dati reali.
- B: pagina artifact con inserimento manuale e calcolo nel browser; solo dati di prova.
- B pubblicata come artifact privato (Preanalisi Crisi): calcolo verificato a mano contro il motore Python su un esempio; nessun dato salvato né inviato.

## 2026-10-04 (sera) - Revisione sostanziale delle relazioni: motore v3
- Nuovo `relazione_v3.py` (corpo 4-5 pagine + appendici A-D, A4, tabelle non spezzate, controllo segnaposto) e estensioni di `analisi_crisi/word_xml.py` (compatibili con la v2).
- Costruttori per caso (cartella riservata): `NUOVI_CASI/<caso>/CASO/costruisci_caso_v3.py` -> `caso_v3.json`; rigenerazione con `00_ORCHESTRAZIONE/rigenera_v3.sh <caso>`.
- Rimossi: classificazione automatica della natura della crisi; massa passiva = max(bilancio, ruoli); "non percorribile" da formula 50% x 5 anni; coefficienti di realizzo senza perizia.
- Aggiunti: normalizzazione per rettifica con margine progressivo; riconciliazione per creditore (debito PROVVISORIO); due giudizi (sostenibilita', fattibilita'); scenari omogenei; parametri interni di screening.
- Errori della v2 corretti: 5% di incidenza dei debiti pubblici presentato come soglia CCII; CAI/CRIF/CTC e ruoli del 2020 senza data; ruoli 2020 sommati a dati 2021-2022.
- `semaforo.py` NON modificato (la v3 non lo usa per il verdetto): riforma da approvare (HG-3).
- Test: `test_sintetici/test_relazione_v3.py` (DEMO). DEMO in `DEMO/` (caso fittizio, tabella dati ideali, relazione DEMO).
- Tabella di controllo: `00_ORCHESTRAZIONE/Tabella_controllo_revisione_v3.docx/.pdf` (pagine lette dai PDF).
- Residui: registro dei caricamenti (data di acquisizione), testo vigente degli articoli, soglie di settore CNDCEC, perizia/ruoli/CR Eurocasa, file temporanei di LibreOffice (.~lock, lu*.tmp) e `_render_sintetico` da cancellare a mano.

## 2026-10-04 (sera) - Revisione v3.1 (7 correzioni dell'avvocato; HG-2 e DEMO NON ancora approvate)
- Letto il decreto dirigenziale 23/04/2026 (B.U. Min. Giustizia n. 10 del 31/05/2026; fonte pubblica ilcaso.it, non il Bollettino): test pratico A/B prognostico, fasce 1/3/5, lista di controllo, sezione II-bis. Entrata in vigore da verificare.
- relazione_v3.py: `rapporto_semplificato` (alias `rapporto_test_pratico` conservato), `scheda_test_ministeriale` (NON ESEGUITO), `scheda_test_ministeriale_calcolato` (DEMO), sezione 1 con tre giudizi + stato DEFINITIVA/NON DEFINITIVA, sezione opzionale 7-bis tesoreria, norme in sintesi nel corpo e testo completo in App. E. word_xml.py: tabelle >7 righe interrompibili tra le righe.
- Nuovo analisi_crisi/semaforo_v3.py (sostenibilità, qualità dei dati, fattibilità); semaforo.py v2 invariato. Test: test_semaforo_v3.py, test_relazione_v3.py aggiornato (tutti i test passano).
- Costruttori Eurocasa/Mercurio/DEMO aggiornati (copie PRE_REV4 conservate); output nuovi con suffisso v3.1 (le v3 restano). Script: rigenera_v3_1.sh, rigenera_demo.sh, costruisci_tabella_controllo_v3_1.py.
- Verifica indipendente (agente separato, ricalcolo dalle fonti): 34 confermati, 7 discrepanze corrette (rimandi pagina, A7/A9, quota 551, S3 DEMO non omogeneo, data DEMO, fondi ammortamento Mercurio 2024: valore lordo -19.315,52 senza B10), 3 non verificabili.
- Esiti: Mercurio sostenibilità GIALLO(v3) -> ROSSO(v3.1, flusso più prudente), fattibilità CONDIZIONATA provvisoria; Eurocasa ROSSO / NON CONCLUDENTE; entrambe NON DEFINITIVE. DEMO: ROSSO / ALTA / CONDIZIONATA definitiva.
- Aperti: HG-2 sui parametri, HG-3 su integrazione del semaforo v3 nell'interfaccia, registro caricamenti, libro cespiti, tesoreria, ruoli Mercurio, perizia Eurocasa.

## 2026-10-04 (notte) - Congelamento "Preanalisi Crisi v1.0-pilota" (metodo approvato da Aurelio; giudizi Eurocasa/Mercurio NON validati)
- Mercurio: ROSSO = allerta finanziaria prudenziale sui dati storici; sostenibilità corrente NON VERIFICATA. Soglie su valori non arrotondati, valori prossimi (±5%) segnalati. DEMO: "valutazione completa sul dataset simulato". Regole tecniche della tabella di raccolta in note separate.
- HG-3 autorizzato: semaforo_v3 nell'interfaccia (4 riquadri), modulo pratica con gate, verbale a hash a catena, versione/parametri. Backup in versioni/ (pre_HG3, v3.1). Ripristino: config_motore.json -> v2.
- Congelato in versioni/v1.0-pilota (MANIFEST con sha256). Regole: solo errori sostanziali nelle prime tre pratiche; il resto in BACKLOG_MIGLIORAMENTI.md.

## 2026-10-04 (notte) - Rev.2 "raccolta documentale non bloccante" (richiesta esplicita di Aurelio)
- Gate ristretto al solo consolidamento; preanalisi provvisoria sempre avviabile (anche ricognizione del fascicolo con registro vuoto), max 5 richieste, scenari sospesi puntualmente, due indicatori (sufficienza per iniziare / per concludere), approvazione "come provvisoria" con nome nel verbale.
- Nuovo modulo checklist.py (gruppi A/B, stati ricevuto/mancante/da aggiornare/illeggibile/non pertinente). Congelato in versioni/v1.0-pilota-rev2_raccolta; versioni precedenti conservate.

## rev.3 (04/10/2026) - consegna Mac
- Correzioni PDF/preanalisi (6 punti), stato 'inesistente', Installa_Mac.command, GUIDA_MAC.md, DEMO_PDF, requirements.txt. Nessuna regola analitica nuova; SOGLIE_V3 invariate.
- Manifest: versioni/v1.0-pilota-rev3_interfaccia/MANIFEST.json (include l'ultima interfaccia).
- Prova E2E da browser su cloud (Python 3.13, dati sintetici); NON eseguita su macOS.
