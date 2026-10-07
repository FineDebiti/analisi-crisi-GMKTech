# ANALISI CRISI - copia GMKtec con modello locale (Qwen) - guida per Giuseppe

Stato: **pacchetto preparato e provato su Linux (Ubuntu 24.04, ambiente cloud) con un finto modello. NON ancora provato sul GMKtec, né con Qwen reale.** La replica è "pronta" solo dopo i passi 1-5 qui sotto, eseguiti sul GMKtec.
Il motore (calcoli, soglie, giudizi, PDF) è identico al Mac: impronta `a09b02b7…`, rev.3, parametri invariati. Tutto resta locale: l'app rifiuta endpoint del modello che non siano 127.0.0.1/localhost.

## 0. Principio
Il modello **propone** (dati con documento/pagina/periodo/citazione, mancanti, incongruenze, normalizzazioni, scenari, richieste). Il **codice verifica** (citazione alla lettera nella pagina, numero coincidente) e **calcola**. I valori presi dal modello restano "DA VERIFICARE" finché il titolare non li conferma. Il modello non tocca soglie né protocollo.

## 1. Verifica l'ambiente (non installa nulla)
- Linux o WSL: `bash verifica_ambiente.sh` - Windows nativo: `powershell -ExecutionPolicy Bypass -File verifica_ambiente.ps1`
- Manda `report_ambiente.txt`. Serve per fissare: sistema operativo, Python, GPU/RAM, software di esecuzione (llama.cpp / Ollama / LM Studio), **id esatto del modello, quantizzazione e contesto**.
- Sul nome "Qwen 3.8 27B": dal mio lato non posso confermare che esista un modello con questo nome. Fa fede quello che riporta il runtime (`/v1/models`, `ollama show`, nome del file .gguf). Se è diverso (versione, 27B/32B, instruct/base, quantizzazione) scrivilo così com'è nelle schede. **Non installare né sostituire modelli** senza prima chiarire con Aurelio.

## 2. Installazione (una volta, internet necessario per le dipendenze)
- **Consigliato: Linux/WSL** - `bash Installa_Linux.sh`. Crea `.venv` locale (mai copiata da altre macchine), installa reportlab/pdfplumber/pillow, esegue 4 prove su dati sintetici (incluso il livello modello con un finto server). Deve finire con *INSTALLAZIONE COMPLETATA*.
- **Windows nativo (non provato)**: doppio clic su `Installa_Windows.bat`. Se fallisce, usa WSL.
- OCR locale per PDF scansionati (facoltativo): `sudo apt install tesseract-ocr tesseract-ocr-ita poppler-utils`; in Windows tesseract e pdftoppm nel PATH. Nessun OCR remoto. I valori da OCR sono sempre DA VERIFICARE e mantengono la pagina.
- Python 3.10 o superiore.

## 3. Configura il modello locale (solo dopo il passo 1)
1. Avvia il tuo runtime come già fai (es. `llama-server -m <file>.gguf -c <contesto> --port 8080`; Ollama `http://127.0.0.1:11434/v1`; LM Studio `http://127.0.0.1:1234/v1`).
2. Copia `llm_config.esempio.json` in `llm_config.json` e compila: `endpoint` (solo loopback), `modello` (id esatto dal runtime), `etichetta_modello` (come lo chiama Aurelio), `quantizzazione`, `contesto_configurato`. Lascia `temperatura` 0 e `seed` 7: valgono per tutte le prove.
3. Con `abilitato: false` (o senza file) l'app funziona senza modello, come sul Mac.
4. Dipendenze esterne: nessuna oltre al runtime locale che già usi. Segnala se il tuo runtime chiama servizi esterni (telemetria, scarico modelli): documenti e prompt non devono uscire dalla macchina.

## 4. Avvio e arresto
- Avvio: `bash Avvia_Linux.sh` (Windows: `Avvia_Windows.bat`) -> http://127.0.0.1:8765. Arresto: `bash Arresta_Linux.sh` o Ctrl+C.
- Accesso da altri PC: solo via rete privata/Tailscale, `bash Avvia_Linux.sh rete <IP>` con PIN. **Non verificato.** Non esistono permessi staff/titolare: un solo livello di accesso.

## 5. Prova DEMO dalla schermata (da fare sul GMKtec)
1. Home: crea la pratica `DEMO`. 2. Registro: carica i 3 PDF della cartella `DEMO_PDF`; segna B4 e B9 "inesistente". 3. Dati: controlla i 9 valori letti dal parser (origine "Estratto automaticamente"); inserisci a mano liquidità utilizzabile 20.000, debiti pubblici 110.000, debiti bancari 215.000, tesoreria "No". 4. Scheda **Modello locale**: "Estrai con il modello locale" -> controlla la tabella (RISCONTRATO / NON RISCONTRATO / DUPLICATO / CONFLITTO, confronto col parser) e applica solo ciò che accetti: nasce "Proposto dal modello locale (da verificare)". 5. Correggi un valore (storico). 6. Preanalisi -> Approva come provvisoria -> scarica PDF. 7. Cambia un dato: l'approvazione decade. 8. Arresta, riavvia: tutto presente.
Risultati attesi: `DEMO_RISULTATI_ATTESI.md`. Annota ogni scostamento (copia lo schermo).

## 6. Esperimento A/B
Vedi `ab/README_AB.md`. In breve: `ab/prepara_demo.py` crea la DEMO di riferimento; `ab/esegui_ab.py bundle` costruisce lo stesso fascicolo per Claude e Qwen (prova A su dati verificati, prova B dai PDF); `qwen` esegue il modello locale; Claude esegue lo stesso bundle in una conversazione nuova; `valuta` misura; `scheda` produce la scheda **cieca A/B** per il titolare. La prima risposta di ciascun sistema non si riscrive.

## 7. Che cosa riportare ad Aurelio
`report_ambiente.txt`; esito delle 4 prove di installazione; esito della DEMO (passi 1-8) con eventuali scostamenti; tempi del modello sulla DEMO; la cartella del bundle DEMO (senza il file CHIAVE).
