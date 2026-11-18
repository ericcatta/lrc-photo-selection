# Verifica della versione 0.1.0

## Eseguito sul Mac

- Backend/API e simulazione SDK Lua 5.1: **32 test passati** (`.venv/bin/python -m pytest -q`).
- Componenti React in DOM simulato: **6 test passati** (`npm --prefix web test`).
- Build TypeScript/Vite completata; controllo dipendenze Python superato.
- Apple Vision compilato con Swift e provato su un'immagine sintetica uniforme: nessun volto rilevato, nessun errore.
- Nessuna fotografia personale utilizzata nei test. Nessun catalogo letto tramite SQL o modificato direttamente.

I test coprono importazione idempotente, nomi duplicati, copie virtuali nel manifest, revisione concorrente, preset immutabili per servizio, target e copertura prudente, decisioni manuali, budget di spazio disco, ripresa, token e origine delle richieste, claim esclusivo delle stelle, journal prima della mutazione, conservazione rating e timestamp, annullamento e ricevute.

## Limiti aperti

La prova SDK reale su Lightroom Classic 16.0 è bloccata da `cgWindowNotFound` nella sessione grafica. Non è stato aperto Lightroom. Il campione autorizzato è il catalogo vecchio JPEG con le sue anteprime; il catalogo principale non autorizzato è escluso dal collaudo. Non dichiarare la compatibilità Lightroom reale come già certificata.

Verificare in particolare il comportamento di `lastEditTime` dopo una modifica manuale 0 → 3 → 0 stelle: i test simulati validano il confronto, non provano la semantica del campo Adobe. Se Lightroom non segnala questo cambiamento, il confronto non può rilevare quella sequenza e la procedura di importazione/applicazione va rivista prima dell'uso operativo.

La registrazione distingue cataloghi per percorso e fotografie per UUID + localIdentifier. Non distingue automaticamente la sostituzione del file catalogo allo stesso percorso con una copia che conserva gli stessi identificativi: in quel caso non riutilizzare servizi precedenti e registrare nuovamente il catalogo.

Il journal locale con flush/close e rinomina protegge dalle interruzioni del processo; non è una garanzia contro guasti hardware o perdita di alimentazione prima della persistenza fisica del filesystem.

La baseline confronta JPEG identici e conserva tutto il resto. Non sono calibrati modelli semantici, riconoscimento persone, scene, occhi chiusi, pose o punteggi estetici. SigLIP 2 non è stato scaricato né eseguito. Le evidenze opzionali non influenzano automaticamente le esclusioni. Offset temporali salvati, non ancora utilizzati dalla baseline.

Modalità OpenAI non implementata/abilitata per l'analisi: mancano campione misurato, scelta modello, configurazione Keychain, stima e budget autorizzato. Nessuna richiesta API o spesa è stata effettuata.

## Audit dipendenze web

`npm audit --omit=dev`: **0 vulnerabilità**. L'audit completo segnala la catena di strumenti di sviluppo basata su picomatch (ReDoS, GHSA-fc5q-39xc-vjpf), senza correzione pubblicata nella fonte consultata il 18 novembre 2026. Non adottare automaticamente il downgrade suggerito dall'audit. Il prodotto serve solo asset statici dal backend Python: Vite/Vitest e i glob di build non ricevono input dell'utente né sono esposti come servizio dell'app. Rivalutare l'advisory prima di aggiornare gli strumenti o esporre un dev server.

Fonte: https://github.com/advisories/GHSA-fc5q-39xc-vjpf

Un avviso di deprecazione Starlette riguarda il test client httpx; i test passano. Nessun errore di esecuzione rilevato nei controlli svolti.
