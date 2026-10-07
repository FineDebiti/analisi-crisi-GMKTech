# Applicativo ANALISI CRISI — specifica (bozza v0.2, 03/10/2026)

Sostituisce la v0.1. Le modifiche derivano dalle decisioni di Aurelio del 03/10/2026.

## Obiettivo
Input: bilanci e documenti contabili equivalenti, visura camerale, centrale rischi Banca d'Italia, estratti di ruolo (PDF).
Pipeline: PDF -> estrazione dati (JSON) -> revisione umana -> Excel -> Word di sintesi.

## I due file di destinazione
**Excel `Traietti Alessandro.xlsm`** — motore "Riparto" per Liquidazione Controllata, 15 fogli:
dashboard, anagrafica, documenti, nucleo_familiare, flussi_cassa_impresa, inventario, passivo, riparto_lc_d1/d2, piano_d1/d2, compensi, genera_report, impostazioni (nascosto), _licenza (nascosto). Contiene macro VBA e formule collegate tra i fogli. I fogli sono protetti.

**Word `Template_Preanalisi_Economico-Finanziaria_CNC.docx`** — Composizione Negoziata (CNC), 20 sezioni + conclusione, tabelle e campi `[...]`.

## Perimetro (procedure diverse)
- **Dati comuni, compilati dall'app**: solo i fogli `anagrafica`, `flussi_cassa_impresa`, `passivo`.
- **Solo Liquidazione Controllata** (riparto, piano, compensi, inventario, nucleo familiare): l'app non li tocca.
- **Solo CNC** (flusso annuo destinabile, numero di anni, offerta, waterfall, stress test, confronto liquidazione/continuità): non hanno un foglio Excel. Sono input manuali dell'avvocato; le sezioni narrative del Word restano bozze marcate "DA VERIFICARE".
- L'Excel non viene esteso con fogli o logiche CNC senza approvazione esplicita.

## Mappa dati (PDF -> Excel -> Word)
| Fonte PDF | Foglio Excel | Parte del Word |
|---|---|---|
| Bilancio depositato / situazione contabile (2 esercizi) | flussi_cassa_impresa, regime ordinario (col. C = Anno -2, D = Anno -1) | Sez. 3, tabelle 3.1 e 3.2 |
| Dichiarazione dei redditi (quadri RE/RG/LM) | flussi_cassa_impresa, regimi semplificata e forfetario (col. E, un solo anno) | Sez. 3 |
| Visura camerale | anagrafica | Frontespizio, Sez. 2 |
| Estratto di ruolo | passivo | Sez. 5 |
| Centrale rischi | passivo | Sez. 6 |
| Input manuali CNC (nessun foglio Excel) | — | Sez. 1, 4, 9-19 |

## Fase 1 — parser dei documenti contabili
Tre tipi di documento, un solo schema JSON, le stesse celle di destinazione:
- **a) Bilancio depositato** (società di capitali, schema civilistico art. 2425 c.c.).
- **b) Situazione contabile / bilancio di verifica** del commercialista (imprese che non depositano).
- **c) Dichiarazione dei redditi** (quadri RE/RG/LM) per ditte individuali e forfettari.

Ordine di sviluppo confermato: a -> c -> b. Un parser alla volta.

Tecnica: parser a regole in Python con `pdfplumber` (approvato), tutto in locale. OCR locale per le scansioni: da proporre e approvare solo se serve. XBRL: eccezione facoltativa, non progettata ora.

### Regole di estrazione
1. Ogni dato riporta: valore, stato (FATTO / INFERENZA / DA VERIFICARE), fonte (file, tipo di documento, pagina, testo letto), cella di destinazione.
2. Dato non trovato: valore vuoto, stato DA VERIFICARE. Nessun dato inventato.
3. Controlli aritmetici: i totali ricalcolati devono coincidere con quelli del documento; in caso contrario il dato diventa DA VERIFICARE.
4. Voci del conto economico non mappate dall'Excel (B12, B13, sezione D): tenute fuori dalle celle e riportate tra i "residui", mai sommate ad altre voci.
5. Righe 28-30 di `flussi_cassa_impresa` (variazione CCN, capex, rimborso debiti): lasciate vuote, inserimento manuale dell'avvocato.
6. Colonna "Previsionale" (E, regime ordinario): input manuale, l'app non la compila.

7. Riga 32 (oneri finanziari netti di cassa): il parser non la compila mai. Verificato da Aurelio: la riga 33 sottrae oneri già dedotti nell'utile (riga 21), quindi riempirla crea un doppio conteggio. La formula non si tocca.
8. Dichiarazione dei redditi: nel JSON entrambi gli anni; nell'Excel l'ultimo disponibile.
9. Contributi previdenziali (righe 40 e 50): lasciati vuoti e segnalati.
10. Test solo su PDF sintetici. Sui file reali il contenuto non viene mai letto; l'anonimizzazione avverrà con uno script locale lanciato da Aurelio.
11. Scansioni: nessun OCR per ora. Se il parser riceve una scansione si ferma e la segnala; l'OCR locale verrà proposto solo ai primi test sulle scansioni.

### Punti aperti
- Sez. 4 (dato dell'anno corrente) e sez. 15 (costi energetici) del Word non hanno una cella nell'Excel.

## Fasi
- **F1**: parser dei documenti contabili + JSON (nessuna scrittura su Excel).
- **F2**: scrittura in Excel su una COPIA del file. Lettura in sola lettura del foglio nascosto `impostazioni` autorizzata solo da questa fase. La gestione dei fogli protetti richiede una decisione di Aurelio.
- **F3**: generazione Word dal template.
- **F4**: eventuale scraping dei portali, solo con approvazione.

## Vincoli
- Si lavora solo su copie. Macro VBA, fogli nascosti e `_licenza` non si toccano.
- Approvazione preventiva per: cambi di architettura, nuove dipendenze o servizi esterni, invio di dati fuori dal Mac, modifiche all'Excel originale.
- Dati dei clienti solo in locale. Test solo con dati fittizi, mai con il fascicolo Traietti.
