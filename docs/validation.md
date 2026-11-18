# Verifica dell’implementazione

## Aggiornamento dopo audit — 18 novembre 2026

- **47 test backend/SDK simulati passati**, inclusi i 15 test Lua; **13 test React passati**; build TypeScript/Vite riuscita.
- Regressioni: piani A/B e ripresa dopo riavvio, conferma esatta, annullamento durante attesa del write gate, riuso ricevuta esistente, import incrementale idempotente, catalogo errato e identità in conflitto, protezione baseline/decisioni/target, cronologia persistente e sostituzione atomica, compatibilità digest manifest v1, archivio e riapertura.
- Analisi locale esplicita e cache verificate con encoder/detector sintetici: ripresa dopo interruzione, invalidazione per versione del modello, errore di rilevamento non memorizzato. NumPy installato nel venv per il test dei vicini visivi; nessun peso IA scaricato.
- Prova integrata `scripts/browser_smoke.mjs` con Chrome headless e backend HTTP reale: decisione, annulla/ripristina, analisi Apple Vision su anteprime uniformi sintetiche, confronto e risoluzione, piano confermato, claim e ricevuta SDK simulata, aggiunta foto, archivio e riapertura. Nessuna stella reale applicata. Desktop 1500 px e mobile 390 px senza overflow.
- `scripts/benchmark_scale.py`, rilevazione prima dell’integrazione finale: 1.000 elementi, dettaglio circa 16 ms, baseline 0,087 s; 5.000 elementi, dettaglio circa 63 ms, baseline 1,002 s. Tutte le candidate conservate. Solo metadati e una preview sintetica per servizio; non è un benchmark RAW, IA o del rendering di migliaia di miniature.
- Ritentato accesso Finder: `cgWindowNotFound`. **Collaudo reale Lightroom non eseguito.** Restano da verificare `lastEditTime`, disponibilità delle anteprime JPEG senza originali, comportamento della selezione con filtri e semantica SDK reale.
- La raccolta locale facoltativa è rinviata fino a tale collaudo; nessuna creazione o sincronizzazione di raccolte presente nel codice. Nessun modello semantico calibrato sul campione reale, nessuna API OpenAI avviata.

Annulla/ripristina agisce sulle decisioni manuali; non annulla le analisi o le stelle Lightroom. Le garanzie di serializzazione dei test riguardano le normali operazioni SDK del plugin e i controlli nel write gate, non un’esecuzione arbitraria di più processi indipendenti sullo stesso catalogo.

## Verifica iniziale 0.1.0 (storico)

## Eseguito sul Mac

- Backend/API e simulazione SDK Lua 5.1: **32 test passati** (`.venv/bin/python -m pytest -q`).
- Componenti React in DOM simulato: **7 test passati** (`npm --prefix web test`).
- Build TypeScript/Vite completata; controllo dipendenze Python superato.
- Prova HTTP con server reale su loopback e sei anteprime sintetiche: asset compilati, autenticazione cookie, importazione, selezione conservativa (5 candidate per target 3) e piano di 4 rating idonei verificati. Server temporaneo arrestato dopo la prova.
- Apple Vision compilato con Swift e provato su un'immagine sintetica uniforme: nessun volto rilevato, nessun errore.
- Nessuna fotografia personale utilizzata nei test. Nessun catalogo letto tramite SQL o modificato direttamente.

I test coprono importazione idempotente, nomi duplicati, copie virtuali nel manifest, revisione concorrente, preset immutabili per servizio, target e copertura prudente, decisioni manuali, budget di spazio disco, ripresa, token e origine delle richieste, claim esclusivo delle stelle, journal prima della mutazione, conservazione rating e timestamp, annullamento e ricevute.

## Limiti aperti

La prova SDK reale su Lightroom Classic 16.0 è bloccata da `cgWindowNotFound` nella sessione grafica. Non è stato aperto Lightroom. Il campione autorizzato è il catalogo vecchio JPEG con le sue anteprime; il catalogo principale non autorizzato è escluso dal collaudo. Non dichiarare la compatibilità Lightroom reale come già certificata.

Verificare in particolare il comportamento di `lastEditTime` dopo una modifica manuale 0 → 3 → 0 stelle: i test simulati validano il confronto, non provano la semantica del campo Adobe. Se Lightroom non segnala questo cambiamento, il confronto non può rilevare quella sequenza e la procedura di importazione/applicazione va rivista prima dell'uso operativo.

La registrazione distingue cataloghi per percorso e fotografie per UUID + localIdentifier. Non distingue automaticamente la sostituzione del file catalogo allo stesso percorso con una copia che conserva gli stessi identificativi: in quel caso non riutilizzare servizi precedenti e registrare nuovamente il catalogo.

Il journal locale con flush/close e rinomina protegge dalle interruzioni del processo; non è una garanzia contro guasti hardware o perdita di alimentazione prima della persistenza fisica del filesystem.

La baseline confronta JPEG identici e conserva tutto il resto. Non sono calibrati modelli semantici, riconoscimento persone, scene, occhi chiusi, pose o punteggi estetici. SigLIP 2 non è stato scaricato né eseguito. Le evidenze opzionali non influenzano automaticamente le esclusioni. Offset temporali usati dall’ordinamento cronologico della web app; non sono evidenza di equivalenza nel motore.

Modalità OpenAI non implementata/abilitata per l'analisi: mancano campione misurato, scelta modello, configurazione Keychain, stima e budget autorizzato. Nessuna richiesta API o spesa è stata effettuata.

## Audit dipendenze web

`npm audit --omit=dev`: **0 vulnerabilità**. L'audit completo segnala la catena di strumenti di sviluppo basata su picomatch (ReDoS, GHSA-fc5q-39xc-vjpf), senza correzione pubblicata nella fonte consultata il 18 novembre 2026. Non adottare automaticamente il downgrade suggerito dall'audit. Il prodotto serve solo asset statici dal backend Python: Vite/Vitest e i glob di build non ricevono input dell'utente né sono esposti come servizio dell'app. Rivalutare l'advisory prima di aggiornare gli strumenti o esporre un dev server.

Fonte: https://github.com/advisories/GHSA-fc5q-39xc-vjpf

Un avviso di deprecazione Starlette riguarda il test client httpx; i test passano. Nessun errore di esecuzione rilevato nei controlli svolti.

## Revisione dell’interfaccia

Layout a pagina unica con provino principale, strumenti laterali, palette neutra chiara e barra superiore scura. Slider quantità sincronizzato con inserimento numerico preciso; slider separato per la dimensione delle anteprime. I dettagli dei criteri restano espandibili e i limiti del motore sono visibili.

Verificati build e 7 test React, compresi sincronizzazione slider/campo, limiti della quantità e assenza di avvio implicito. Acquisito screenshot reale con Chrome headless autorizzato e sei anteprime sintetiche; controllo desktop a 1500 px e mobile a 390 px senza overflow orizzontale. Nessun catalogo o fotografia reale coinvolto.
