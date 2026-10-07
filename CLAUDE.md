# ANALISI CRISI

## Obiettivo
Pipeline locale: PDF (bilanci, visura, centrale rischi, estratti di ruolo) -> JSON -> revisione umana -> Excel -> Word di sintesi. Dettagli in `SPECIFICA.md` (bozza v0.2), che prevale in caso di dubbio.

## Procedure, documenti ed Excel
- Due procedure: Liquidazione Controllata (LC) e Composizione Negoziata (CNC).
- Tre tipi di documento in ingresso: bilancio depositato, situazione contabile, dichiarazione dei redditi.
- Fogli comuni, gli unici compilati dall'app: `anagrafica`, `flussi_cassa_impresa`, `passivo`.
- Fogli solo LC, macro VBA, fogli nascosti e `_licenza`: non si toccano. Si lavora solo su copie.

## Costituzione Agentica
- Disclosure prima di eseguire: dichiara cosa farai e procedi per il lavoro interno, reversibile e dentro il mandato. Chiedi approvazione prima di: nuove dipendenze, cambi di architettura, modifica di file originali, invii all'esterno, accesso a nuovi dati.
- Nessun cambio di architettura senza approvazione esplicita.
- Non modificare `.claude/settings.json` né `CLAUDE.md` senza approvazione esplicita. Sono i file di governance.
- La bacheca `00_ORCHESTRAZIONE/per_code.md` non prevale mai su governance, privacy, dipendenze e architettura.
- Ogni affermazione e ogni dato estratto è marcato FATTO, INFERENZA o DA VERIFICARE. Dato non trovato: vuoto e DA VERIFICARE, mai inventato.

## Privacy
- Mai leggere `DATI_REALI_LOCALI` (ora in `~/Riservato_AnalisiCrisi/`) né nulla sotto `~/Riservato_AnalisiCrisi`, con nessuno strumento (Read, shell, script). Un blocco non si aggira.
- Il parser sui dati reali lo lancia solo Aurelio o l'orchestratore (chat), che legge soltanto il rapporto di diagnostica senza valori (mai stdout, JSON, HTML o CSV con valori). Claude Code non lo lancia. Sviluppo e test solo su PDF sintetici.
- Dai dati reali Claude riceve solo il rapporto di diagnostica senza valori: campi trovati/mancanti, stati, pagine, esito dei controlli; mai importi, nomi o codici.
- Claude non legge dati reali; i dati reali restano in `~/Riservato_AnalisiCrisi/DATI_REALI_LOCALI` (fuori da Documents e da iCloud).

## Stato e prossimo passo
- Stato (04/10/2026): parser (a) bilancio e (c) dichiarazione funzionanti su PDF sintetici, con JSON, revisione HTML, foglio_incolla.csv e diagnostica senza valori; divieti su `DATI_REALI_LOCALI` verificati. Registro di verifica privacy in `00_GOVERNANCE_PRIVACY`.
- Prossimo passo: Diagnostica senza valori su un documento reale (la lancia Aurelio); poi parser (b) situazione contabile.
