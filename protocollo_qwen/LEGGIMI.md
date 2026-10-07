# Protocollo per Qwen (e per Claude nell'A/B)

File: `SISTEMA.md` (istruzioni), `SCHEMA.json` (formato della risposta), `ESEMPI.json` (esempio SINTETICO con numeri diversi dalla DEMO, per non contaminarla), `FONTI.md` (fonti normative e loro stato di verifica), `PROMPT_DI_SISTEMA_COMPLETO.txt` (il messaggio di sistema esattamente come inviato: istruzioni + campi + schema + fonti + parametri in sola lettura + esempio).
Configurazione per istruzioni ed esempi, **non** addestramento dei pesi. Il prompt è identico per i due sistemi e per le prove A e B: cambia solo il messaggio utente.
Se si modifica un file di questa cartella, l'impronta dei messaggi cambia: ripetere le prove con lo stesso protocollo per tutti.
