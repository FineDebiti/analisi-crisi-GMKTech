# Esperimento A/B - procedura

Regole: stesso fascicolo, stesse istruzioni, stessi criteri; **nessun sistema vede l'output dell'altro**; la **prima risposta** si conserva senza correzioni (il programma rifiuta di sovrascriverla); si registra tutto: modello e configurazione, versione del motore e parametri (nel bundle), tempi, errori.

## Preparazione (DEMO)
```
python3 ab/prepara_demo.py --radice ~/PROVA_AB/CASI          # crea la DEMO con le funzioni dell'app (nessuna modifica manuale ai JSON)
python3 ab/esegui_ab.py bundle --prova B --cartella ~/PROVA_AB/CASI/DEMO --out ~/PROVA_AB/bundle/prova_B
python3 ab/esegui_ab.py bundle --prova A --cartella ~/PROVA_AB/CASI/DEMO --out ~/PROVA_AB/bundle/prova_A
```
- **Prova A - analisi**: stessi dati verificati dal titolare (stato FATTO), calcoli del codice, stato dei documenti, protocollo e fonti. Il modello non estrae: ragiona (normalizzazioni, incongruenze, scenari, richieste).
- **Prova B - percorso completo**: stessi PDF originali; errori di **lettura** (dati/fonti/periodi/zeri) e di **ragionamento** (incongruenze, scenari, richieste) sono contati separatamente.

## Esecuzione
- Qwen: `python3 ab/esegui_ab.py qwen --bundle <cartella bundle>` (legge `llm_config.json`; salva modello riportato dal runtime, config, secondi, token).
- Claude: `python3 ab/esegui_ab.py claude --bundle <cartella bundle>` mostra come procedere: **solo** `sistema.txt` + `utente.txt`, conversazione nuova, nessuno strumento, nessun accesso all'output di Qwen. Poi `registra --arm claude --risposta file --secondi N --modello "id esatto" --configurazione "..."`.
- Ripeti A e B per entrambi i sistemi. Il tempo di revisione umana si annota nella scheda.

## Valutazione e scheda
```
python3 ab/esegui_ab.py valuta --bundle <bundle> --verita ab/DEMO_verita.json        # misure deterministiche
python3 ab/esegui_ab.py scheda --bundle <bundle>                                      # scheda A/B CIECA
```
Al titolare consegnare **solo** `SCHEDA_CONFRONTO_AB.md` e la cartella `cieca/`. La chiave (quale sistema è A o B) è in `CHIAVE_AB_non_aprire_prima_della_revisione.json`. Il titolare valuta ragionamento ed evidenze (rubrica 0-3 nella scheda), non il solo semaforo.

## Per la pratica reale
Stesso flusso con la cartella della pratica reale e una **verità costruita dal titolare** (valori, pagine, mancanti, incongruenze note) al posto di `DEMO_verita.json`. Le misure automatiche non sostituiscono il giudizio del titolare.

## Limiti dichiarati
- La cecità A/B è parziale: lo stile delle risposte può rivelare il sistema.
- La DEMO ha un'unica incongruenza (non intenzionale) nel roll-forward del patrimonio netto: poche osservazioni, non basta per conclusioni statistiche.
- "Scenari concordanti col motore" misura l'accordo col motore, non la verità sul caso.
