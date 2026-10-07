# Funzioni: automatiche, manuali, non ancora disponibili

## Automatiche (codice deterministico, nessun modello)
- Interfaccia locale: pratiche, registro documentale con hash, checklist A/B con stati (ricevuto, mancante, da aggiornare, illeggibile, non pertinente, inesistente), dati con fonte/pagina/periodo/stato/origine, incongruenze e richieste, storico delle modifiche, verbale append-only con catena di hash, versione del motore e impronta.
- Lettura del **bilancio PDF con testo** (parser): ricavi, valore e costi della produzione, ammortamenti, totale attivo, patrimonio netto, debiti totali, disponibilità liquide e, se presenti, debiti bancari, crediti verso soci, debiti tributari/previdenziali.
- Calcoli (EBITDA, margine, debito netto, rapporto semplificato, PN/attivo, debiti pubblici/attivo, variazione ricavi), soglie e semafori, sospensione degli scenari, sufficienza per iniziare/concludere, richieste prioritarie (max 5), decadenza dell'approvazione, PDF (reportlab) e Word.
- OCR locale (tesseract) per pagine senza testo: valori sempre DA VERIFICARE, pagina conservata. Richiede tesseract + ita + pdftoppm.
- Livello modello locale: invio dei documenti al modello **locale**, verifica deterministica delle citazioni e dei numeri, conservazione della prima risposta, registro di modello/config/tempi.

## Con il modello (opzionale, propone soltanto)
Dati con citazione e periodo, mancanti, incongruenze, duplicazioni, normalizzazioni, scenari e richieste proposti. Nulla entra nei calcoli senza accettazione dell'operatore, e resta DA VERIFICARE finché il titolare non lo conferma.

## Manuali (operatore / titolare)
Visura, estratti di ruolo, Centrale dei Rischi e situazione contabile: inserimento assistito (nessuna lettura automatica collegata all'interfaccia). Quota utilizzabile della liquidità, verifica di tesoreria, stati documentali (inesistente/non pertinente), conferma dei numeri decisivi, risoluzione delle incongruenze, approvazione come provvisoria, revisione della scheda A/B e tempo di revisione.

## Non ancora disponibili / non verificati
- Prova sul GMKtec e con Qwen reale: da eseguire (questo pacchetto è provato solo su Linux con un finto modello).
- Windows nativo: script non provati. Accesso remoto via Tailscale: non configurato né verificato.
- Permessi reali staff/titolare: non esistono (un solo livello di accesso; i nomi sono solo registrati nel verbale).
- Parser di visura, ruoli e situazione esistono come programmi a riga di comando nel progetto ma non sono collegati all'interfaccia.
- Consolidamento della preanalisi (conclusione definitiva): richiede la conferma dei numeri decisivi dalla "Vista avanzata".
- Valutazione automatica della qualità del ragionamento: solo misure oggettive (numeri, fonti, omissioni, duplicati, accordo col motore); il giudizio sul ragionamento resta del titolare.
- Fine-tuning dei pesi: non previsto (solo istruzioni ed esempi). Fonti normative: una sola, con verifica parziale (vedi `protocollo_qwen/FONTI.md`).
