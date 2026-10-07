# Regole di sperimentazione - Preanalisi Crisi v1.0-pilota
- Il modello è congelato. Durante le prime tre pratiche si correggono solo gli ERRORI SOSTANZIALI (numeri sbagliati, regola che produce un giudizio errato, dato riservato esposto, violazione di governance). Ogni correzione: nota nel verbale, nuova impronta, copia della versione precedente.
- Ogni altro miglioramento (testo, impaginazione, nuove schede, nuovi indicatori) va in `BACKLOG_MIGLIORAMENTI.md` senza riaprire il modello; si valuta dopo la terza pratica.
- Per ogni pratica: registro documentale -> dati estratti con fonti -> incongruenze -> richieste prioritarie -> VERIFICA DELL'AVVOCATO sui numeri decisivi -> solo dopo la valutazione. Nessuna conclusione prima del gate.
- Ogni valutazione conserva versione del motore, impronta dei parametri e verbale dei controlli (hash a catena).
- Ripristino: `config_motore.json` {"semaforo": "v2"} oppure copia da `versioni/`.
