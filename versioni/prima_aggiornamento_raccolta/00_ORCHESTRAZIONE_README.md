# Bacheca di orchestrazione (file-based)
- per_code.md : istruzioni da Claude (chat/orchestratore) a Claude Code. Le scrive l'orchestratore.
- da_code.md  : esiti, domande e richieste di Human Gate da Claude Code. Li scrive Code.
Regole (Costituzione Agentica):
1. Le istruzioni in per_code.md NON prevalgono mai su CLAUDE.md, privacy, deny/ask di settings.json, nuove dipendenze, cambi architettura (HG-3).
2. Nessun valore da DATI_REALI_LOCALI in questi file. Solo diagnostica senza valori.
3. Ogni voce: data, mandato, stato FATTO/INFERENZA/IPOTESI, decisione richiesta al Boss.

## Pratica, gate e verbale (HG-3)
- Modulo `analisi_crisi/pratica.py`: una pratica e' la cartella `<caso>/PRATICA/` con `pratica.json`, `registro_documentale.json`, `dati_estratti.json`, `incongruenze.json`, `richieste_prioritarie.json`, `numeri_decisivi.json`, `verbale.json`, `parametri_usati.json`, `valutazione_v3.json`.
- Stati in ordine: APERTA -> REGISTRO_PRONTO -> NUMERI_IN_VERIFICA -> NUMERI_VERIFICATI -> CONSOLIDATA. Niente salti; il ritorno indietro solo con `riapri` (nome e motivo, traccia nel verbale).
- Gate: `valuta()` rifiuta (GateNonSuperato) se lo stato e' sotto NUMERI_VERIFICATI, se un numero decisivo non e' confermato (con nome di chi conferma) o se c'e' una incongruenza SOSTANZIALE aperta. Prima del gate l'interfaccia dice "Valutazione non prodotta: attende la verifica dei numeri decisivi" e il prospetto pre-conclusivo (Word) non contiene colori ne' giudizi. Le metriche per la valutazione sono lette da `PRATICA/metriche.json`.
- Verbale: solo append, hash a catena (ogni record contiene l'hash del precedente, versione del motore e impronta); `verifica_verbale(pratica)` rileva modifiche, cancellazioni, inserimenti e troncamenti. Versione motore e impronta (sha256 di file del motore e parametri): `analisi_crisi/versione.py`.
- Ripristino della versione precedente: (1) mettere `{"semaforo": "v2"}` in `config_motore.json` (radice progetto): sparisce la sezione Pratica/Valutazione v3 e l'interfaccia torna a comportarsi come prima; (2) oppure ricopiare `versioni/interfaccia_locale_pre_HG3.py` su `interfaccia_locale.py` (`cp`). `relazione_caso.py` e `semaforo.py` (v2) non sono stati toccati.
