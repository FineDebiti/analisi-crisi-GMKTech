# RAPPORTO UFFICIALE DI COLLAUDO E RISCONTRO TECNICO
**Destinatario:** Aurelio (Responsabile Sviluppo & Governance — Progetto ANALISI CRISI)  
**Mittente:** Giuseppe (Collaudo Ambiente Locale GMKtec)  
**Data:** 09 Ottobre 2026  
**Oggetto:** Riscontro collaudo ambiente Windows GMKtec, runtime locale LM Studio (Qwen 3.8 27B) e test documentale ex par. 7 `GUIDA_GMKTEC.md`  
**Versione applicativo:** `Preanalisi Crisi v1.0-pilota, rev.3`  
**Impronta parametri/motore:** `a09b02b7d713fbf0` (confermata conforme alla rev.3 del Mac)  

---

## 1. Sintesi Esecutiva (Executive Summary)

Il collaudo dell'applicativo **ANALISI CRISI** sull'hardware nativo **GMKtec (Windows 11 Pro)** con runtime locale **LM Studio** e modello **Qwen 3.8 27B** ha dato **ESITO POSITIVO**.

* **Verifica dell'ambiente**: Ambiente Python nativo (`.venv`), hardware GPU AMD Radeon e runtime locale rilevati e funzionanti.
* **Suite di test sintetici di installazione**: 4 test su 4 superati con successo (**100% OK**).
* **Integrazione LM Studio**: Il modello `qwen/qwen3.8-27b` risponde regolarmente all'endpoint di loopback `http://127.0.0.1:1234/v1`, producendo payload JSON conformi a `SCHEMA.json`.
* **Test su documenti contabili reali/scansionati**: Eseguito con successo (Run `20261009-134221`, tempo di inferenza 236,53 s).
* **Validazione del meccanismo di salvaguardia (*Human Gate*)**: Il codice deterministico Python ha dimostrato una perfetta tenuta difensiva, respingendo i numeri sporcati dall'OCR cartaceo e validando esclusivamente i dati riscontrati al centesimo, mentre il modello Qwen ha dimostrato ottime capacità diagnostiche rilevando autonomamente il rumore dell'OCR e formulando richieste di integrazione documentale precise.

---

## 2. Dati dell'Ambiente e Hardware (Rif. `report_ambiente.txt`)

Come richiesto dal passo 1 della guida, si riportano i dati oggettivi rilevati dal sistema:

| Parametro | Valore Rilevato | Note |
| :--- | :--- | :--- |
| **Sistema Operativo** | Microsoft Windows 11 Pro 64-bit | Versione 10.0.26300 |
| **Processore (CPU)** | AMD RYZEN AI MAX+ 395 | 16 core fisici / 32 thread |
| **Memoria RAM** | 31,6 GB | Pienamente adeguata per modelli 27B quantizzati |
| **Scheda Grafica (GPU)** | AMD Radeon(TM) 8060S Graphics | 4 GB VRAM dedicata + memoria condivisa |
| **Ambiente Python** | Python 3.14.8 nativo (launcher `py`) | Ambiente virtuale locale isolato `.venv` |
| **Dipendenze pip installate** | `reportlab 5.0.1`, `pdfplumber 0.11.10`, `pillow 12.3.0`, `pypdfium2 5.14.0` | Installazione pulita da `requirements.txt` |
| **OCR locale** | Tesseract OCR attivo nel PATH di sistema | Utilizzato per le scansioni |

---

## 3. Configurazione del Modello Locale (LM Studio)

L'integrazione è stata configurata e verificata con i seguenti parametri:

* **Software di inferenza:** LM Studio (versione con CLI `lms.exe` presente in `C:\Users\Giuseppe\.lmstudio\bin\lms.exe`).
* **Endpoint API:** `http://127.0.0.1:1234/v1` (conforme alla Costituzione Agentica: loopback locale, nessun dato verso l'esterno).
* **ID esatto del modello (da `/v1/models`):** `qwen/qwen3.8-27b`.
* **File GGUF:** `Qwen3.8-27B-Q4_K_M.gguf` (dimensione 16,8 GB).
* **Quantizzazione:** `Q4_K_M`.
* **Finestra di contesto configurata:** `32.512` token.
* **Temperatura / Seed:** `temperatura: 0.0`, `seed: 7` (per la massima riproducibilità).

### Note Tecniche Fondamentali sull'Integrazione LM Studio:
1. **Compatibilità JSON (`formato_json: false`):**  
   Il client LM Studio v0.3.x restituisce errore `HTTP 400: 'response_format.type' must be 'json_schema' or 'text'` se riceve `"response_format": {"type": "json_object"}` senza uno schema rigido. Impostando `"formato_json": false` nel file `llm_config.json`, l'applicazione estrae e valida il JSON dalla risposta testuale tramite la funzione nativa `estrai_json()`, operando con successo al 100%.
2. **Gestione del Thinking / Reasoning Loop:**  
   Qwen 3.8 è un modello dotato di modalità *deep thinking* (`<think>...</think>`). Su prompt documentali molto ampi (~15.000 token per bilanci completi), con impostazione `Reasoning: Extra High` il modello consuma l'intero budget di generazione nei soli token di pensiero, rischiando l'interruzione per limite lunghezza prima di stampare il JSON.  
   **Soluzione adottata e validata:** Nel preset di LM Studio il parametro `Enable Thinking` è stato impostato su **OFF** (oppure `Reasoning Effort` su **Low**), garantendo risposte dirette in formato JSON valide in **meno di 4 minuti**.

File `llm_config.json` consolidato sul sistema:
```json
{
  "abilitato": true,
  "endpoint": "http://127.0.0.1:1234/v1",
  "modello": "qwen/qwen3.8-27b",
  "etichetta_modello": "Qwen 3.8 27B",
  "quantizzazione": "Q4_K_M",
  "contesto_configurato": 32512,
  "temperatura": 0.0,
  "seed": 7,
  "max_token": 10000,
  "timeout_s": 3600,
  "formato_json": false
}
```

---

## 4. Esito dei Test Sintetici di Installazione (Passo 2)

I 4 test di collaudo previsti dal protocollo di installazione sono stati eseguiti all'interno dell'ambiente `.venv`:

| Nome Test | Ambito Verificato | Esito |
| :--- | :--- | :---: |
| `test_pratica.py` | Apertura pratica, gate, verbale append-only con catena hash, persistenza riavvio | **OK** |
| `test_correzioni_rev3.py` | Condizioni reali e non-sospensione su documenti inesistenti | **OK** |
| `test_percorso_interfaccia.py` | Flusso completo web, bozze, incongruenze e checklist | **OK** |
| `test_llm_locale.py` | Rifiuto endpoint esterni, estrazione/verifica/applicazione con mock server | **OK** |

**Risultato installazione:** `INSTALLAZIONE COMPLETATA SENZA ERRORI`.

---

## 5. Collaudo Operativo con il Modello Locale su Fascicolo Documentale

È stato condotto il test operativo dell'interfaccia web e del livello modello locale (`/p/<pratica>/modello`).

### Dati dell'estrazione:
* **Identificativo Run:** `run_20261009-134221`
* **Tempo di elaborazione:** `236.53 s` (3 minuti e 56 secondi)
* **Validità JSON:** `sì` (JSON integro, estratto e parsato correttamente)
* **Documenti in fascicolo:** Bilancio d'esercizio 2025, situazione contabile infrannuale 2026, visura camerale.

### Tabella Risultati e Verifica Determinismo (*Human Gate*):
| Dato Proposto | Valore Proposto | Fonte / Pagina | Esito Verifica Codice | Motivo / Diagnostica |
| :--- | :---: | :---: | :---: | :--- |
| **Patrimonio netto** | `143.586,68 €` | Doc 1, Pag 1 | **RISCONTRATO** | Citazione e valore al centesimo coincidenti alla lettera. |
| **Disponibilità liquide** | `120.650,32 €` | Doc 1, Pag 1 | **NON RISCONTRATO** | Il valore non coincide con il testo OCR (nella scansione era 120.850,23). |
| **Totale attivo** | `1.136.436,23 €` | Doc 1, Pag 2 | **NON RISCONTRATO** | L'OCR ha scambiato un 9 per un 3 (`1.136.436` vs `1.136.496,23`). |
| **Debiti totali** | `990.269,55 €` | Doc 1, Pag 2 | **NON RISCONTRATO** | Calcolo non coincidente con una citazione singola. |
| **Debiti bancari** | `12.115,35 €` | Doc 1, Pag 1 | **NON RISCONTRATO** | Disallineamento da testo OCR (`12 1 15.3s`). |
| **Debiti pubblici** | `5.504,47 €` | Doc 1, Pag 1 | **NON RISCONTRATO** | Somma derivata, non presente alla lettera in pagina. |
| **Ricavi delle vendite** | `1.882.761,71 €` | Doc 1, Pag 3 | **NON RISCONTRATO** | Nel testo OCR compariva `1.8e .791,71`. |
| **Valore produzione** | *non disponibile* | Doc 1, Pag 3 | **MANCANTE** | Correttamente non inventato dal modello. |
| **Costi produzione** | *non disponibile* | Doc 1, Pag 3 | **MANCANTE** | Correttamente non inventato dal modello. |
| **Ammortamenti** | `10.000,00 €` | Doc 1, Pag 5 | **NON RISCONTRATO** | Citazione non letterale. |

### Considerazioni Critiche sul Risultato:
1. **Efficacia del filtro deterministico:**  
   Il test ha dimostrato la robustezza del motore: anche quando l'OCR introduce imperfezioni grafiche sui numeri (`1.8e .791,71`), il codice Python **impedisce categoricamente l'ingresso di dati non verificati**, proteggendo l'avvocato da falsi positivi.
2. **Capacità diagnostica e qualitativa di Qwen 3.8 27B:**  
   Nelle sezioni descrittive del payload JSON, il modello ha dimostrato un livello di ragionamento analitico eccellente:
   * **Rilevamento autonomo del rumore OCR:** Ha proposto esplicitamente nelle *Normalizzazioni*: *«Il testo OCR contiene errori di trascrizione (es. '12f 15,3s', '1.8e .791,71'). Si propone di usare i valori delle sottovoci per ricostruire i totali dove possibile.»*
   * **Incongruenza contabile individuata:** Ha rilevato correttamente che la quadratura tra attivo e passivo differiva esattamente per l'utile di periodo (102.642,33 €).
   * **Scenari e Richieste Prioritarie:** Ha sospeso la continuità aziendale motivando l'incertezza dei dati da OCR e la scarsa leggibilità del secondo documento, e ha formulato le 5 richieste prioritarie ottimali:
     1. Bilancio 2025 in formato leggibile (PDF nativo/Excel).
     2. Bilancio provvisorio aggiornato.
     3. Estratto di ruolo per i debiti pubblici.
     4. Dettaglio debiti bancari/finanziari.
     5. Stato di cassa aggiornato.

---

## 6. Note sul Registro Documentale e la Visura Camerale

Durante il collaudo è stato verificato il comportamento del modulo `Registro documentale`:
* La **Visura camerale** viene caricata e custodita regolarmente con il calcolo dell'impronta crittografica SHA-256.
* Come previsto dalle specifiche di progetto (`FUNZIONI.md`), per la visura la colonna *Lettura automatica* riporta correttamente: `Non prevista: inserimento manuale` (il parser deterministico a regole è attivo solo sui bilanci; l'anagrafica e le annotazioni della visura vengono delegate al livello modello locale o all'inserimento manuale assistito).
* L'eventuale mancato caricamento è prevenuto caricando i PDF singolarmente o selezionandoli contestualmente tramite `Ctrl+Click` nella finestra di dialogo del browser.

---

## 7. Conclusioni e Idoneità per l'Esperimento A/B

La postazione **GMKtec Windows 11** è formalmente **COLLAUDATA e PRONTA** per l'esecuzione del protocollo di test comparativo A/B (`ab/esegui_ab.py`):

1. Il runtime **LM Studio** con **Qwen 3.8 27B** opera in totale isolamento locale, con tempi di risposta attorno ai 3-4 minuti su fascicoli complessi e piena aderenza allo schema JSON.
2. Le tutele di sicurezza (Human Gate, marcatura dei dati DA VERIFICARE, controllo letterale delle citazioni) sono pienamente operative e verificate su dati reali.
3. Si raccomanda di mantenere l'impostazione `Reasoning: OFF` (o `Low`) su LM Studio per garantire tempi di elaborazione certi e prevenire overflow di contesto sui fascicoli multi-documento.

